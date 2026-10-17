"""Build a clean release payload; never copy keys, runs, weights or training data."""
from __future__ import annotations
import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENT_MODULES = (
    "__init__.py", "audio_tools.py", "capabilities.py", "knowledge.py", "midi_tools.py",
    "operation_report.py", "project_memory.py", "router.py", "service.py", "symbolic_models.py",
    "tool_loop.py", "vst_service.py", "runtime.py", "doctor.py", "download_models.py", "midi_llm_runner.py", "demucs_runner.py", "model_job.py", "errors.py", "midi_merge.py", "midi_postprocess.py",
)


def package(plugin: Path, output: Path, platform: str, python_seed: Path | None = None):
    if not plugin.is_dir():
        raise FileNotFoundError(plugin)
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"Output must be empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    shutil.copytree(plugin, output / "Triceratops.vst3")
    backend = output / "backend"
    agent = backend / "text2music" / "agent"
    agent.mkdir(parents=True)
    shutil.copy2(ROOT / "text2music" / "__init__.py", agent.parent / "__init__.py")
    for name in AGENT_MODULES:
        shutil.copy2(ROOT / "text2music" / "agent" / name, agent / name)
    importer = agent / "reaper"
    importer.mkdir()
    shutil.copy2(ROOT / "text2music/agent/reaper/Triceratops - Import from Agent.lua", importer)
    shutil.copytree(ROOT / "knowledge", backend / "knowledge", ignore=shutil.ignore_patterns("__pycache__"))
    docs = output / "docs"
    docs.mkdir()
    for name in ("readme.md", "README.en.md", "NOTICE", "THIRD_PARTY_NOTICES.md", "LICENSE-TRICERATOPS.md", "AGPL-3.0.txt"):
        shutil.copy2(ROOT / name, docs / name)
    for name in ("readme.md", "README.en.md"):
        shutil.copy2(ROOT / name, backend / name)
    if platform == "windows":
        if python_seed is None:
            raise ValueError("Windows packaging requires --python-seed")
        shutil.copytree(python_seed, output / "python", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    else:
        for name in ("setup-macos.sh", "requirements-runtime.txt"):
            shutil.copy2(ROOT / "vst3/installer" / name, output / name)
        (output / "setup-macos.sh").chmod(0o755)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=("windows", "macos"), required=True)
    parser.add_argument("--plugin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--python-seed", type=Path)
    args = parser.parse_args()
    package(args.plugin, args.output, args.platform, args.python_seed)
