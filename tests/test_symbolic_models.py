from pathlib import Path

import pytest

from text2music.agent import symbolic_models
from text2music.agent.tool_loop import tool_schemas


def test_symbolic_tool_schemas_expose_real_backends():
    functions = {item["function"]["name"]: item["function"] for item in tool_schemas()}
    assert functions["generate_draft"]["parameters"]["properties"]["backend"]["enum"] == [
        "auto", "midi_llm", "text2score"
    ]
    assert functions["infill_midi"]["parameters"]["properties"]["bar_ids"]["minItems"] == 1


def test_missing_model_fails_instead_of_falling_back(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(symbolic_models, "MIDI_LLM_MODEL", tmp_path / "missing")
    with pytest.raises(RuntimeError, match="not installed completely"):
        symbolic_models.generate_midi_llm("piano", tmp_path / "out")


def test_model_status_checks_concrete_files(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(symbolic_models, "MIDI_LLM_ROOT", tmp_path / "code")
    monkeypatch.setattr(symbolic_models, "MIDI_LLM_MODEL", tmp_path / "model")
    monkeypatch.setattr(symbolic_models, "MIDI_GPT_MODEL", tmp_path / "gpt.safetensors")
    assert symbolic_models.model_status()["midi_llm"]["ready"] is False
    assert symbolic_models.model_status()["midi_gpt"]["ready"] is False
