from text2music.agent.vst_service import _host_context
import json
from pathlib import Path
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import pytest
from text2music.agent import vst_service


@pytest.fixture
def service_api(tmp_path, monkeypatch):
    state = vst_service.TriceratopsState(workspace_id="unit-fixture")
    monkeypatch.setattr(vst_service, "APP", state)
    for name in ("STATUS", "HISTORY", "CONVERSATION", "CONVERSATION_ARCHIVE"):
        monkeypatch.setattr(vst_service, name, tmp_path / name.lower())
    server = ThreadingHTTPServer(("127.0.0.1", 0), vst_service.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def post(path, payload):
        request = Request(f"http://127.0.0.1:{server.server_port}{path}",
                          data=json.dumps(payload).encode(),
                          headers={"Content-Type": "application/json"})
        try:
            response = urlopen(request, timeout=3)
        except HTTPError as exc:
            response = exc
        with response:
            return response.code, json.load(response)

    yield state, post
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)


def test_invalid_chat_is_rejected_without_sticking_busy(service_api):
    state, post = service_api
    assert post("/chat", {"message": " "})[0] == 400
    assert post("/chat", {"message": "hello", "host": {"time_signature": "oops"}})[0] == 400
    assert not state.busy
    assert post("/chat", ["not a JSON object"])[0] == 400
    assert post("/chat", {"message": "convert", "action": "imaginary_tool"})[0] == 400
    assert post("/chat", {"message": "convert", "action": []})[0] == 400
    assert not state.busy


def test_second_editor_preserves_active_task_and_result(service_api):
    state, post = service_api
    state.busy = True
    state.last_reply = "Generating"
    state.last_result = {"midi": "existing.mid"}
    vst_service._write_status("sampling", "60", "Generating")
    code, result = post("/session/open", {"session": "second-editor"})
    assert code == 200
    assert result["busy"] is True
    assert result["reply"] == "Generating"
    assert result["result"]["midi"] == "existing.mid"
    assert result["state"] == "sampling"


def test_clear_chat_rejects_active_task_and_resets_idle_result(service_api):
    state, post = service_api
    state.busy = True
    code, error = post("/chat/clear", {})
    assert code == 409
    assert "Stop the active task" in error["error"]
    state.busy = False
    state.last_result = {"midi": "stale.mid"}
    state.last_error = "old error"
    code, result = post("/chat/clear", {})
    assert code == 200
    assert result["result"] == {}
    assert result["error"] == ""


def test_direct_invalid_host_task_releases_busy(service_api):
    state, _ = service_api
    state.busy = True
    state.run_chat({"message": "hello", "host": {"tempo": "invalid"}})
    assert not state.busy
    assert "Invalid host context" in state.last_error


def test_busy_chat_and_missing_import_return_actionable_errors(service_api):
    state, post = service_api
    state.busy = True
    code, result = post("/chat", {"message": "hello"})
    assert code == 409
    assert result["error"] == "agent is busy"
    state.busy = False
    code, result = post("/import_reaper", {})
    assert code == 400
    assert "No MIDI file" in result["error"]


def test_stems_use_audio_import_command(service_api, monkeypatch):
    state, post = service_api
    state.last_result = {"files": ["E:\\out\\bass.wav", "E:\\out\\vocals.wav"]}
    calls = []
    monkeypatch.setattr(vst_service, "_trigger_reaper_import",
                        lambda command, files: calls.append((command, files)) or {"triggered": True, "detail": ""})
    code, result = post("/import_reaper", {})
    assert code == 200 and result["ok"]
    assert calls == [("import_audio_stems", "E:\\out\\bass.wav|E:\\out\\vocals.wav")]
    state.last_result = {"trace": []}
    code, result = post("/import_reaper", {"files": ["E:\\out\\bass.wav"]})
    assert code == 200 and result["ok"]
    assert calls[-1] == ("import_audio_stems", "E:\\out\\bass.wav")
    assert post("/import_reaper", {"files": "bad"})[0] == 400


def test_import_preserves_agent_reply_and_reports_bridge_failure(service_api, monkeypatch):
    state, post = service_api
    state.last_reply = "Four real stems are ready."
    monkeypatch.setattr(vst_service, "_trigger_reaper_import",
                        lambda *args: {"triggered": False, "detail": "REAPER is unavailable"})
    code, result = post("/import_reaper", {"file": "E:\\out\\score.mid"})
    assert code == 503 and not result["ok"]
    assert result["error"] == "REAPER is unavailable"
    assert state.last_reply == "Four real stems are ready."
    assert state.last_error == ""


