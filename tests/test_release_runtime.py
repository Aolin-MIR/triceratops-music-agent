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
    prepared = vst_service._prepare_reaper_import("import_midi_file", "C:\\music\\test.mid")
    result = vst_service._trigger_reaper_import("import_midi_file", "C:\\music\\test.mid")
    script = Path(prepared["script_path"]).read_text()
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


@pytest.mark.skipif(os.name == "nt", reason="POSIX inherited signal dispositions")
def test_backend_restores_sigterm_from_host_ignored_disposition(tmp_path):
    import subprocess
    import sys
    config = tmp_path / "runtime.json"
    config.write_text(json.dumps(dict(python=sys.executable, runs_dir=str(tmp_path / "runs"),
        model_home=str(tmp_path / "models"), reaper="/unused/reaper", device="cpu")))
    code = """
import signal, sys, runpy, os
from text2music.agent import runtime
signal.signal(signal.SIGTERM, signal.SIG_IGN)
def service(*args, **kwargs):
    os.kill(os.getpid(), signal.SIGTERM)
    raise RuntimeError('SIGTERM was still ignored')
runtime.runpy.run_module = service
sys.argv = ['runtime', '--config', sys.argv[1]]
runtime.main()
"""
    result = subprocess.run([sys.executable, "-c", code, str(config)], capture_output=True, timeout=10)
    import signal
    assert result.returncode == -signal.SIGTERM, result.stderr.decode()


def test_mac_command_line_import_is_rejected_instead_of_starting_another_host(monkeypatch):
    monkeypatch.setattr(vst_service.sys, "platform", "darwin")
    with pytest.raises(RuntimeError, match="in-host REAPER API"):
        vst_service._reaper_import_argv("/Applications/REAPER.app/Contents/MacOS/REAPER", Path("/tmp/import.lua"))


def test_windows_import_retains_nonewinst_and_native_paths(monkeypatch):
    monkeypatch.setattr(vst_service.sys, "platform", "win32")
    script = Path("C:/music/Triceratops - Import.lua")
    assert vst_service._reaper_import_argv("C:/REAPER/reaper.exe", script) == [
        "C:/REAPER/reaper.exe", "-nonewinst", "C:\\music\\Triceratops - Import.lua"]


def test_import_receipt_rejects_stale_success_and_reports_actual_project(tmp_path, monkeypatch):
    monkeypatch.setattr(vst_service, "RUNS_DIR", tmp_path)
    old_id, new_id = "a" * 32, "b" * 32
    directory = vst_service._import_request_dir(new_id)
    directory.mkdir(parents=True)
    receipt = directory / "reaper-import-result.txt"
    receipt.write_text(f"REQUEST_ID: {old_id}\nIMPORTED: 1\nPROJECT: /old.rpp\nERROR: \n")
    assert vst_service._read_import_receipt(new_id) is None
    receipt.write_text(f"REQUEST_ID: {new_id}\nIMPORTED: 1\nPROJECT: /current.rpp\nERROR: \n")
    result = vst_service._read_import_receipt(new_id)
    assert result["ok"] and result["project_path"] == "/current.rpp"
    receipt.write_text(f"REQUEST_ID: {new_id}\nIMPORTED: 0\nERROR: Cannot load media\n")
    assert not vst_service._read_import_receipt(new_id)["ok"]
    with pytest.raises(ValueError, match="identifier"):
        vst_service._read_import_receipt("../another-file")


