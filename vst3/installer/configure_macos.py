"""Merge user settings without replacing existing paths, devices or credentials."""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys
import tempfile
import time


def write_config(data: Path, python: Path, api_key: str = "") -> dict:
    data.mkdir(parents=True, exist_ok=True)
    config = data / "runtime.json"
    settings = json.loads(config.read_text(encoding="utf-8")) if config.exists() else {}
    if not isinstance(settings, dict):
        raise ValueError("runtime.json must contain an object")
    defaults = dict(python=str(python), runs_dir=str(data / "runs"), model_home=str(data / "models"),
                    reaper="/Applications/REAPER.app/Contents/MacOS/REAPER",
                    logic="/Applications/Logic Pro.app/Contents/MacOS/Logic Pro", device="auto",
                    model_policy="auto", midi_llm_device="auto", midi_gpt_device="auto",
                    midi_llm_dtype="auto", audio_device="cpu", chat_deployment="remote",
                    local_chat_available=False, local_chat_model="Qwen3.5-4B",
                    local_chat_base_url="http://127.0.0.1:8000/v1",
                    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1", chat_model="qwen-plus")
    for key, value in defaults.items():
        settings.setdefault(key, value)
    from text2music.agent.macos_bootstrap import OLLAMA_VERSION
    settings.setdefault('ollama_runtime', str(data / 'runtimes' / ('ollama-' + OLLAMA_VERSION)))
    settings.setdefault('runtime_download_source', os.environ.get('TRICERATOPS_DOWNLOAD_SOURCE', 'auto'))
    settings.setdefault('model_source', os.environ.get('TRICERATOPS_DOWNLOAD_SOURCE', 'auto'))
    if api_key:
        settings["api_key"] = api_key
    if config.exists():
        backup = data / f"runtime.backup-{time.time_ns()}.json"
        descriptor = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(config.read_bytes())
    descriptor, temporary = tempfile.mkstemp(prefix=".runtime-", dir=data)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(settings, stream, indent=2)
            stream.write("\n")
        os.replace(temporary, config)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()
    config.chmod(0o600)
    return settings


if __name__ == "__main__":
    write_config(Path(sys.argv[1]), Path(sys.argv[2]), os.environ.get("TRICERATOPS_SETUP_KEY", ""))
