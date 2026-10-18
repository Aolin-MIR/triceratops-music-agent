"""Run the pinned upstream decoder with an explicitly configured Torch device."""
from __future__ import annotations
import os
import json
import runpy
import sys
import time
from pathlib import Path


def main():
    import torch
    from transformers import AutoModelForCausalLM
    from text2music.agent.symbolic_models import MIDI_LLM_ROOT
    sys.path.insert(0, str(MIDI_LLM_ROOT))
    namespace = runpy.run_path(str(MIDI_LLM_ROOT / "generate_transformers.py"))
    device = os.environ.get("TRICERATOPS_MIDI_LLM_DEVICE", os.environ.get("TRICERATOPS_DEVICE", "cuda"))
    if device not in {"cpu", "cuda", "mps"}:
        raise ValueError("TRICERATOPS_DEVICE must be cpu, cuda or mps")
    def load(model_path):
        started = time.monotonic()
        if device == "cpu":
            torch.set_num_threads(int(os.environ.get("TRICERATOPS_CPU_THREADS", "8")))
        precision = os.environ.get("TRICERATOPS_MIDI_LLM_DTYPE", "default")
        if precision not in {"default", "float32", "float16", "bfloat16"}:
            raise ValueError("MIDI-LLM dtype must be default, float32, float16 or bfloat16")
        dtype = (torch.bfloat16 if device == "cuda" else torch.float32) if precision == "default" else getattr(torch, precision)
        model = AutoModelForCausalLM.from_pretrained(
            model_path, dtype=dtype, local_files_only=True, trust_remote_code=False
        ).to(device).eval()
        actual = str(next(model.parameters()).device)
        if actual.split(":")[0] != device:
            raise RuntimeError(f"Requested {device}, but MIDI-LLM loaded on {actual}")
        if "--output_root" in sys.argv:
            output = Path(sys.argv[sys.argv.index("--output_root") + 1])
            output.mkdir(parents=True, exist_ok=True)
            (output / "runtime-device.json").write_text(json.dumps({
                "requested_device": device, "actual_device": actual,
                "dtype": str(next(model.parameters()).dtype),
                "cpu_threads": torch.get_num_threads(),
                "load_seconds": round(time.monotonic() - started, 3),
            }), encoding="utf-8")
        return model
    # Upstream main resolves globals in its own function dictionary.
    namespace["main"].__globals__["prepare_hf_model"] = load
    namespace["main"]()


if __name__ == "__main__":
    main()
