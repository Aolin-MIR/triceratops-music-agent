import importlib.util
import os
from pathlib import Path
import subprocess
import sys

from text2music.agent import process_entry


def test_module_launch_survives_isolated_python_and_relocated_unicode_path(tmp_path):
    root = tmp_path / "安装 with spaces"
    package = root / "text2music" / "agent"
    package.mkdir(parents=True)
    (package.parent / "__init__.py").touch()
    (package / "__init__.py").touch()
    (package / "sibling.py").write_text("VALUE = 'package import succeeded'\n")
    (package / "probe.py").write_text(
        "import sys\nfrom .sibling import VALUE\nprint(VALUE, sys.argv[1])\n")
    entry = package / "process_entry.py"
    entry.write_bytes(Path(process_entry.__file__).read_bytes())
    spec = importlib.util.spec_from_file_location("relocated_entry", entry)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    command = module.python_module_command("text2music.agent.probe", "argument with spaces")
    command.insert(1, "-I")
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True,
                            env={**os.environ, "PYTHONPATH": ""}, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "package import succeeded argument with spaces"
    assert command[0] == sys.executable

def test_module_launch_retains_selected_private_runtime_paths(tmp_path, monkeypatch):
    private = tmp_path / "private torch runtime"
    private.mkdir()
    (private / "selected_runtime_probe.py").write_text("VALUE = 'private runtime retained'\n")
    monkeypatch.setenv("PYTHONPATH", str(private))
    command = process_entry.python_module_command("selected_runtime_probe")
    command.insert(1, "-I")
    (private / "selected_runtime_probe.py").write_text("print('private runtime retained')\n")
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "private runtime retained"