def test_opening_editor_does_not_load_an_unrequested_model(service_api, monkeypatch):
    state, post = service_api
    from text2music.agent import model_job
    monkeypatch.setattr(model_job, "run_model_job", lambda *a, **k: pytest.fail("unrequested model load"))
    assert post("/session/open", {"session": "audio-editor"})[0] == 200


def test_host_context_accepts_vst_string_time_signature():
    context = _host_context({"tempo": 96, "time_signature": "4/4", "sample_rate": 48000})

    assert "Tempo: 96.00 BPM" in context
    assert "Time Signature: 4/4" in context


def test_host_context_accepts_structured_time_signature():
    context = _host_context({"time_signature": [6, 8]})

    assert "Time Signature: 6/8" in context


def test_chat_rejects_unsupported_language_without_starting_task(service_api):
    state,post=service_api
    code,result=post("/chat",{"message":"analyze","language":"fr"})
    assert code==400 and "language must be zh or en" in result["error"]
    assert not state.busy


def test_undo_follows_loaded_files_lineage_through_interleaved_and_old_history(tmp_path, monkeypatch):
    # Real files represent two independent edits and an unrelated project/branch.
    original, first, second, other = [tmp_path / name for name in
                                     ("original.mid", "first.mid", "second.mid", "other.mid")]
    for path in (original, first, second, other):
        path.write_bytes(b"test history identity only, not model output")
    history = tmp_path / "history.jsonl"
    monkeypatch.setattr(vst_service, "HISTORY", history)
    entries = [{"midi": str(first), "source": str(original)},
               {"midi": str(second), "parent_midi": str(first)}]
    entries += [{"midi": str(other)} for _ in range(25)]
    history.write_text("\n".join(json.dumps(entry) for entry in entries))
    before = history.read_bytes()
    restored = vst_service._previous_midi_version(second)
    assert restored["midi"] == str(first)
    assert vst_service._previous_midi_version(first)["midi"] == str(original)
    with pytest.raises(ValueError, match="no recorded prior"):
        vst_service._previous_midi_version(original)
    with pytest.raises(ValueError, match="no recorded prior"):
        vst_service._previous_midi_version(other)
    assert history.read_bytes() == before


def test_undo_missing_parent_never_restores_an_unrelated_file(tmp_path, monkeypatch):
    current = tmp_path / "current.mid"
    current.touch()
    history = tmp_path / "history.jsonl"
    monkeypatch.setattr(vst_service, "HISTORY", history)
    history.write_text(json.dumps({"midi": str(current), "parent_midi": str(tmp_path / "missing.mid")}))
    with pytest.raises(FileNotFoundError, match="Previous MIDI version is missing"):
        vst_service._previous_midi_version(current)
    with pytest.raises(ValueError, match="Load the MIDI version"):
        vst_service._previous_midi_version(None)


def test_host_import_preparation_and_matching_receipt(service_api, tmp_path, monkeypatch):
    state, post = service_api
    monkeypatch.setattr(vst_service, "RUNS_DIR", tmp_path)
    def forbidden_launch(*args, **kwargs):
        raise AssertionError("Host preparation must not launch another process")
    monkeypatch.setattr(vst_service.subprocess, "Popen", forbidden_launch)
    code, prepared = post("/prepare_import_reaper", {"file": str(tmp_path / "real-output.mid")})
    assert code == 200 and len(prepared["request_id"]) == 32
    assert Path(prepared["script_path"]).is_file()
    directory = Path(prepared["script_path"]).parent
    assert prepared["request_id"] in (directory / "reaper-command.txt").read_text()
    assert post("/import_reaper_receipt", {"request_id": prepared["request_id"]})[0] == 409
    (directory / "reaper-import-result.txt").write_text(
        f"REQUEST_ID: {prepared['request_id']}\nIMPORTED: 1\nPROJECT: /host/project.rpp\nERROR: \n")
    code, result = post("/import_reaper_receipt", {"request_id": prepared["request_id"]})
    assert code == 200 and result["ok"] and result["imported"] == 1
    assert result["project_path"] == "/host/project.rpp"


def test_discard_endpoint_removes_only_its_private_pending_import(service_api, tmp_path, monkeypatch):
    state, post = service_api
    monkeypatch.setattr(vst_service, "RUNS_DIR", tmp_path)
    _, one = post("/prepare_import_reaper", {"file": "/one.mid"})
    _, two = post("/prepare_import_reaper", {"file": "/two.mid"})
    code, result = post("/discard_import_reaper", {"request_id": one["request_id"]})
    assert code == 200 and not result["ok"] and result["imported"] == 0
    assert "discarded" in result["error"]
    assert not Path(one["script_path"]).exists()
    assert Path(two["script_path"]).exists()
    assert post("/discard_import_reaper", {"request_id": "../other"})[0] == 400


