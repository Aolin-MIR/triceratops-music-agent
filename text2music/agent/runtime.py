"""Load a user-owned installation configuration before importing the service."""
from __future__ import annotations
import argparse
import json
import os
import runpy
import signal
import sys
from pathlib import Path
from text2music.agent.model_policy import resolve_policy, VALID_DEVICES, VALID_DTYPES


def configure(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    for name in ("python", "runs_dir", "model_home", "reaper", "device"):
        if not isinstance(config.get(name), str) or not config[name].strip():
            raise ValueError(f"Missing runtime configuration: {name}")
    if config["device"] not in VALID_DEVICES | {"auto"}:
        raise ValueError("device must be cpu, cuda, mps or auto")
    precision = config.get("midi_llm_dtype", "default")
    if precision not in VALID_DTYPES | {"auto"}:
        raise ValueError("midi_llm_dtype must be default, float32, float16 or bfloat16")
    resolved = resolve_policy(config)
    # Explicit legacy device/dtype values take precedence over auto policy.
    if config["device"] in VALID_DEVICES:
        resolved["midi_llm_device"] = config["device"]
        gpt_override = config.get("midi_gpt_device")
        resolved["midi_gpt_device"] = config["device"] if gpt_override in (None, "auto") else gpt_override
    if precision != "auto":
        resolved["midi_llm_dtype"] = precision
    root = Path(__file__).resolve().parents[2]
    model_home = Path(config["model_home"])
    chat_deployment = resolved["chat_deployment"]
    if chat_deployment == "local-openai":
        qwen_base_url = config.get("local_chat_base_url", "http://127.0.0.1:8000/v1")
        qwen_model = config.get("local_chat_model", config.get("chat_model", "Qwen3.5-4B"))
        qwen_key = config.get("local_chat_api_key", "local")
    else:
        qwen_base_url = config.get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        qwen_model = config.get("chat_model", "qwen-plus")
        qwen_key = config.get("api_key", "")
    os.environ.update({
        "PYTHONUTF8": "1",
        "TEXT2SCORE_PYTHON": config["python"], "TEXT2SCORE_RUNS_DIR": config["runs_dir"],
        "MIDI_LLM_ROOT": str(model_home / "MIDI-LLM-code"),
        "MIDI_LLM_MODEL": str(model_home / "midi-llm"),
        "MIDI_GPT_MODEL": str(model_home / "midi-gpt" / "yellow_medium-final.safetensors"),
        "TRICERATOPS_REAPER": config["reaper"],
        "TRICERATOPS_DEVICE": resolved["midi_llm_device"],
        "TRICERATOPS_MIDI_GPT_DEVICE": resolved["midi_gpt_device"],
        "TRICERATOPS_AUDIO_DEVICE": resolved["audio_device"],
        "TRICERATOPS_MIDI_LLM_DTYPE": resolved["midi_llm_dtype"],
        "HF_ENDPOINT": config.get("hf_endpoint", "https://hf-mirror.com"),
        "QWEN_API_KEY": qwen_key,
        "QWEN_BASE_URL": qwen_base_url,
        "QWEN_MODEL": qwen_model,
        "TRICERATOPS_CHAT_DEPLOYMENT": chat_deployment,
    })
    extra = config.get("extra_python_paths", [])
    sys.path[:0] = [str(root), *extra]
    os.environ["PYTHONPATH"] = os.pathsep.join([str(root), *extra])
    config = dict(config)
    config["resolved_model_policy"] = resolved
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
