from pathlib import Path
import sys

from text2music.agent import service


def test_windows_music_generation_uses_bundled_python_without_wsl(monkeypatch, tmp_path):
    monkeypatch.setattr(service, "_use_warm_worker_queue", lambda: False)
    plan = tmp_path / "plan.txt"
    output = tmp_path / "output"

    command = service._generation_command(plan, output)

    assert command == [sys.executable, "inference.py", "--plan_path", str(plan),
                       "--output_folder", str(output)]
    assert all("wsl" not in part.lower() and "/mnt/" not in part for part in command)
    assert service._use_warm_worker_queue() is False
