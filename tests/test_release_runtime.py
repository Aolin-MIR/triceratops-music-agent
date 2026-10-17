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


def test_release_payload_includes_optional_audio_units_and_only_allowlisted_backend(tmp_path):
    import importlib.util
    script = Path(__file__).parents[1] / "vst3/installer/package_release.py"
    spec = importlib.util.spec_from_file_location("package_release", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Bundle markers test packaging only; real AU validation is recorded separately.
    vst = tmp_path / "Triceratops.vst3"
    vst.mkdir()
    units = []
    for name in ("Triceratops MIDI.component", "Triceratops Audio.component"):
        unit = tmp_path / name
        unit.mkdir()
        (unit / "bundle-marker").write_text(name)
        units.append(unit)
    output = tmp_path / "release"
    module.package(vst, output, "macos", au_plugins=units)
    for unit in units:
        assert (output / unit.name / "bundle-marker").read_text() == unit.name
    assert (output / "configure_macos.py").is_file()
    assert not list(output.rglob("runtime.json"))
    assert not list(output.rglob("*.safetensors"))
    assert set(path.name for path in (output / "backend/text2music/agent").glob("*.py")) == set(module.AGENT_MODULES)
    with pytest.raises(ValueError, match="Invalid macOS Audio Unit"):
        module.package(vst, tmp_path / "windows", "windows", au_plugins=units)
    assert not (tmp_path / "windows").exists()


def test_logic_only_mac_install_does_not_require_reaper(tmp_path, monkeypatch):
    from text2music.agent import doctor
    logic = tmp_path / "Logic Pro"
    logic.touch()
    settings = {"logic": str(logic), "reaper": str(tmp_path / "absent-REAPER")}
    monkeypatch.setattr(doctor.sys, "platform", "darwin")
    assert doctor.available_hosts(settings) == ["Logic Pro"]
    monkeypatch.setattr(doctor.sys, "platform", "win32")
    assert doctor.available_hosts(settings) == []
