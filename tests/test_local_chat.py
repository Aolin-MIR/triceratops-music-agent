import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
import pytest
from text2music.agent import llm_backend as backend
from text2music.agent.direct_actions import action_arguments, run_direct_action


def test_disabled_chat_does_not_create_cloud_client(monkeypatch):
    monkeypatch.setenv("TRICERATOPS_LLM_PROVIDER", "disabled")
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    assert backend.check_chat_backend()["direct_buttons"]
    with pytest.raises(RuntimeError, match="Chat is disabled"):
        backend.create_chat_client()


@pytest.mark.parametrize("url", ["https://example.com", "http://127.0.0.1/v1", "http://user:secret@localhost:11434"])
def test_local_provider_rejects_remote_or_credential_urls(monkeypatch, url):
    monkeypatch.setenv("TRICERATOPS_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("TRICERATOPS_OLLAMA_URL", url)
    with pytest.raises(ValueError):
        backend.ChatSettings.load()


def test_local_chat_cannot_be_configured_for_cpu(monkeypatch):
    monkeypatch.setenv('TRICERATOPS_LLM_PROVIDER', 'llama_cpp')
    monkeypatch.setenv('TRICERATOPS_LLM_DEVICE', 'cpu')
    with pytest.raises(ValueError, match='requires GPU'):
        backend.ChatSettings.load()


@pytest.mark.parametrize("action", ["more_energy", "tighten_timing", "continue_midi"])
def test_button_preset_cannot_be_replaced_with_arbitrary_arguments(action):
    with pytest.raises(ValueError, match="cannot be overridden"):
        action_arguments(action, {"operations": {"transpose": 12}})


def test_direct_action_rejects_invalid_arguments_before_any_mutation():
    with pytest.raises(ValueError, match="Invalid transform_midi"):
        run_direct_action("transform_midi", arguments={"request": "edit", "operations": {"transpose": 999}},
                          execute=lambda *a: pytest.fail("invalid edit executed"))


def test_direct_error_is_preserved_without_chat_fallback(monkeypatch):
    monkeypatch.setattr(backend, "create_chat_client", lambda: pytest.fail("button invoked LLM"))
    def execute(*args):
        raise RuntimeError("weights missing")
    result = run_direct_action("audio_to_midi", arguments={}, execute=execute)
    assert result.trace[0]["state"] == "failed"
    assert result.trace[0]["result"]["error"] == "RuntimeError: weights missing"


def test_cancelled_button_does_not_execute():
    result = run_direct_action("continue_midi", arguments={}, cancelled=lambda: True,
                               execute=lambda *a: pytest.fail("cancelled operation executed"))
    assert result.trace[0]["state"] == "failed"


@pytest.fixture
def ollama_server(monkeypatch):
    requests = []
    memory = {"size": 4_000_000_000, "size_vram": 4_000_000_000}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            requests.append((self.path, None))
            self.reply({"models": [{"name": "unit-model:4b", **memory}]})
        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append((self.path, data))
            if self.path == '/api/show':
                self.reply({"capabilities": ["completion", "tools"]})
            elif self.path == '/api/chat':
                if any(item['role'] == 'tool' for item in data['messages']):
                    self.reply({"done": True, "message": {"content": "TRICERATOPS_OK_37"}})
                else:
                    self.reply({"done": True, "message": {"tool_calls": [{"function": {
                        "name": "compatibility_probe", "arguments": {"value": 37}}}]}})
            else:
                pytest.fail('Unexpected local API route')
        def reply(self, data):
            body = json.dumps(data).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv('TRICERATOPS_LLM_PROVIDER', 'ollama')
    monkeypatch.setenv('TRICERATOPS_OLLAMA_URL', f'http://127.0.0.1:{server.server_port}')
    monkeypatch.setenv('TRICERATOPS_LOCAL_MODEL', 'unit-model:4b')
    monkeypatch.setenv('TRICERATOPS_LLM_DEVICE', 'gpu')
    monkeypatch.setenv('HTTP_PROXY', 'http://127.0.0.1:1')
    monkeypatch.delenv('QWEN_API_KEY', raising=False)
    yield requests, memory
    server.shutdown()
    server.server_close()
    thread.join(3)


def test_local_native_calls_replay_and_fixed_residency_without_cloud_key(ollama_server):
    requests, _ = ollama_server
    result = backend.check_chat_backend()
    assert result['native_tools'] and result['tool_result_replay'] and result['resident']
    chats = [data for path, data in requests if path == '/api/chat']
    assert len(chats) == 2
    assert all(data['keep_alive'] == -1 and data['options']['num_gpu'] == 999 for data in chats)
    replay = next(item for item in chats[-1]['messages'] if item['role'] == 'tool')
    assert replay['tool_name'] == 'compatibility_probe'
    assert all('keep_alive' not in (data or {}) or data['keep_alive'] != 0 for _, data in requests)


def test_partial_gpu_offload_is_rejected_instead_of_hiding_it(ollama_server):
    _, memory = ollama_server
    memory['size_vram'] = 2_000_000_000
    with pytest.raises(RuntimeError, match='does not fully reside on GPU'):
        backend.check_chat_backend()


def test_fixed_cpu_local_chat_is_rejected_before_server_use(ollama_server, monkeypatch):
    requests, memory = ollama_server
    monkeypatch.setenv('TRICERATOPS_LLM_DEVICE', 'cpu')
    memory['size_vram'] = 0
    with pytest.raises(ValueError, match='requires GPU'):
        backend.check_chat_backend()
    assert not requests
    assert all(data['options']['num_gpu'] == 0 for path, data in requests if path == '/api/chat')


def test_direct_buttons_edit_real_midi_with_chat_disabled(tmp_path, monkeypatch):
    from mido import MidiFile, MidiTrack, Message
    from text2music.agent import vst_service
    monkeypatch.setenv('TRICERATOPS_LLM_PROVIDER', 'disabled')
    monkeypatch.delenv('QWEN_API_KEY', raising=False)
    monkeypatch.setattr(backend, 'create_chat_client', lambda: pytest.fail('direct button invoked LLM'))
    for name in ('RUNS_DIR', 'STATUS', 'HISTORY', 'MEMORY', 'CONVERSATION', 'CONVERSATION_ARCHIVE'):
        monkeypatch.setattr(vst_service, name, tmp_path if name == 'RUNS_DIR' else tmp_path / name.lower())
    source = tmp_path / 'source.mid'
    midi = MidiFile()
    midi.tracks.append(MidiTrack([Message('note_on', note=60, velocity=70, time=23),
                                 Message('note_off', note=60, time=407)]))
    midi.save(source)
    state = vst_service.TriceratopsState()
    state.run_chat({'message': 'This text must not be parsed as the button parameters', 'action': 'more_energy',
                    'midi_path': str(source), 'host': {}, 'language': 'en'})
    assert state.last_error == '' and not state.busy
    result = MidiFile(state.last_result['midi'])
    notes = [event for track in result.tracks for event in track if event.type == 'note_on']
    assert [(event.note, event.velocity, event.time) for event in notes] == [(60, 82, 23)]
    assert state.last_result['trace'][0]['dispatch'] == 'direct'
    state.run_chat({'message': 'analyze', 'action': 'analyze_selected_midi', 'midi_path': str(source),
                    'host': {}, 'language': 'zh'})
    assert not state.last_error and '1 个音符' in state.last_reply
