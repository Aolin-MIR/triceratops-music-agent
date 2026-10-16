"""Explicit, revision-pinned model installation for the desktop distribution."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path, PurePosixPath

WEIGHTS = {
    "midi-llm/model.safetensors": "7da7f50fefa027208121661c799d3bde2a7c04ad01d40a3d4a597be3fdcaf2ae",
    "midi-gpt/yellow_medium-final.safetensors": "acd856168e87c640868ac20cf7523e5912e5171506101fbaebd8eea49a7c4f7c",
}
REPOS = (
    ("slseanwu/MIDI-LLM_Llama-3.2-1B", "8b82ab9ec144348900e9ea4623b123e0b12f60b3", "midi-llm",
     ["*.json", "*.safetensors", "README.md"]),
    ("Metacreation/MIDI-GPT", "3aa5748ba68e32a43c70ddc66b5e595069484532", "midi-gpt",
     ["yellow_encoder.json", "yellow_medium-final.safetensors", "README.md"]),
)
CODE_REVISION = "93c660c7ce1e74c94a1cd8c3929b3d6f99e3039b"
DEMUCS_REVISION = "cbc8a9b1a87023b7fd74e7b3412e6321c0eab003"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(home: Path) -> None:
    for name, expected in WEIGHTS.items():
        path = home / name
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"Model checksum mismatch or missing file: {path}")
        print(f"SHA256 OK: {name}", flush=True)


def install(home: Path, endpoint: str) -> None:
    os.environ["HF_ENDPOINT"] = endpoint
    os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "120"
    from huggingface_hub import snapshot_download
    home.mkdir(parents=True, exist_ok=True)
    for repo, revision, folder, patterns in REPOS:
        print(f"Downloading {repo}@{revision} from {endpoint}", flush=True)
        key = next(name for name in WEIGHTS if name.startswith(folder + "/"))
        existing = home / key
        valid = existing.is_file() and sha256(existing) == WEIGHTS[key]
        snapshot_download(repo, revision=revision, local_dir=home / folder, allow_patterns=patterns,
                          ignore_patterns=["*.safetensors"] if valid else None,
                          force_download=existing.is_file() and not valid)
    # Prime Demucs' standard HF cache; runtime is kept offline at this revision.
    snapshot_download("adefossez/HTDemucs", revision=DEMUCS_REVISION)
    print("Downloading pinned MIDI-LLM decoder source", flush=True)
    with tempfile.TemporaryDirectory() as temporary:
        archive = Path(temporary) / "decoder.tar.gz"
        urllib.request.urlretrieve(
            f"https://codeload.github.com/slSeanWU/MIDI-LLM/tar.gz/{CODE_REVISION}", archive
        )
        destination = home / "MIDI-LLM-code"
        destination.mkdir(exist_ok=True)
        with tarfile.open(archive) as bundle:
            for member in bundle.getmembers():
                parts = PurePosixPath(member.name).parts[1:]
                if not parts or ".." in parts or not member.isfile():
                    continue
                relative = Path(*parts)
                if relative.suffix not in {".py", ".md", ".json"}:
                    continue
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.extractfile(member) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
    verify(home)
    manifest = {"version": "0.9.0", "weights": WEIGHTS,
                "decoder_revision": CODE_REVISION, "demucs_revision": DEMUCS_REVISION}
    (home / "installed-models.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--endpoint", default="https://hf-mirror.com")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        verify(args.home)
    else:
        install(args.home, args.endpoint)


if __name__ == "__main__":
    main()
