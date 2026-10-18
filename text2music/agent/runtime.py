"""Load a user-owned installation configuration before importing the service."""
from __future__ import annotations
import argparse
import json
import os
import runpy
import sys
from pathlib import Path


def configure(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    for name in ("python", "runs_dir", "model_home", "reaper", "device"):
        if not isinstance(config.get(name), str) or not config[name].strip():
            raise ValueError(f"Missing runtime configuration: {name}")
    if config["device"] not in {"cpu", "cuda", "mps"}:
        raise ValueError("device must be cpu, cuda or mps")
    for name in ("midi_llm_device", "midi_gpt_device", "stem_device"):
        if config.get(name, config["device"]) not in {"cpu", "cuda", "mps"}:
            raise ValueError(f"{name} must be cpu, cuda or mps")
    root = Path(__file__).resolve().parents[2]
    extra = config.get("extra_python_paths", [])
    sys.path[:0] = [str(root), *extra]
    os.environ["PYTHONPATH"] = os.pathsep.join([str(root), *extra])
    model_home = Path(config["model_home"])
    os.environ.update({
        "PYTHONUTF8": "1", "TRICERATOPS_CONFIG": str(path.resolve()),
        "TEXT2SCORE_PYTHON": config["python"], "TEXT2SCORE_RUNS_DIR": config["runs_dir"],
        "MIDI_LLM_ROOT": str(model_home / "MIDI-LLM-code"),
        "MIDI_LLM_MODEL": str(model_home / "midi-llm"),
        "MIDI_GPT_MODEL": str(model_home / "midi-gpt" / "yellow_medium-final.safetensors"),
        "TRICERATOPS_MIDI_LLM_DEVICE": config.get("midi_llm_device", config["device"]),
        "TRICERATOPS_MIDI_GPT_DEVICE": config.get("midi_gpt_device", config["device"]),
        "TRICERATOPS_STEM_DEVICE": config.get("stem_device", config["device"]),
        "TRICERATOPS_REAPER": config["reaper"], "TRICERATOPS_DEVICE": config["device"],
        "HF_ENDPOINT": config.get("hf_endpoint", "https://hf-mirror.com"),
        "TRICERATOPS_LLM_PROVIDER": config.get("llm_provider", "remote"),
        "TRICERATOPS_LLM_DEVICE": config.get("llm_device", "gpu" if config.get("llm_provider") in {"ollama", "llama_cpp"} else "cpu"),
        "TRICERATOPS_OLLAMA_URL": "http://127.0.0.1:11435",
        "TRICERATOPS_LLAMA_CPP_URL": config.get("llama_cpp_url", "http://127.0.0.1:1234/v1"),
        "TRICERATOPS_LOCAL_MODEL": config.get("local_model", "qwen3.5:4b-q4_K_M"),
        "TRICERATOPS_LLM_TIMEOUT": str(config.get("llm_timeout", 180 if config.get("llm_provider") in {"ollama", "llama_cpp"} else 60)),
        "TRICERATOPS_LLM_CONTEXT": str(config.get("llm_context", 8192)),
        "QWEN_API_KEY": config.get("api_key", ""),
        "QWEN_BASE_URL": config.get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        "QWEN_MODEL": config.get("chat_model", "qwen-plus"),
    })
    if config.get("gpu_index") is not None:
        os.environ["CUDA_VISIBLE_DEVICES"] = str(config["gpu_index"])
    from text2music.agent.llm_backend import ChatSettings
    ChatSettings.load()  # Reject invalid modes/devices before starting the service.
    return config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    configure(args.config)
    runpy.run_module("text2music.agent.vst_service", run_name="__main__")


if __name__ == "__main__":
    main()
