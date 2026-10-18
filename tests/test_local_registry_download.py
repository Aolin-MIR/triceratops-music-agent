import hashlib
import json
from pathlib import Path

from text2music.agent import local_runtime


class Response:
    def __init__(self, body, status=200, headers=None):
        self.body = body
        self.status = status
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, size=-1):
        if size < 0:
            size = len(self.body)
        result, self.body = self.body[:size], self.body[size:]
        return result

    def getcode(self):
        return self.status


def test_registry_download_extracts_only_verified_gguf_layer(tmp_path, monkeypatch):
    model_bytes = b"verified-gguf-fixture"
    digest = "sha256:" + hashlib.sha256(model_bytes).hexdigest()
    manifest = json.dumps({
        "schemaVersion": 2,
        "layers": [
            {"mediaType": "application/vnd.ollama.image.projector", "digest": "sha256:" + "0" * 64, "size": 99},
            {"mediaType": "application/vnd.ollama.image.model", "digest": digest, "size": len(model_bytes)},
        ],
    }).encode()
    requested = []

    class Opener:
        def open(self, request, timeout):
            requested.append((request.full_url, timeout))
            if "/manifests/4b-q4_K_M" in request.full_url:
                return Response(manifest)
            if request.full_url.endswith("/blobs/" + digest):
                return Response(model_bytes)
            raise AssertionError(f"Unexpected URL: {request.full_url}")

    monkeypatch.setattr(local_runtime, "MODEL_REGISTRY", "https://registry.test")
    monkeypatch.setattr(local_runtime, "build_opener", lambda: Opener())
    config = {
        "local_model": "qwen3.5:4b-q4_K_M",
        "model_home": str(tmp_path / "models"),
    }
    reports = []

    local_runtime.pull_model_registry(config, reports.append)

    model_path = local_runtime._model_gguf(config)
    assert model_path.read_bytes() == model_bytes
    assert len(requested) == 2
    assert requested[0][0].endswith("/v2/library/qwen3.5/manifests/4b-q4_K_M")
    assert requested[1][0].endswith("/v2/library/qwen3.5/blobs/" + digest)
    assert "SHA-256" in reports[-1]


def test_release_windows_payload_does_not_require_or_include_ollama(tmp_path):
    import importlib.util

    script = Path(__file__).parents[1] / "vst3/installer/package_release.py"
    spec = importlib.util.spec_from_file_location("package_release_windows_without_ollama", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    plugin = tmp_path / "Triceratops.vst3"
    plugin.mkdir()
    python_seed = tmp_path / "python"
    python_seed.mkdir()
    llama_cpp = tmp_path / "llama-cpp"
    llama_cpp.mkdir()
    (llama_cpp / "llama-server.exe").write_bytes(b"fixture")
    output = tmp_path / "payload"

    module.package(plugin, output, "windows", python_seed=python_seed,
                   llama_cpp_runtime=llama_cpp)

    assert (output / "llama-cpp" / "llama-server.exe").is_file()
    assert not (output / "ollama").exists()
