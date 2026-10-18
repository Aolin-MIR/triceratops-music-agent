"""Fail setup explicitly when dependencies, models, or device are not usable."""
from __future__ import annotations
import argparse
import importlib
from pathlib import Path
from text2music.agent.runtime import configure


def check(config: Path, *, check_chat: bool = True) -> None:
    settings = configure(config)
    import torch
    for name in ("transformers", "accelerate", "openai", "mido", "music21", "librosa",
                 "soundfile", "jsonschema", "demucs", "sphn", "basic_pitch", "onnxruntime", "midigpt", "anticipation"):
        importlib.import_module(name)
        print(f"Import OK: {name}", flush=True)
    if not Path(settings["reaper"]).is_file():
        raise RuntimeError("Configured REAPER executable is missing")
    devices = {settings["device"], *(settings.get(name, settings["device"]) for name in ("midi_llm_device", "midi_gpt_device", "stem_device"))}
    if "cuda" in devices and not torch.cuda.is_available():
        raise RuntimeError("CUDA was selected but Torch cannot use your NVIDIA GPU; update the driver or explicitly select CPU")
    if settings.get("midi_llm_device", settings["device"]) == "cuda" and not torch.cuda.is_bf16_supported():
        raise RuntimeError("MIDI-LLM CUDA generation requires BF16 support on the selected GPU")
    if "mps" in devices and not torch.backends.mps.is_available():
        raise RuntimeError("MPS was selected but is not available")
    from text2music.agent.download_models import verify
    verify(Path(settings["model_home"]))
    from text2music.agent.symbolic_models import model_status
    for name, status in model_status().items():
        if not status["ready"]:
            raise RuntimeError(f"{name}: incomplete model or decoder source")
    from basic_pitch import FilenameSuffix, build_icassp_2022_model_path
    from text2music.agent.demucs_runner import load_pinned_model
    load_pinned_model()
    import onnxruntime
    onnxruntime.InferenceSession(str(build_icassp_2022_model_path(FilenameSuffix.onnx)),
                                providers=["CPUExecutionProvider"])
    from text2music.agent.llm_backend import check_chat_backend
    if check_chat:
        report = check_chat_backend()
        import json
        print("Chat compatibility: " + json.dumps(report), flush=True)
    print("Runtime, model checksums and Basic Pitch ONNX session OK", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    check(parser.parse_args().config)
