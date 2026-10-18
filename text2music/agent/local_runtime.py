"""Prepare native local-chat backends with explicit GPU verification."""
from __future__ import annotations
import hashlib
import json
import os
import re
import subprocess
import shutil
import time
from pathlib import Path
from urllib.request import Request, build_opener, ProxyHandler
from dataclasses import replace

MODEL_DOWNLOAD_URL = 'http://127.0.0.1:11435'
MODEL_REGISTRY = 'https://registry.ollama.ai'


def ensure_ollama(config: dict, report) -> None:
    from text2music.agent.llm_backend import ChatSettings, local_request
    settings = replace(ChatSettings.load(), provider='ollama', base_url=MODEL_DOWNLOAD_URL,
                       model=config['local_model'], timeout=3, device=config['llm_device'])
    try:
        local_request(settings, '/api/version')
        return
    except RuntimeError:
        pass
    root = Path(__file__).resolve().parents[3]
    executable = Path(config.get('ollama_runtime', root / 'ollama')) / ('ollama.exe' if os.name == 'nt' else 'ollama')
    if not executable.is_file() and os.name != 'nt':
        system_binary = shutil.which('ollama')
        if system_binary:
            executable = Path(system_binary)
    if not executable.is_file() and __import__('sys').platform == 'darwin':
        from text2music.agent.macos_bootstrap import install_ollama
        data = Path(config['model_home']).parent
        executable = install_ollama(data, config.get('runtime_download_source', config.get('model_source', 'auto')), report) / 'ollama'
    if not executable.is_file():
        raise RuntimeError('The bundled local-chat runtime is missing. Install the complete Triceratops package, or start Ollama at the selected URL.')
    env = os.environ.copy()
    env.update(OLLAMA_HOST='127.0.0.1:11435', OLLAMA_MODELS=str(config.get('ollama_model_store', Path(config['model_home'])/'ollama')),
               OLLAMA_KEEP_ALIVE='-1', OLLAMA_NUM_PARALLEL='1', OLLAMA_MAX_LOADED_MODELS='1',
               OLLAMA_CONTEXT_LENGTH=str(config.get('llm_context', 8192)))
    if config.get('gpu_index') is not None:
        env['CUDA_VISIBLE_DEVICES'] = str(config['gpu_index'])
    log = Path(config['model_home']).parent / 'ollama-download-server.log'
    log.parent.mkdir(parents=True, exist_ok=True)
    report('Starting the bundled local chat runtime')
    with log.open('ab') as output:
        subprocess.Popen([str(executable), 'serve'], env=env, stdout=output, stderr=output,
                         stdin=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    for _ in range(60):
        time.sleep(.5)
        try:
            local_request(settings, '/api/version')
            return
        except RuntimeError:
            continue
    raise RuntimeError('Local runtime did not start within 30 seconds; see ollama-server.log')


def pull_model(config: dict, report) -> None:
    request = Request(MODEL_DOWNLOAD_URL+'/api/pull',
                      data=json.dumps({'model': config['local_model'], 'stream': True}).encode(),
                      headers={'Content-Type': 'application/json'})
    report('Local chat model: official Ollama registry (no verified domestic mirror)')
    with build_opener(ProxyHandler({})).open(request, timeout=120) as response:
        complete = False
        last = 0.0
        for line in response:
            item = json.loads(line)
            if item.get('error'):
                raise RuntimeError(item['error'])
            complete = item.get('status') == 'success'
            if time.monotonic()-last > 1 or complete:
                report(f"Local model: {item.get('status', '')} {item.get('completed', 0)//1048576}/{item.get('total', 0)//1048576} MiB")
                last = time.monotonic()
        if not complete:
            raise RuntimeError('Local model download did not finish successfully')


def pull_model_registry(config: dict, report) -> None:
    """Download only the GGUF layer needed by llama.cpp, without installing Ollama."""
    model = config['local_model']
    name, separator, tag = model.rpartition(':')
    if not separator:
        name, tag = model, 'latest'
    if (not name or not re.fullmatch(r'[A-Za-z0-9._/-]+', name)
            or any(part in {'.', '..'} for part in name.split('/'))
            or not re.fullmatch(r'[A-Za-z0-9._-]+', tag)):
        raise ValueError('The local model must use a valid registry name and tag')
    repository = name if '/' in name else 'library/' + name
    base_url = f'{MODEL_REGISTRY}/v2/{repository}'
    manifest_request = Request(base_url + '/manifests/' + tag, headers={
        'Accept': 'application/vnd.docker.distribution.manifest.v2+json, application/vnd.oci.image.manifest.v1+json',
        'User-Agent': 'Triceratops/1.0 local-model-setup',
    })
    with build_opener().open(manifest_request, timeout=60) as response:
        manifest = json.loads(response.read(2 * 1024 * 1024))
    layers = [layer for layer in manifest.get('layers', [])
              if layer.get('mediaType') == 'application/vnd.ollama.image.model']
    if len(layers) != 1:
        raise RuntimeError('The selected registry manifest must contain exactly one GGUF model layer')
    layer = layers[0]
    digest = layer.get('digest', '')
    size = layer.get('size')
    if (not re.fullmatch(r'sha256:[0-9a-f]{64}', digest)
            or not isinstance(size, int) or size <= 0):
        raise RuntimeError('The model registry returned an invalid GGUF layer descriptor')

    model_store = Path(config.get('ollama_model_store', Path(config['model_home']) / 'ollama'))
    blob = model_store / 'blobs' / digest.replace(':', '-')
    partial = blob.with_name(blob.name + '.partial')
    blob.parent.mkdir(parents=True, exist_ok=True)

    def file_hash(path: Path) -> tuple[str, int]:
        hasher = hashlib.sha256()
        length = 0
        with path.open('rb') as source:
            for chunk in iter(lambda: source.read(4 * 1024 * 1024), b''):
                hasher.update(chunk)
                length += len(chunk)
        return hasher.hexdigest(), length

    if blob.is_file():
        existing_hash, existing_size = file_hash(blob)
        if existing_hash != digest[7:] or existing_size != size:
            blob.unlink()
        else:
            report(f'Local GGUF is verified ({size // 1048576} MiB)')

    if not blob.is_file():
        offset = partial.stat().st_size if partial.is_file() else 0
        if offset >= size:
            partial.unlink()
            offset = 0
        headers = {'User-Agent': 'Triceratops/1.0 local-model-setup'}
        if offset:
            headers['Range'] = f'bytes={offset}-'
        report('Local chat model: downloading verified GGUF from the official model registry')
        request = Request(base_url + '/blobs/' + digest, headers=headers)
        with build_opener().open(request, timeout=60) as response:
            status = getattr(response, 'status', response.getcode())
            if offset and status == 206:
                content_range = response.headers.get('Content-Range', '')
                if not content_range.startswith(f'bytes {offset}-'):
                    raise RuntimeError('The model registry returned an invalid resume range')
                mode = 'ab'
            elif status == 200:
                offset = 0
                mode = 'wb'
            else:
                raise RuntimeError(f'The model registry returned unexpected HTTP status {status}')
            hasher = hashlib.sha256()
            if offset:
                with partial.open('rb') as source:
                    for chunk in iter(lambda: source.read(4 * 1024 * 1024), b''):
                        hasher.update(chunk)
            downloaded = offset
            last_report = time.monotonic()
            with partial.open(mode) as output:
                while True:
                    chunk = response.read(4 * 1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
                    hasher.update(chunk)
                    downloaded += len(chunk)
                    if downloaded > size:
                        raise RuntimeError('The downloaded GGUF is larger than its registry descriptor')
                    if time.monotonic() - last_report >= 1:
                        report(f'Local model: {downloaded // 1048576}/{size // 1048576} MiB')
                        last_report = time.monotonic()
                output.flush()
                os.fsync(output.fileno())
        if downloaded != size or hasher.hexdigest() != digest[7:]:
            raise RuntimeError('The downloaded GGUF size or SHA-256 does not match the registry manifest')
        os.replace(partial, blob)

    manifest_path = model_store / 'manifests' / 'registry.ollama.ai' / repository / tag
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    stored_manifest = {'schemaVersion': 2, 'layers': [layer]}
    temporary_manifest = manifest_path.with_name(manifest_path.name + '.tmp')
    temporary_manifest.write_text(json.dumps(stored_manifest), encoding='utf-8')
    os.replace(temporary_manifest, manifest_path)
    report(f'Local model verified: {size // 1048576} MiB (SHA-256)')


def _model_gguf(config: dict) -> Path:
    model = config['local_model']
    name, separator, tag = model.rpartition(':')
    if not separator:
        name, tag = model, 'latest'
    model_store = Path(config.get('ollama_model_store', Path(config['model_home'])/'ollama'))
    repository = name if '/' in name else 'library/' + name
    manifest = model_store/'manifests'/'registry.ollama.ai'/repository/tag
    if not manifest.is_file():
        raise FileNotFoundError(f'Local chat model manifest is missing: {manifest}')
    data = json.loads(manifest.read_text(encoding='utf-8'))
    layers = [layer for layer in data.get('layers', []) if layer.get('mediaType') == 'application/vnd.ollama.image.model']
    if len(layers) != 1 or not str(layers[0].get('digest', '')).startswith('sha256:'):
        raise RuntimeError('The selected model manifest does not identify exactly one GGUF model layer')
    blob = model_store/'blobs'/layers[0]['digest'].replace(':', '-')
    if not blob.is_file() or blob.stat().st_size != int(layers[0]['size']):
        raise RuntimeError('The local GGUF model layer is missing or incomplete')
    return blob


def ensure_llama_cpp(config: dict, report, *, download: bool = False) -> None:
    """Run the pinned GGUF model with every layer on the selected Vulkan GPU."""
    if config.get('llm_device') != 'gpu':
        raise RuntimeError('Local chat requires GPU mode; CPU inference is disabled.')
    root = Path(__file__).resolve().parents[3]
    executable = Path(config.get('llama_cpp_runtime', root/'llama-cpp'))/'llama-server.exe'
    if os.name != 'nt' or not executable.is_file():
        raise RuntimeError('The bundled Windows Vulkan llama.cpp runtime is missing. Reinstall the complete Triceratops package.')
    from text2music.agent.llm_backend import ChatSettings, server_request
    model_server_url = config.get('llama_cpp_url', 'http://127.0.0.1:1234/v1').rstrip('/')
    parsed = __import__('urllib.parse', fromlist=['urlparse']).urlparse(model_server_url)
    if parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost', '::1'} or parsed.path.rstrip('/') != '/v1':
        raise ValueError('llama.cpp must bind to a loopback HTTP /v1 endpoint')
    if download:
        pull_model_registry(config, report)
    model_path = _model_gguf(config)
    devices = subprocess.run([str(executable), '--list-devices'], capture_output=True, text=True, timeout=20)
    if devices.returncode:
        raise RuntimeError('llama.cpp could not enumerate Vulkan devices; no CPU fallback is allowed.')
    from text2music.agent.hardware import inspect_hardware
    hardware = inspect_hardware()
    gpu_index = config.get('gpu_index')
    nvidia = next((gpu for gpu in hardware['nvidia'] if gpu['index'] == gpu_index), None)
    if nvidia is None and gpu_index is None and hardware['nvidia']:
        nvidia = max(hardware['nvidia'], key=lambda gpu: gpu['free'])
    if nvidia is None:
        raise RuntimeError('The selected NVIDIA GPU could not be verified for local chat.')
    import re
    match = next((re.match(r'\s*(Vulkan\d+):\s*(.*)', line) for line in devices.stdout.splitlines()
                  if nvidia['name'].casefold() in line.casefold()), None)
    if not match:
        raise RuntimeError('The selected NVIDIA GPU is unavailable in llama.cpp Vulkan; CPU fallback is disabled.')
    device = match.group(1)
    log = Path(config['model_home']).parent/'llama-cpp-gpu-server.log'
    log.parent.mkdir(parents=True, exist_ok=True)
    pid_marker = log.with_suffix('.json')
    if pid_marker.is_file():
        try:
            marker = json.loads(pid_marker.read_text(encoding='utf-8'))
            os.kill(int(marker['pid']), 0)
            props = server_request(ChatSettings('llama_cpp', config['local_model'], model_server_url, 'gpu', 3, 8192),
                                   model_server_url[:-3]+'/props')
            if marker.get('device') == device and props.get('model_alias') == config['local_model']:
                marker.update({'gpu_index': nvidia['index'], 'gpu_name': nvidia['name'],
                               'resident_gpu_bytes': model_path.stat().st_size,
                               'all_layers_on_gpu': True, 'model_path': str(model_path)})
                pid_marker.write_text(json.dumps(marker, indent=2), encoding='utf-8')
                report('Verified the existing llama.cpp GPU server and resident model')
                return
        except (OSError, KeyError, ValueError, RuntimeError):
            pid_marker.unlink(missing_ok=True)
    health_url = model_server_url[:-3].rstrip('/')+'/health'
    try:
        server_request(ChatSettings('llama_cpp', config['local_model'], model_server_url, 'gpu', 2, 8192), health_url)
    except RuntimeError:
        pass
    else:
        raise RuntimeError('The local inference port is occupied by an unmanaged server; stop it before setup.')
    command = [str(executable), '--model', str(model_path), '--alias', config['local_model'],
               '--host', parsed.hostname, '--port', str(parsed.port or 1234), '--ctx-size', str(config.get('llm_context', 8192)),
               '--n-gpu-layers', 'all', '--device', device, '--parallel', '1', '--jinja', '--no-ui', '--no-warmup', '--verbose']
    report(f'Starting llama.cpp with all model layers on {nvidia["name"]} ({device})')
    with log.open('wb') as output:
        process = subprocess.Popen(command, cwd=str(executable.parent), stdout=output, stderr=subprocess.STDOUT,
                                   stdin=subprocess.DEVNULL, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    for _ in range(180):
        if process.poll() is not None:
            detail = log.read_text(encoding='utf-8', errors='replace')[-1200:] if log.exists() else ''
            raise RuntimeError('llama.cpp GPU startup failed; CPU fallback is disabled. '+detail)
        time.sleep(.5)
        try:
            if server_request(ChatSettings('llama_cpp', config['local_model'], model_server_url, 'gpu', 3, 8192), health_url).get('status') == 'ok':
                break
        except RuntimeError:
            continue
    else:
        process.terminate()
        raise RuntimeError('llama.cpp GPU server did not become ready within 90 seconds; CPU fallback is disabled.')
    details = log.read_text(encoding='utf-8', errors='replace')
    offload = re.search(r'offloaded\s+(\d+)/(\d+)\s+layers to GPU', details, re.IGNORECASE)
    if not offload or offload.group(1) != offload.group(2):
        process.terminate()
        raise RuntimeError('llama.cpp did not confirm every model layer on GPU; CPU fallback is disabled.')
    pid_marker.write_text(json.dumps({'pid': process.pid, 'device': device, 'model': config['local_model'],
                                      'model_path': str(model_path), 'gpu_index': nvidia['index'],
                                      'gpu_name': nvidia['name'], 'resident_gpu_bytes': model_path.stat().st_size,
                                      'all_layers_on_gpu': True}, indent=2), encoding='utf-8')
    report(f'GPU verified: all {offload.group(1)} model layers resident on {nvidia["name"]}')


def ensure_macos_local(config: dict, report, *, download: bool = False) -> None:
    """Use Ollama's native Metal path and require measured full GPU residency."""
    import platform
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        raise RuntimeError('The Metal local-chat runtime requires native Apple Silicon')
    if config.get('llm_device') != 'gpu':
        raise RuntimeError('Local chat requires GPU mode; CPU offload is disabled')
    ensure_ollama(config, report)
    if download:
        pull_model(config, report)
    from text2music.agent.llm_backend import ChatSettings, local_request, residency
    settings = replace(ChatSettings.load(), timeout=180)
    report('Loading the selected local model on Metal; verifying actual GPU residency')
    local_request(settings, '/api/chat', {'model': settings.model, 'stream': False,
        'messages': [{'role': 'user', 'content': 'Reply OK'}], 'keep_alive': -1,
        'options': {'num_ctx': settings.context_size, 'num_predict': 4}})
    actual = residency(settings)
    report('Metal GPU residency verified: ' + str(actual['vram_bytes']) + ' bytes')


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description='Prepare the pinned local chat model on the selected GPU')
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    from text2music.agent.runtime import configure
    config = configure(args.config)
    ensure_llama_cpp(config, print, download=True)


if __name__ == '__main__':
    main()
