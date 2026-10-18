import json
import os
from types import SimpleNamespace
from pathlib import Path
import pytest
from text2music.agent import runtime, vst_service
from text2music.agent.download_models import verify


def test_runtime_configuration_is_relocatable_and_keeps_selected_device(tmp_path, monkeypatch):
    # Restore all environment changes after configuring this isolated profile.
    monkeypatch.setattr(os, "environ", dict(os.environ))
    monkeypatch.setattr(runtime.sys, "path", list(runtime.sys.path))
    config = tmp_path / "runtime.json"
    config.write_text(json.dumps(dict(python="/custom/python", runs_dir=str(tmp_path / "runs"),
        model_home=str(tmp_path / "models"), reaper="/custom/reaper", device="cpu", api_key="test-only")))
    runtime.configure(config)
    assert os.environ["TRICERATOPS_DEVICE"] == "cpu"
    assert os.environ["MIDI_GPT_MODEL"] == str(tmp_path / "models/midi-gpt/yellow_medium-final.safetensors")
    assert os.environ["TEXT2SCORE_RUNS_DIR"] == str(tmp_path / "runs")


def test_runtime_rejects_missing_configuration(tmp_path):
    config = tmp_path / "runtime.json"
    config.write_text('{}')
    with pytest.raises(ValueError, match="Missing runtime configuration"):
        runtime.configure(config)


def test_model_verification_rejects_incomplete_download(tmp_path):
    folder = tmp_path / "midi-llm"
    folder.mkdir()
    (folder / "model.safetensors").write_bytes(b"partial download")
    with pytest.raises(RuntimeError, match="checksum mismatch"):
        verify(tmp_path)


def test_reaper_importer_uses_configured_runs_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(vst_service, "RUNS_DIR", tmp_path / "another install")
    monkeypatch.setattr(vst_service, "_find_reaper_executable", lambda: "")
    result = vst_service._trigger_reaper_import("import_midi_file", "C:\\music\\test.mid")
    script = (vst_service.RUNS_DIR / "Triceratops - Import.lua").read_text()
    assert "local ROOT = nil" not in script
    assert "another install" in script
    assert "E:\\\\text2score" not in script
    assert result["triggered"] is False


def test_native_windows_file_path_does_not_become_a_wsl_mount(monkeypatch):
    monkeypatch.setattr(vst_service, "os", SimpleNamespace(name="nt"))
    assert str(vst_service._windows_to_wsl("C:\\Music\\clip.mid")) == "C:\\Music\\clip.mid"


def test_fixed_devices_are_configured_independently(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "environ", dict(os.environ))
    monkeypatch.setattr(runtime.sys, "path", list(runtime.sys.path))
    config = tmp_path / "runtime.json"
    config.write_text(json.dumps(dict(python="/python", runs_dir=str(tmp_path / "runs"),
        model_home=str(tmp_path / "models"), reaper="/reaper", device="cuda", api_key="",
        llm_provider="ollama", llm_device="gpu", midi_gpt_device="cpu", stem_device="cpu")))
    runtime.configure(config)
    assert os.environ["TRICERATOPS_LLM_DEVICE"] == "gpu"
    assert os.environ["TRICERATOPS_MIDI_LLM_DEVICE"] == "cuda"
    assert os.environ["TRICERATOPS_MIDI_GPT_DEVICE"] == "cpu"
    assert os.environ["TRICERATOPS_STEM_DEVICE"] == "cpu"
    assert os.environ["QWEN_API_KEY"] == ""
