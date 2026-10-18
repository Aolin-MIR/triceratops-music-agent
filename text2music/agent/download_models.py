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
DEMUCS_SHA256 = "d9fa14133cfcc034a6758923bb3a8ca9f8dfd0b582134643bbf83f72c17576dd"


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


def install(home: Path, endpoint: str = "auto", report=print) -> None:
    from text2music.agent.model_sources import model_sources, resolve_mirror
    route = model_sources(endpoint) if endpoint in {"auto", "official", "china"} else {"hf_endpoint": endpoint}
    endpoint = route["hf_endpoint"]
    print("MODEL_SOURCES: " + json.dumps(route, ensure_ascii=False), flush=True)
    os.environ["HF_ENDPOINT"] = endpoint
    os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "120"
    from huggingface_hub import snapshot_download
    home.mkdir(parents=True, exist_ok=True)
    import threading
    stopped = threading.Event()
    def progress():
        while not stopped.wait(3):
            size = 0
            for path in home.rglob('*'):
                try:
                    if path.is_file(): size += path.stat().st_size
                except FileNotFoundError:
                    continue
            report(f'Music model files: {size//1048576} MiB cached / downloaded; checksums are verified before completion')
    thread = threading.Thread(target=progress, daemon=True)
    thread.start()
    try:
        actual_sources = {}
        for repo, revision, folder, patterns in REPOS:
            resolved = resolve_mirror(endpoint, repo, revision, "README.md")
            actual_sources[repo] = resolved
            print("MODEL_SOURCE: " + json.dumps({"repo": repo, **resolved}), flush=True)
            print(f"Downloading {repo}@{revision} from {resolved['endpoint']}", flush=True)
            key = next(name for name in WEIGHTS if name.startswith(folder + "/"))
            existing = home / key
            valid = existing.is_file() and sha256(existing) == WEIGHTS[key]
            snapshot_download(repo, revision=revision, token=False, endpoint=resolved["endpoint"], local_dir=home / folder, allow_patterns=patterns,
                              ignore_patterns=["*.safetensors"] if valid else None,
                              force_download=existing.is_file() and not valid)
        # Prime Demucs' standard HF cache; runtime is kept offline at this revision.
        resolved = resolve_mirror(endpoint, "adefossez/HTDemucs", DEMUCS_REVISION, "htdemucs.yaml")
        actual_sources["adefossez/HTDemucs"] = resolved
        print("MODEL_SOURCE: " + json.dumps({"repo": "adefossez/HTDemucs", **resolved}), flush=True)
        demucs = Path(snapshot_download("adefossez/HTDemucs", revision=DEMUCS_REVISION, token=False, endpoint=resolved["endpoint"]))
        if sha256(demucs / "955717e8.safetensors") != DEMUCS_SHA256:
            raise RuntimeError("HTDemucs model checksum mismatch; installation stopped")
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
                    if not target.resolve().is_relative_to(destination.resolve()):
                        raise RuntimeError("Unsafe decoder archive path")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with bundle.extractfile(member) as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)
        verify(home)
        manifest = {"version": "1.0.0", "sources": route, "actual_sources": actual_sources, "weights": WEIGHTS,
                    "decoder_revision": CODE_REVISION, "demucs_revision": DEMUCS_REVISION, "demucs_sha256": DEMUCS_SHA256}
        (home / "installed-models.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    finally:
        stopped.set()
        thread.join(timeout=4)



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--endpoint", default="auto")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        verify(args.home)
    else:
        install(args.home, args.endpoint)


if __name__ == "__main__":
    main()
