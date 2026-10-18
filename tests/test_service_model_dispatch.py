"""Exercise every service-to-model dispatch without loading weights in unit tests."""
import json
import wave
from pathlib import Path

import pytest
from mido import Message, MidiFile, MidiTrack

from text2music.agent import model_job, tool_loop, vst_service


def make_midi(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    midi = MidiFile()
    track = MidiTrack()
    midi.tracks.append(track)
    track.extend([Message("note_on", note=60, velocity=80),
                  Message("note_off", note=60, time=480)])
    midi.save(path)
    return path


@pytest.fixture
def isolated_service(tmp_path, monkeypatch):
    monkeypatch.delenv("TRICERATOPS_CONFIG", raising=False)
    monkeypatch.setattr(vst_service, "RUNS_DIR", tmp_path)
    for name in ("STATUS", "HISTORY", "MEMORY", "CONVERSATION", "CONVERSATION_ARCHIVE"):
        monkeypatch.setattr(vst_service, name, tmp_path / name.lower())
    return vst_service.TriceratopsState(workspace_id="unit-fixture")


@pytest.mark.parametrize("tool,extra", [
    ("generate_draft", {"backend": "midi_llm", "max_tokens": 96,
                        "constraints": {"tempo_bpm": 90}}),
    ("continue_midi", {"bar_count": 4}),
    ("infill_midi", {"track_ids": [0], "bar_ids": [0]}),
    ("separate_stems", {}),
    ("audio_to_midi", {}),
])
def test_model_dispatch_reaches_adapter_and_publishes_output(isolated_service, tmp_path, monkeypatch, tool, extra):
    state = isolated_service
    midi = make_midi(tmp_path / "input.mid")
    audio = tmp_path / "input.wav"
    with wave.open(str(audio), "wb") as stream:
        stream.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
        stream.writeframes(bytes(4410))
    request = "Dreamy, distant piano; keep the fragile mood and a little rhythmic hesitation."
    calls = []

    def job(name, arguments, **kwargs):
        calls.append((name, arguments))
        output = arguments.get("destination", arguments.get("output_dir", tmp_path) / "output.mid")
        if name == "separate_stems":
            folder = arguments["output_dir"]
            folder.mkdir(parents=True)
            paths = []
            for stem in ("vocals", "drums", "bass", "other"):
                path = folder / (stem + ".wav")
                path.write_bytes(audio.read_bytes())
                paths.append(str(path))
            return {"files": paths}
        make_midi(output)
        if name == "audio_to_midi":
            (output.parent / "runtime-device.json").write_text(json.dumps({"note_count": 1, "actual_device": "cpu"}))
            return {"files": [str(output)]}
        return {"midi": str(output), "backend": "midi_llm" if name == "generate_draft" else "midi_gpt",
                "added_bars": 4, "original_bars": 1, "notes": 1}

    def chat(message, *, execute, on_event, **kwargs):
        arguments = {"request": request, **extra}
        result = execute(tool, arguments)
        event = {"step": 1, "tool": tool, "arguments": arguments, "state": "completed", "result": result}
        on_event(event)
        return tool_loop.ToolDecision(tool, arguments, trace=[event])

    monkeypatch.setattr(model_job, "run_model_job", job)
    monkeypatch.setattr(tool_loop, "run_tool_loop", chat)
    state.run_chat({"message": request, "midi_path": str(midi), "audio_path": str(audio), "language": "en"})

    assert not state.busy
    assert state.last_error == ""
    assert vst_service._read_status()["state"] == "completed"
    assert calls[0][0] == tool
    assert state.last_result["trace"][0]["state"] == "completed"
    if tool == "generate_draft":
        assert calls[0][1]["prompt"] == request
        assert calls[0][1]["constraints"] == extra["constraints"]
        assert calls[0][1]["max_tokens"] == 96
        assert Path(state.last_result["midi"]).is_file()
        assert json.loads(vst_service.HISTORY.read_text())["request"] == request


def test_features_button_reports_current_models_without_loading_weights(isolated_service, monkeypatch):
    monkeypatch.setattr(model_job, "run_model_job", lambda *a, **k: pytest.fail("unexpected model load"))
    isolated_service.run_chat({"message": "Features", "action": "list_capabilities", "language": "en"})
    assert not isolated_service.last_error
    assert set(isolated_service.last_result["models"]) == {"midi_llm", "midi_gpt"}


def test_retired_worker_status_cannot_replace_current_task(isolated_service, tmp_path):
    worker = tmp_path / "worker_queue"
    worker.mkdir()
    (worker / "worker-state.txt").write_text("STATE: error\\nDETAIL: retired worker failed\\n")
    vst_service._write_status("completed", "100", "MIDI ready")
    snapshot = isolated_service.snapshot()
    assert snapshot["state"] == "completed"
    assert snapshot["detail"] == "MIDI ready"
    assert not any(key.startswith("worker_") for key in snapshot)