def test_generation_dispatch_reaches_model_job_after_worker_cleanup(tmp_path, monkeypatch):
    """Dispatch regression only; does not fabricate a generated MIDI result."""
    from text2music.agent import model_job, symbolic_models, tool_loop
    for name in ('RUNS_DIR', 'STATUS', 'HISTORY', 'MEMORY', 'CONVERSATION', 'CONVERSATION_ARCHIVE'):
        monkeypatch.setattr(vst_service, name, tmp_path if name == 'RUNS_DIR' else tmp_path/name.lower())
    monkeypatch.setattr(symbolic_models, 'model_status', lambda: {})
    calls = []
    def probe_model(tool, arguments, **kwargs):
        calls.append((tool, arguments))
        raise RuntimeError('model-job-probe-reached')
    def probe_loop(message, *, execute, **kwargs):
        return execute('generate_draft', {'request': 'Sparse piano, no drums', 'max_tokens': 96})
    monkeypatch.setattr(model_job, 'run_model_job', probe_model)
    monkeypatch.setattr(tool_loop, 'run_tool_loop', probe_loop)
    state = vst_service.TriceratopsState(workspace_id="unit-fixture")
    state.run_chat({'message': 'Generate piano', 'host': {}})
    assert len(calls) == 1 and calls[0][0] == 'generate_draft'
    assert calls[0][1]['max_tokens'] == 96
    assert 'model-job-probe-reached' in state.last_error
    assert 'NameError' not in state.last_error


def test_losing_backend_start_does_not_overwrite_active_task_status(tmp_path, monkeypatch):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
        occupied.bind(('127.0.0.1', 0));occupied.listen()
        monkeypatch.setattr(vst_service, 'HOST', '127.0.0.1')
        monkeypatch.setattr(vst_service, 'PORT', occupied.getsockname()[1])
        monkeypatch.setattr(vst_service, 'RUNS_DIR', tmp_path)
        monkeypatch.setattr(vst_service, 'STATUS', tmp_path/'status.txt')
        before = 'STATE: working\nPROGRESS: 30\nDETAIL: generate_draft: running\n'
        vst_service.STATUS.write_text(before)
        import pytest
        with pytest.raises(OSError):
            vst_service.main()
        assert vst_service.STATUS.read_text() == before


def test_archive_compaction_does_not_drop_old_constraints_and_clear_starts_new_context(service_api):
    state, post = service_api
    state.append_turn('user','Important early constraint: no drums.')
    for i in range(204):
        state.append_turn('assistant',f'Historical reply {i}')
    vst_service._compact_conversation()
    assert vst_service.CONVERSATION_ARCHIVE.is_file()
    history = vst_service._conversation_history()
    assert len(history) == 205
    assert history[0]['content'] == 'Important early constraint: no drums.'
    assert post('/chat/clear',{})[0] == 200
    assert vst_service._conversation_history() == []
    state.append_turn('user','New conversation.')
    assert [h['content'] for h in vst_service._conversation_history()] == ['New conversation.']


def test_verification_blocks_task_and_settings_races_and_reports_failure(service_api, monkeypatch):
    from text2music.agent import llm_backend
    state, post = service_api
    started, release = threading.Event(), threading.Event()
    def verify(selection):
        assert selection == 'local'
        started.set()
        assert release.wait(5)
        raise RuntimeError('GPU server unavailable')
    monkeypatch.setattr(llm_backend,'check_chat_backend',verify)
    try:
        assert post('/chat/verify',{'session':'editor','chat_backend':'local'})[0] == 202
        assert started.wait(2)
        assert state.chat_switches['editor']['state'] == 'verifying'
        assert post('/chat/verify',{'session':'other','chat_backend':'remote'})[0] == 409
        assert post('/chat',{'message':'Do not start during verification'})[0] == 409
    finally:
        release.set()
    import time
    deadline = time.monotonic()+3
    while state.chat_switches['editor']['state'] == 'verifying' and time.monotonic()<deadline:
        time.sleep(.01)
    assert state.chat_switches['editor']['state'] == 'failed'
    assert 'GPU server unavailable' in state.chat_switches['editor']['error']
    assert not state.busy


def test_persistent_executor_record_retains_actual_values_without_recursive_trace(service_api):
    state, _ = service_api
    state.append_turn('assistant','Analysis done.',executions=[{'tool':'analyze_audio','state':'completed',
        'arguments':{},'result':{'tempo':93,'key':'D minor','trace':['recursive'],'context_usage':{'large':True}}}])
    event = vst_service._conversation_history()[0]['executions'][0]
    assert event['result'] == {'tempo':93,'key':'D minor'}
