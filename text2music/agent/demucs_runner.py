"""Use the installed HTDemucs snapshot, without a runtime network fallback."""
from __future__ import annotations
import os


def load_pinned_model(name="hf://htdemucs", repo=None):
    if name != "hf://htdemucs" or repo is not None:
        raise ValueError("Triceratops 0.9 uses the pinned HTDemucs model")
    import yaml
    from huggingface_hub import hf_hub_download
    from demucs.apply import BagOfModels
    from demucs.hf import load_safetensors_model
    from text2music.agent.download_models import DEMUCS_REVISION, DEMUCS_SHA256, sha256
    from pathlib import Path
    def local(filename):
        return hf_hub_download("adefossez/HTDemucs", filename, revision=DEMUCS_REVISION,
                               local_files_only=True)
    with open(local("htdemucs.yaml"), encoding="utf-8") as stream:
        bag = yaml.safe_load(stream)
    if sha256(Path(local("955717e8.safetensors"))) != DEMUCS_SHA256:
        raise RuntimeError("HTDemucs model checksum mismatch")
    models = [load_safetensors_model(local(f"{signature}.safetensors")) for signature in bag["models"]]
    model = BagOfModels(models, bag.get("weights"), bag.get("segment"))
    model.eval()
    return model


def main():
    import torch
    import demucs.api
    import demucs.separate
    if os.environ.get("TRICERATOPS_DEVICE", "cpu") == "cpu":
        torch.set_num_threads(int(os.environ.get("TRICERATOPS_CPU_THREADS", "8")))
    demucs.api.get_model = load_pinned_model
    demucs.separate.main()


if __name__ == "__main__":
    main()
