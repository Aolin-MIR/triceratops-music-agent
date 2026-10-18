"""Load a user-owned installation configuration before importing the service."""
from __future__ import annotations
import argparse
import json
import os
import runpy
import sys
import signal
from pathlib import Path

# Hosts launch this file by absolute path with no project PYTHONPATH.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from text2music.agent.model_policy import resolve_policy, VALID_DEVICES, VALID_DTYPES


def configure(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    for name in ("python", "runs_dir", "model_home", "reaper", "device"):
        if not isinstance(config.get(name), str) or not config[name].strip():
            raise ValueError(f"Missing runtime configuration: {name}")
    if config["device"] not in VALID_DEVICES | {"auto"}:
        raise ValueError("device must be cpu, cuda, mps or auto")
    resolved = resolve_policy(config)
    for name in ("midi_llm_device", "midi_gpt_device"):
        explicit = config.get(name, config["device"])
        if explicit != "auto":
            if explicit not in VALID_DEVICES:
                raise ValueError(f"{name} must be cpu, cuda, mps or auto")
            resolved[name] = explicit
    audio = config.get("stem_device", config.get("audio_device", config["device"]))
    if audio != "auto":
        if audio not in VALID_DEVICES:
            raise ValueError("stem_device must be cpu, cuda, mps or auto")
        resolved["audio_device"] = audio
    # A saved CPU device must not bypass the Mac low-memory precision policy.
    precision_default = "auto" if sys.platform == "darwin" else "default" if config["device"] != "auto" else "auto"
    precision = config.get("midi_llm_dtype", precision_default)
    if precision not in VALID_DTYPES | {"auto"}:
        raise ValueError("Invalid MIDI-LLM dtype")
    if precision != "auto":
        resolved["midi_llm_dtype"] = precision
    config = dict(config)
    config["resolved_model_policy"] = resolved
    if resolved["chat_deployment"] == "local-openai" and "llm_provider" not in config:
        config.update(llm_provider="remote", api_key=config.get("local_chat_api_key", "local"),
                      base_url=config.get("local_chat_base_url", "http://127.0.0.1:8000/v1"),
                      chat_model=config.get("local_chat_model", "Qwen3.5-4B"))
    root = Path(__file__).resolve().parents[2]
    extra = config.get("extra_python_paths", [])
    sys.path[:0] = [str(root), *extra]
    os.environ["PYTHONPATH"] = os.pathsep.join([str(root), *extra])
    model_home = Path(config["model_home"])
    os.environ.update({
        "PYTHONUTF8": "1", "TRICERATOPS_CONFIG": str(path.resolve()),
        "TRICERATOPS_MUSIC_PYTHON": config["python"], "TRICERATOPS_RUNS_DIR": config["runs_dir"],
        "MIDI_LLM_ROOT": str(model_home / "MIDI-LLM-code"),
        "MIDI_LLM_MODEL": str(model_home / "midi-llm"),
        "MIDI_GPT_MODEL": str(model_home / "midi-gpt" / "yellow_medium-final.safetensors"),
        "TRICERATOPS_MIDI_LLM_DEVICE": resolved["midi_llm_device"],
        "TRICERATOPS_MIDI_GPT_DEVICE": resolved["midi_gpt_device"],
        "TRICERATOPS_STEM_DEVICE": resolved["audio_device"],
        "TRICERATOPS_REAPER": config["reaper"], "TRICERATOPS_DEVICE": resolved["midi_llm_device"],
        "TRICERATOPS_AUDIO_DEVICE": resolved["audio_device"],
        "TRICERATOPS_MIDI_LLM_DTYPE": resolved["midi_llm_dtype"],
        "TRICERATOPS_CHAT_DEPLOYMENT": resolved["chat_deployment"],
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
    if os.name != "nt":
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        signal.signal(signal.SIGINT, signal.SIG_DFL)
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    configure(args.config)
    runpy.run_module("text2music.agent.vst_service", run_name="__main__")


if __name__ == "__main__":
    main()
