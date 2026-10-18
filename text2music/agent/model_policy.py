"""Hardware-aware model deployment policy.

The policy is deliberately conservative: it chooses only device paths that
have been validated for the model on the current release.  Users can opt out
with explicit per-model settings in ``runtime.json``; an unavailable explicit
device is rejected by the doctor rather than silently changed.
"""
from __future__ import annotations

import platform
import subprocess
from typing import Any


VALID_DEVICES = {"cpu", "cuda", "mps"}
VALID_POLICIES = {"auto", "custom"}
VALID_CHAT_DEPLOYMENTS = {"remote", "local-openai"}
VALID_DTYPES = {"default", "float32", "float16", "bfloat16"}


def _sysctl(name: str) -> str:
    if platform.system() != "Darwin":
        return ""
    try:
        result = subprocess.run(["/usr/sbin/sysctl", "-n", name], capture_output=True,
                                text=True, timeout=2, check=True)
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip()


def detect_hardware() -> dict[str, Any]:
    """Return a small, non-sensitive hardware description for policy choices."""
    memory = _sysctl("hw.memsize")
    memory_gb = int(memory) / (1024 ** 3) if memory.isdigit() else 0.0
    arch = platform.machine()
    chip = _sysctl("machdep.cpu.brand_string") or _sysctl("hw.model")
    if platform.system() != "Darwin":
        profile = "generic"
    elif arch == "arm64" and memory_gb <= 0:
        profile = "mac-memory-unknown"
    elif arch == "arm64" and memory_gb <= 8.5:
        profile = "mac-low-memory"
    elif arch == "arm64" and memory_gb < 24:
        profile = "mac-balanced"
    elif arch == "arm64":
        profile = "mac-high-memory"
    else:
        profile = "mac-intel-or-unknown"
    return {
        "platform": platform.system(),
        "architecture": arch,
        "chip": chip,
        "unified_memory_gb": round(memory_gb, 2),
        "profile": profile,
    }


def _auto_policy(hardware: dict[str, Any]) -> dict[str, str]:
    """Choose model-specific defaults from tested, conservative paths."""
    profile = hardware["profile"]
    # Precision and device are separate decisions. The tested 8 GB Mac needs
    # FP16; other Mac profiles keep the runner's original device precision
    # (CPU=float32). Missing memory information never implies a low-end Mac.
    # Preserve the existing non-Mac policy; Windows setup pins its own dtype.
    mac_profile = profile.startswith("mac-")
    precision = "float16" if not mac_profile or profile == "mac-low-memory" else "default"
    # MPS stays opt-in until a model-specific device/operator test passes.
    result = {
        "midi_llm_device": "cpu",
        "midi_llm_dtype": precision,
        "midi_gpt_device": "cpu",
        "audio_device": "cpu",
        "chat_deployment": "remote",
    }
    if profile in {"generic", "mac-intel-or-unknown"}:
        result["midi_gpt_device"] = "cpu"
    return result


def resolve_policy(config: dict[str, Any], hardware: dict[str, Any] | None = None) -> dict[str, Any]:
    """Resolve auto/custom settings without mutating the user's config."""
    policy = config.get("model_policy", "auto")
    if policy not in VALID_POLICIES:
        raise ValueError("model_policy must be auto or custom")
    hardware = hardware or detect_hardware()
    if policy == "auto":
        resolved = _auto_policy(hardware)
    else:
        # ``auto`` is a useful per-model placeholder in the installer-generated
        # file.  Custom mode only replaces the fields the user actually pins.
        resolved = _auto_policy(hardware)
        for key in ("midi_llm_device", "midi_llm_dtype", "midi_gpt_device", "audio_device"):
            value = config.get(key)
            if value is not None and value != "auto":
                resolved[key] = value
        if config.get("chat_deployment") not in (None, "auto"):
            resolved["chat_deployment"] = config["chat_deployment"]
    # A local Qwen 4B service is selected only when setup has explicitly
    # verified an OpenAI-compatible endpoint.  This lets Windows 1.0 provide
    # its local deployment without forcing it onto an 8 GB Mac.
    if policy == "auto" and config.get("local_chat_available") is True:
        resolved["chat_deployment"] = "local-openai"
    # Legacy explicit ``device`` remains an override for both symbolic models.
    if policy == "custom" and config.get("device") in VALID_DEVICES:
        resolved["midi_llm_device"] = config["device"]
        gpt_override = config.get("midi_gpt_device")
        resolved["midi_gpt_device"] = config["device"] if gpt_override in (None, "auto") else gpt_override
    for key in ("midi_llm_device", "midi_gpt_device", "audio_device"):
        if resolved[key] not in VALID_DEVICES:
            raise ValueError(f"{key} must be cpu, cuda or mps")
    if resolved["midi_llm_dtype"] not in VALID_DTYPES:
        raise ValueError("midi_llm_dtype must be default, float32, float16 or bfloat16")
    if resolved["chat_deployment"] not in VALID_CHAT_DEPLOYMENTS:
        raise ValueError("chat_deployment must be remote or local-openai")
    return {"hardware": hardware, "policy": policy, **resolved}


def precision_status(config: dict[str, Any], hardware: dict[str, Any] | None = None) -> dict[str, Any]:
    """Expose the automatic decision separately from an intentional override."""
    resolved = resolve_policy(config, hardware)
    requested = config.get("midi_llm_dtype", "auto")
    if requested not in VALID_DTYPES | {"auto"}:
        raise ValueError("Invalid MIDI-LLM dtype")
    automatic = requested == "auto"
    dtype = resolved["midi_llm_dtype"] if automatic else requested
    reduced = automatic and resolved["hardware"]["profile"] == "mac-low-memory"
    return {"requested": requested, "resolved": dtype,
            "hardware_profile": resolved["hardware"]["profile"],
            "reason": "auto-low-memory" if reduced else "auto-original" if automatic else "manual"}

