from pathlib import Path

import pytest

from text2music.agent import symbolic_models
from text2music.agent.tool_loop import tool_schemas


def test_symbolic_tool_schemas_expose_real_backends():
    functions = {item["function"]["name"]: item["function"] for item in tool_schemas()}
    assert functions["generate_draft"]["parameters"]["properties"]["backend"]["enum"] == [
        "auto", "midi_llm"
    ]
    assert functions["infill_midi"]["parameters"]["properties"]["bar_ids"]["minItems"] == 1
    assert functions["continue_midi"]["parameters"]["properties"]["bar_count"]["maximum"] == 32


@pytest.mark.parametrize("length", [0, 33, True, "4"])
def test_continuation_rejects_invalid_length_before_loading_model(tmp_path, length):
    with pytest.raises(ValueError, match="between 1 and 32"):
        symbolic_models.continue_midi_gpt(tmp_path / "source.mid", tmp_path / "out.mid", bar_count=length)


def test_missing_model_fails_instead_of_falling_back(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(symbolic_models, "MIDI_LLM_MODEL", tmp_path / "missing")
    monkeypatch.setattr(symbolic_models, "MIDI_GPT_MODEL", tmp_path / "missing-gpt.safetensors")
    with pytest.raises(RuntimeError, match="not installed completely"):
        symbolic_models.generate_midi_llm("piano", tmp_path / "out")


def test_text_to_midi_returns_only_parseable_midi_with_notes(monkeypatch, tmp_path: Path):
    import mido
    from types import SimpleNamespace

    output = tmp_path / "output"
    output.mkdir()
    monkeypatch.setattr(symbolic_models, "_require_model", lambda _: None)

    def generate(*args, **kwargs):
        midi = mido.MidiFile()
        track = mido.MidiTrack()
        midi.tracks.append(track)
        track.extend([mido.Message("note_on", note=60, velocity=80, time=0),
                      mido.Message("note_off", note=60, velocity=0, time=120)])
        midi.save(output / "generated.mid")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(symbolic_models.subprocess, "run", generate)
    result = symbolic_models.generate_midi_llm("a sparse piano phrase", output)
    assert result["raw_midi"] == str(output / "generated.mid")
    assert result["validation"]["note_count"] == 1
    assert mido.MidiFile(result["midi"]).length > 0


@pytest.mark.parametrize("content, expected", [
    (b"not a midi file", "unreadable MIDI file"),
    (b"", "without playable notes"),
])
def test_text_to_midi_rejects_invalid_or_silent_output(monkeypatch, tmp_path: Path, content, expected):
    import mido
    from types import SimpleNamespace

    output = tmp_path / "output"
    output.mkdir()
    monkeypatch.setattr(symbolic_models, "_require_model", lambda _: None)
    def generate(*args, **kwargs):
        destination = output / "generated.mid"
        if content:
            destination.write_bytes(content)
        else:
            mido.MidiFile().save(destination)
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(symbolic_models.subprocess, "run", generate)
    with pytest.raises(RuntimeError, match=expected):
        symbolic_models.generate_midi_llm("a sparse piano phrase", output)


def test_model_status_checks_concrete_files(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(symbolic_models, "MIDI_LLM_ROOT", tmp_path / "code")
    monkeypatch.setattr(symbolic_models, "MIDI_LLM_MODEL", tmp_path / "model")
    monkeypatch.setattr(symbolic_models, "MIDI_GPT_MODEL", tmp_path / "gpt.safetensors")
    assert symbolic_models.model_status()["midi_llm"]["ready"] is False
    assert symbolic_models.model_status()["midi_gpt"]["ready"] is False
