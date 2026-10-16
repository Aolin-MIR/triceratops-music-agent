"""Run the pinned upstream decoder with an explicitly configured Torch device."""
from __future__ import annotations
import os
import runpy
import sys
from pathlib import Path


def main():
    import torch
    from transformers import AutoModelForCausalLM
    from text2music.agent.symbolic_models import MIDI_LLM_ROOT
    sys.path.insert(0, str(MIDI_LLM_ROOT))
    namespace = runpy.run_path(str(MIDI_LLM_ROOT / "generate_transformers.py"))
    device = os.environ.get("TRICERATOPS_DEVICE", "cuda")
    if device not in {"cpu", "cuda", "mps"}:
        raise ValueError("TRICERATOPS_DEVICE must be cpu, cuda or mps")
    def load(model_path):
        if device == "cpu":
            torch.set_num_threads(int(os.environ.get("TRICERATOPS_CPU_THREADS", "8")))
        dtype = torch.bfloat16 if device == "cuda" else torch.float32
        return AutoModelForCausalLM.from_pretrained(
            model_path, dtype=dtype, local_files_only=True, trust_remote_code=False
        ).to(device).eval()
    # Upstream main resolves globals in its own function dictionary.
    namespace["main"].__globals__["prepare_hf_model"] = load
    namespace["main"]()


if __name__ == "__main__":
    main()