def test_unavailable_host_does_not_leave_a_new_command_for_another_consumer(tmp_path, monkeypatch):
    monkeypatch.setattr(vst_service, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(vst_service, "_find_reaper_executable", lambda: "")
    result = vst_service._trigger_reaper_import("import_midi_file", "/missing.mid")
    assert not result["triggered"]
    assert not (tmp_path / "reaper-command.txt").exists()


def test_concurrent_imports_keep_private_commands_scripts_and_receipts(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    monkeypatch.setattr(vst_service, "RUNS_DIR", tmp_path)
    # A legacy panel must never claim or lose any VST request.
    sentinel = tmp_path / "reaper-command.txt"
    sentinel.write_text("legacy-panel-owned command")
    paths = [f"/project-{index}/genuine-output.mid" for index in range(12)]
    with ThreadPoolExecutor(max_workers=6) as pool:
        prepared = list(pool.map(lambda path: vst_service._prepare_reaper_import("import_midi_file", path), paths))
    assert len({item["request_id"] for item in prepared}) == len(paths)
    for path, item in zip(paths, prepared):
        script = Path(item["script_path"])
        command = (script.parent / "reaper-command.txt").read_text()
        assert f"FILES: {path}\n" in command
        assert f"REQUEST_ID: {item['request_id']}\n" in command
        assert str(script.parent) in script.read_text()
        receipt = script.parent / "reaper-import-result.txt"
        receipt.write_text(f"REQUEST_ID: {item['request_id']}\nIMPORTED: 1\nPROJECT: {path}.rpp\nERROR: \n")
    # Other requests' receipts cannot replace this request's target or count.
    for path, item in zip(paths, prepared):
        assert vst_service._read_import_receipt(item["request_id"])["project_path"] == path + ".rpp"
    assert sentinel.read_text() == "legacy-panel-owned command"


def test_abandoning_one_pending_import_preserves_other_requests_and_completed_receipts(tmp_path, monkeypatch):
    monkeypatch.setattr(vst_service, "RUNS_DIR", tmp_path)
    first = vst_service._prepare_reaper_import("import_midi_file", "/one.mid")
    second = vst_service._prepare_reaper_import("import_midi_file", "/two.mid")
    first_dir = Path(first["script_path"]).parent
    second_dir = Path(second["script_path"]).parent
    discarded = vst_service._discard_reaper_import(first["request_id"])
    assert not discarded["ok"] and discarded["imported"] == 0
    assert not Path(first["script_path"]).exists()
    assert not (first_dir / "reaper-command.txt").exists()
    assert (first_dir / "abandoned.txt").is_file()
    assert Path(second["script_path"]).is_file()
    assert (second_dir / "reaper-command.txt").is_file()
    receipt = second_dir / "reaper-import-result.txt"
    receipt.write_text(f"REQUEST_ID: {second['request_id']}\nIMPORTED: 1\nPROJECT: /two.rpp\nERROR: \n")
    before = receipt.read_bytes()
    assert vst_service._discard_reaper_import(second["request_id"])["ok"]
    assert receipt.read_bytes() == before


def test_abandon_does_not_claim_an_already_executing_import_was_cancelled(tmp_path, monkeypatch):
    monkeypatch.setattr(vst_service, "RUNS_DIR", tmp_path)
    prepared = vst_service._prepare_reaper_import("import_midi_file", "/one.mid")
    directory = Path(prepared["script_path"]).parent
    (directory / "reaper-command.txt").rename(directory / "reaper-command.txt.taken")
    with pytest.raises(RuntimeError, match="already claimed"):
        vst_service._discard_reaper_import(prepared["request_id"])
    assert Path(prepared["script_path"]).is_file()


def test_windows_cli_dispatches_the_prepared_request_script_not_a_shared_script(tmp_path, monkeypatch):
    monkeypatch.setattr(vst_service, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(vst_service.sys, "platform", "win32")
    monkeypatch.setattr(vst_service, "_find_reaper_executable", lambda: "reaper.exe")
    calls = []
    def dispatch_fixture(argv, **kwargs):
        # Unit-only host receipt fixture, never included in functional evidence.
        calls.append(argv)
        directory = Path(argv[-1]).parent
        request_id = directory.name
        (directory / "reaper-import-result.txt").write_text(
            f"REQUEST_ID: {request_id}\nIMPORTED: 1\nPROJECT: test-fixture.rpp\nERROR: \n")
    monkeypatch.setattr(vst_service.subprocess, "Popen", dispatch_fixture)
    result = vst_service._trigger_reaper_import("import_midi_file", "/unit-fixture.mid")
    assert result["triggered"] and result["imported"] == 1
    assert calls[0][:2] == ["reaper.exe", "-nonewinst"]
    assert Path(calls[0][-1]).parent == vst_service._import_request_dir(result["request_id"])
    assert not (tmp_path / "reaper-command.txt").exists()


def test_idle_timeout_does_not_claim_gpu_or_verified_model_release(tmp_path, monkeypatch):
    state = vst_service.TriceratopsState()
    clock = {"now": 0.0}
    monkeypatch.setattr(vst_service.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(vst_service.time, "sleep", lambda seconds: clock.update(now=clock["now"] + seconds))
    monkeypatch.setenv("TRICERATOPS_GPU_IDLE_SECONDS", "5")
    monkeypatch.setattr(vst_service, "SHUTDOWN", tmp_path / "worker" / "shutdown")
    monkeypatch.setattr(vst_service, "STATUS", tmp_path / "status.txt")
    state.last_activity = -10
    state.stop_when_unused()
    assert vst_service.SHUTDOWN.read_text() == "idle timeout\n"
    status = vst_service._read_status()
    assert status["state"] == "ready" and status["detail"] == "Service ready"


def test_editor_reopening_during_idle_wait_prevents_shutdown_and_status_overwrite(tmp_path, monkeypatch):
    state = vst_service.TriceratopsState()
    clock = {"now": 0.0}
    def reopen_during_wait(seconds):
        clock["now"] += seconds
        state.sessions["reopened-real-editor-unit-fixture"] = clock["now"]
    monkeypatch.setattr(vst_service.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(vst_service.time, "sleep", reopen_during_wait)
    monkeypatch.setenv("TRICERATOPS_GPU_IDLE_SECONDS", "5")
    monkeypatch.setattr(vst_service, "SHUTDOWN", tmp_path / "worker" / "shutdown")
    monkeypatch.setattr(vst_service, "STATUS", tmp_path / "status.txt")
    vst_service._write_status("ready", "0", "existing editor status")
    state.last_activity = -10
    state.stop_when_unused()
    assert not vst_service.SHUTDOWN.exists()
    assert vst_service._read_status()["detail"] == "existing editor status"
