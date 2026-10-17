"""Load a user-owned installation configuration before importing the service."""
from __future__ import annotations
import argparse
import json
import os
import runpy
import signal
import sys
from pathlib import Path


def configure(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    for name in ("python", "runs_dir", "model_home", "reaper", "device"):
        if not isinstance(config.get(name), str) or not config[name].strip():
            raise ValueError(f"Missing runtime configuration: {name}")
    if config["device"] not in {"cpu", "cuda", "mps"}:
        raise ValueError("device must be cpu, cuda or mps")
    precision = config.get("midi_llm_dtype", "default")
    if precision not in {"default", "float32", "float16", "bfloat16"}:
        raise ValueError("midi_llm_dtype must be default, float32, float16 or bfloat16")
    root = Path(__file__).resolve().parents[2]
    model_home = Path(config["model_home"])
    os.environ.update({
        "PYTHONUTF8": "1",
        "TEXT2SCORE_PYTHON": config["python"], "TEXT2SCORE_RUNS_DIR": config["runs_dir"],
        "MIDI_LLM_ROOT": str(model_home / "MIDI-LLM-code"),
        "MIDI_LLM_MODEL": str(model_home / "midi-llm"),
        "MIDI_GPT_MODEL": str(model_home / "midi-gpt" / "yellow_medium-final.safetensors"),
        "TRICERATOPS_REAPER": config["reaper"], "TRICERATOPS_DEVICE": config["device"],
        "TRICERATOPS_MIDI_LLM_DTYPE": precision,
        "HF_ENDPOINT": config.get("hf_endpoint", "https://hf-mirror.com"),
        "QWEN_API_KEY": config.get("api_key", ""),
        "QWEN_BASE_URL": config.get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        "QWEN_MODEL": config.get("chat_model", "qwen-plus"),
    })
    extra = config.get("extra_python_paths", [])
    sys.path[:0] = [str(root), *extra]
    os.environ["PYTHONPATH"] = os.pathsep.join([str(root), *extra])
    return config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    configure(args.config)
    # AU/VST host processes may ignore SIGTERM. Ignored dispositions survive
    # exec on POSIX; restore termination for this dedicated backend only.
    if os.name != "nt":
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
    runpy.run_module("text2music.agent.vst_service", run_name="__main__")


if __name__ == "__main__":
    main()
