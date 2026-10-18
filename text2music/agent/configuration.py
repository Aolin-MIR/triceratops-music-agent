"""User-owned configuration jobs for the in-plugin Settings panel."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import threading
import uuid
from pathlib import Path

FIELDS = {'chat_policy', 'local_model', 'llm_choice', 'midi_llm_choice', 'midi_gpt_choice',
          'stem_choice', 'midi_llm_dtype', 'model_source', 'llama_cpp_url', 'api_key', 'base_url', 'chat_model', 'llm_context'}


def read_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def revision(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('w', encoding='utf-8') as output:
        os.chmod(temporary, 0o600)
        json.dump(data, output, ensure_ascii=False, indent=2)
    temporary.replace(path)


def validate_changes(changes: dict) -> None:
    if not isinstance(changes, dict) or set(changes) - FIELDS:
        raise ValueError('Unsupported settings field')
    for key, value in changes.items():
        if not isinstance(value, str) or len(value) > 2048:
            raise ValueError(f'Invalid settings value: {key}')
    enums = {'chat_policy': {'auto', 'local', 'remote', 'disabled'}, 'llm_choice': {'auto', 'gpu'},
             'model_source': {'auto', 'official', 'china'}, 'llm_context': {'4096', '8192', '16384'}}
    for key in ('midi_llm_choice', 'midi_gpt_choice', 'stem_choice'):
        enums[key] = {'auto', 'cpu', 'cuda'}
    enums['midi_llm_dtype'] = {'auto', 'default', 'float32', 'float16', 'bfloat16'}
    if sys.platform == 'darwin':
        for key in ('midi_llm_choice', 'midi_gpt_choice', 'stem_choice'):
            enums[key].add('mps')
    for key, options in enums.items():
        if key in changes and changes[key] not in options:
            raise ValueError(f'Invalid {key}')
    from urllib.parse import urlparse
    for field in ('llama_cpp_url', 'base_url'):
        if field not in changes:
            continue
        parsed = urlparse(changes[field])
        if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError(f'Invalid {field}')
        if field == 'llama_cpp_url' and (parsed.hostname not in {'127.0.0.1', 'localhost', '::1'} or parsed.path.rstrip('/') != '/v1'):
            raise ValueError('Local chat must use the loopback llama.cpp /v1 URL')
    if 'local_model' in changes:
        import re
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_./:-]{0,199}', changes['local_model']):
            raise ValueError('Invalid local model name')


def public_config(path: Path) -> dict:
    config = read_config(path)
    provider = config.get('llm_provider', 'remote')
    fields = {name: config.get(name, '') for name in FIELDS - {'api_key'}}
    fields.update(chat_policy=config.get('chat_policy', {'ollama': 'local', 'llama_cpp': 'local'}.get(provider, provider)),
                  local_model=config.get('local_model', 'qwen3.5:4b-q4_K_M'),
                  llama_cpp_url=config.get('llama_cpp_url', 'http://127.0.0.1:1234/v1'),
                  base_url=config.get('base_url', 'https://dashscope.aliyuncs.com/compatible-mode/v1'),
                  chat_model=config.get('chat_model', 'qwen-plus'), model_source=config.get('model_source', 'auto'))
    fields['llm_context'] = str(config.get('llm_context', 8192))
    for key in ('llm_choice', 'midi_llm_choice', 'midi_gpt_choice', 'stem_choice'):
        fields[key] = config.get(key, 'auto')
    fields['midi_llm_dtype'] = config.get('midi_llm_dtype', 'auto' if sys.platform == 'darwin' else 'default')
    from text2music.agent.model_policy import precision_status
    precision = precision_status(config) if sys.platform == 'darwin' else None
    return {'revision': revision(path), 'settings': fields, 'api_key_configured': bool(config.get('api_key')),
            'setup_required': not config.get('setup_complete', False), 'provider': provider,
            'api_requirement': config.get('api_requirement', 'unknown'),
            'devices': {key: config.get(key, config.get('device', 'cpu')) for key in ('llm_device', 'midi_llm_device', 'midi_gpt_device', 'stem_device')},
            'hardware_plan': config.get('hardware_plan', {}), 'model_sources': config.get('model_sources', {}),
            'local_error': config.get('local_error', ''), 'composition_precision': precision}


def include_resident_gpu(hardware: dict, config: dict) -> dict:
    """Credit verified llama.cpp weight residency while retaining runtime headroom."""
    if hardware['system'] == 'Darwin' and hardware['architecture'] == 'arm64':
        from text2music.agent.llm_backend import ChatSettings, residency
        try:
            actual = residency(ChatSettings('ollama', config.get('local_model', 'qwen3.5:4b-q4_K_M'),
                'http://127.0.0.1:11435', 'gpu', 3, int(config.get('llm_context', 8192))))
            resident = actual['vram_bytes']
            return {**hardware, 'ram_available': min(hardware['ram_total'], hardware['ram_available'] + resident),
                    'resident_local_bytes': resident}
        except (OSError, ValueError, RuntimeError):
            return hardware
    if (len(hardware['nvidia']) != 1 or config.get('llm_provider') != 'llama_cpp'
            or not config.get('model_home')):
        return hardware
    marker_path = Path(config['model_home']).parent / 'llama-cpp-gpu-server.json'
    try:
        marker = json.loads(marker_path.read_text(encoding='utf-8'))
        if (marker.get('model') != config.get('local_model', 'qwen3.5:4b-q4_K_M')
                or marker.get('gpu_index') != hardware['nvidia'][0]['index']
                or marker.get('gpu_name') != hardware['nvidia'][0]['name']
                or marker.get('all_layers_on_gpu') is not True):
            return hardware
        os.kill(int(marker['pid']), 0)
        resident_bytes = int(marker['resident_gpu_bytes'])
        if resident_bytes <= 0 or Path(marker['model_path']).stat().st_size != resident_bytes:
            return hardware
        from text2music.agent.llm_backend import ChatSettings, residency
        base_url = config.get('llama_cpp_url', 'http://127.0.0.1:1234/v1')
        status = residency(ChatSettings('llama_cpp', marker['model'], base_url, 'gpu', 3,
                                        int(config.get('llm_context', 8192))))
        if status.get('resident') is not True or status.get('model') != marker['model']:
            return hardware
    except (KeyError, OSError, TypeError, ValueError, RuntimeError):
        return hardware
    gpu = dict(hardware['nvidia'][0])
    gpu['free'] = min(gpu['total'], gpu['free'] + resident_bytes)
    gpu['resident_local_bytes'] = resident_bytes
    return {**hardware, 'nvidia': [gpu]}


class ConfigurationJobs:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.RLock()
        self.process = None
        self.job = {'state': 'idle', 'detail': ''}
        # The service restarts after apply. Keep the committed verification
        # report visible so that reconnecting cannot erase success feedback.
        previous = read_config(path).get('configuration_job', '')
        if isinstance(previous, str) and len(previous) == 32 and all(c in '0123456789abcdef' for c in previous):
            report_path = path.parent / 'configuration' / previous / 'report.json'
            if report_path.is_file():
                report = read_config(report_path)
                if report.get('state') == 'complete':
                    self.job = {'id': previous, **report}
        self.progress = None

    def snapshot(self):
        with self.lock:
            job = dict(self.job)
            if self.job.get('state') == 'running' and self.process and self.process.poll() is None and self.progress and self.progress.exists():
                try:
                    job.update(read_config(self.progress))
                except (ValueError, OSError):
                    pass  # A missing intermediate progress tick never changes terminal state.
            return {**public_config(self.path), 'job': job}

    def start(self, payload: dict, done) -> dict:
        action = payload.get('action')
        if action not in {'inspect', 'prepare', 'apply'}:
            raise ValueError('Settings action must be inspect, prepare or apply')
        changes = payload.get('settings', {})
        validate_changes(changes)
        with self.lock:
            if self.process is not None:
                raise RuntimeError('Another settings task is running')
            if payload.get('revision') != revision(self.path):
                raise RuntimeError('Settings changed in another editor. Close and reopen Settings before applying.')
            job_id = uuid.uuid4().hex
            folder = self.path.parent / 'configuration' / job_id
            folder.mkdir(parents=True)
            request = folder / 'request.json'
            self.progress = folder / 'progress.json'
            report = folder / 'report.json'
            atomic_json(request, {'changes': changes, 'action': action, 'revision': payload['revision'], 'job_id': job_id})
            self.job = {'id': job_id, 'state': 'running', 'detail': 'Checking configuration'}
            command = [sys.executable, '-X', 'utf8', str(Path(__file__).resolve()), '--worker',
                       '--config', str(self.path), '--request', str(request), '--report', str(report)]
            options = {'creationflags': subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {'start_new_session': True}
            try:
                self.process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **options)
            except OSError:
                request.unlink(missing_ok=True)
                self.job = {'id': job_id, 'state': 'failed', 'detail': 'Could not start the configuration worker.'}
                raise RuntimeError(self.job['detail']) from None
            process = self.process
            def wait():
                process.wait()
                with self.lock:
                    cancelled = self.job.get('state') == 'cancelling'
                    try:
                        result = read_config(report)
                        if not isinstance(result, dict) or result.get('state') not in {'complete', 'failed', 'needs_api'}:
                            raise ValueError('Invalid terminal report')
                    except (ValueError, OSError):
                        result = {'state': 'failed', 'detail': 'Configuration worker did not produce a valid verification report.'}
                    if cancelled and read_config(self.path).get('configuration_job') == job_id:
                        cancelled = False
                        result = {'state': 'complete', 'detail': 'Settings were applied before cancellation arrived.'}
                    self.job = {'id': job_id, **({'state': 'cancelled', 'detail': 'Configuration cancelled. Previous settings retained.'} if cancelled else result)}
                    request.unlink(missing_ok=True)
                    request.with_name('candidate.json').unlink(missing_ok=True)
                    self.process = None
                    finished = dict(self.job)
                done(finished)
            threading.Thread(target=wait, daemon=True).start()
            return self.snapshot()

    def cancel(self):
        with self.lock:
            if self.process and self.process.poll() is None:
                self.job.update(state='cancelling', detail='Stopping configuration')
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(self.process.pid), '/T', '/F'], capture_output=True,
                                   creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
                else:
                    os.killpg(self.process.pid, signal.SIGTERM)
            return self.snapshot()


def install_cuda_torch(config: dict, job_id: str, report, run, *, windows: bool) -> None:
    """Keep Windows DLLs used by the current service untouched during setup."""
    command = [sys.executable, '-m', 'pip', 'install', '--upgrade', '--no-deps', 'torch==2.13.0']
    if windows:
        # CUDA Torch can also execute explicit CPU music tasks. Reuse only a
        # previously committed private target; doctor checks actual CUDA use.
        previous = config.get('torch_runtime', '')
        if previous:
            from importlib.metadata import distributions
            versions = [dist.version for dist in distributions(path=[previous]) if dist.metadata.get('Name', '').lower() == 'torch']
            if versions == ['2.13.0+cu130']:
                report('Using the installed private CUDA Torch runtime')
                return
        target = Path(config['python']).parent / 'torch-runtimes' / job_id
        target.mkdir(parents=True, exist_ok=False)
        command.extend(['--target', str(target)])
        extras = [path for path in config.get('extra_python_paths', []) if path != previous]
        config.update(torch_runtime=str(target), extra_python_paths=[str(target), *extras])
    command.extend(['--index-url', 'https://download.pytorch.org/whl/cu130'])
    report('Installing CUDA Torch for the final verified device selection')
    run(command)


def worker(path: Path, request: Path, output: Path):
    # Heavy dependencies and temporary candidate environment stay out of the live service.
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    data = read_config(request)
    config = read_config(path)
    changes = data['changes']
    validate_changes(changes)
    key = changes.get('api_key') or config.get('api_key', '')
    config.update({k: v for k, v in changes.items() if k != 'api_key'})
    config.setdefault('base_url', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
    config.setdefault('chat_model', 'qwen-plus')
    config['api_key'] = key
    progress = output.with_name('progress.json')
    def report(detail):
        safe = str(detail).replace(key, '[redacted]') if key else str(detail)
        atomic_json(progress, {'state': 'running', 'detail': safe[-1800:]})
    def run(command):
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding='utf-8', errors='replace',
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        for line in proc.stdout:
            if line.strip(): report(line.strip())
        if proc.wait(): raise RuntimeError('Installation or verification failed. ' + read_config(progress)['detail'])
    candidate = output.with_name('candidate.json')
    try:
        from text2music.agent.hardware import inspect_hardware, plan_devices
        from text2music.agent.model_sources import model_sources, resolve_mirror
        report('Detecting memory and available GPU capacity')
        policy = config.get('chat_policy', 'auto')
        measured = inspect_hardware()
        if policy in {'auto', 'local'}:
            measured = include_resident_gpu(measured, config)
        music_choices = {name: config.get(name+'_choice', 'auto') for name in ('midi_llm', 'midi_gpt', 'stem')}
        local_plan_error = ''
        try:
            plan = plan_devices(measured, local_chat=policy in {'auto', 'local'},
                                llm_choice=config.get('llm_choice', 'auto'), music_choices=music_choices,
                                local_model=config.get('local_model', ''), midi_llm_dtype=config.get('midi_llm_dtype', 'auto'))
        except ValueError as exc:
            if policy != 'auto': raise
            local_plan_error = str(exc)
            plan = plan_devices(measured, local_chat=False,
                                llm_choice=config.get('llm_choice', 'auto'), music_choices=music_choices)
        config.update({k: plan[k] for k in ('llm_device', 'midi_llm_device', 'midi_gpt_device', 'stem_device', 'gpu_index')})
        config['hardware_plan'] = plan
        report('Selecting model sources by public egress country')
        route = model_sources(config.get('model_source', 'auto'))
        if route['hf_endpoint'].endswith('hf-mirror.com'):
            from text2music.agent.download_models import REPOS, DEMUCS_REVISION
            targets = [(repo, rev, 'README.md') for repo, rev, *_ in REPOS] + [('adefossez/HTDemucs', DEMUCS_REVISION, 'htdemucs.yaml')]
            route['actual_sources'] = {repo: resolve_mirror(route['hf_endpoint'], repo, rev, name) for repo, rev, name in targets}
            if all(item['endpoint'] == 'https://huggingface.co' for item in route['actual_sources'].values()):
                route['hf_endpoint'] = 'https://huggingface.co'
                route['reason'] = 'Domestic mirror unavailable for pinned revisions; official model sources selected.'
        config.update(model_sources=route, hf_endpoint=route['hf_endpoint'], device=config['midi_llm_device'])
        if data['action'] == 'inspect':
            atomic_json(output, {'state': 'complete', 'detail': 'Hardware detected. Apply to verify and save.', 'hardware_plan': plan, 'model_sources': route})
            return
        if data['action'] == 'prepare':
            requirements = Path(__file__).with_name('requirements-runtime.txt')
            if not requirements.exists(): requirements = root / 'vst3' / 'installer' / 'requirements-runtime.txt'
            report('Installing dedicated Python dependencies')
            if measured['system'] == 'Darwin':
                # Keep the Windows deployment unchanged. Transport selection
                # affects package downloads only, never API requests.
                china = route.get('music_models') == 'china-mirror'
                indexes = (['https://mirrors.aliyun.com/pypi/simple/', 'https://pypi.org/simple']
                           if china else ['https://pypi.org/simple', 'https://mirrors.aliyun.com/pypi/simple/'])
                for index_number, index in enumerate(indexes):
                    try:
                        report('Installing dependencies from ' + index)
                        run([sys.executable, '-m', 'pip', 'install', '-r', str(requirements),
                             '--disable-pip-version-check', '--timeout', '20', '--retries', '2', '--index-url', index])
                        break
                    except RuntimeError:
                        if index_number == len(indexes)-1: raise
                        report('Dependency source failed; retrying the alternate package index')
                from text2music.agent.macos_bootstrap import download
                decoder = download('https://github.com/jthickstun/anticipation/archive/af37397922665a0fb8d474d7988b0f3755a38d45.tar.gz',
                    'a002ec7c4e5aa695eef8bc569d49612b950b27bf801fdf0e3408046167d2e90f', 38847,
                    Path(config['model_home']).parent/'downloads', 'china' if china else 'auto', report)
                run([sys.executable, '-m', 'pip', 'install', '--no-deps', '--no-build-isolation', str(decoder)])
            else:
                run([sys.executable, '-m', 'pip', 'install', '-r', str(requirements), '--disable-pip-version-check'])
                run([sys.executable, '-m', 'pip', 'install', '--no-deps', 'https://codeload.github.com/jthickstun/anticipation/tar.gz/af37397922665a0fb8d474d7988b0f3755a38d45'])
            report('Downloading pinned music models from '+route['hf_endpoint'])
            from text2music.agent.download_models import install
            install(Path(config['model_home']), route['hf_endpoint'], report=report)
        config.setdefault('llama_cpp_url', 'http://127.0.0.1:1234/v1')
        config.setdefault('local_model', 'qwen3.5:4b-q4_K_M')
        if measured['system'] == 'Darwin' and config['local_model'] == 'qwen3.5:2b-q4_K_M':
            config.setdefault('llm_context', 8192)
        from text2music.agent.runtime import configure
        from text2music.agent.llm_backend import check_chat_backend
        config['local_error'] = local_plan_error
        if policy in {'auto', 'local'}:
            try:
                if local_plan_error: raise RuntimeError(local_plan_error)
                if not plan['local_feasible']: raise RuntimeError('Insufficient measured RAM headroom for the selected local model combination')
                mac_local = measured['system'] == 'Darwin' and measured['architecture'] == 'arm64'
                config['llm_provider'] = 'ollama' if mac_local else 'llama_cpp'
                atomic_json(candidate, config)
                configure(candidate)
                from text2music.agent.local_runtime import ensure_llama_cpp
                if mac_local:
                    from text2music.agent.local_runtime import ensure_macos_local
                    ensure_macos_local(config, report, download=data['action'] == 'prepare')
                else:
                    ensure_llama_cpp(config, report, download=data['action'] == 'prepare')
                report('Checking local native tool calling, replay and fixed-device residency')
                config['chat_check'] = check_chat_backend()
                config['api_requirement'] = 'optional'
            except Exception as exc:
                if policy == 'local': raise
                config['local_error'] = str(exc).replace(key, '[redacted]') if key else str(exc)
                config['llm_provider'] = 'remote'
                config['api_requirement'] = 'required'
                report('Local chat unavailable: '+config['local_error'])
                if not key:
                    atomic_json(output, {'state': 'needs_api', 'detail': 'Local chat is unavailable. Enter an API key and verify cloud chat, or select direct buttons only.',
                                         'api_requirement': 'required', 'local_error': config['local_error'], 'hardware_plan': plan, 'model_sources': route})
                    return
        else:
            config['llm_provider'] = policy
            config['api_requirement'] = 'required' if policy == 'remote' else 'unused'
        if config['llm_provider'] == 'remote' and policy == 'auto':
            cloud_plan = plan_devices(inspect_hardware(), local_chat=False, music_choices=music_choices)
            for name in ('midi_llm', 'midi_gpt', 'stem'):
                if config.get(name+'_choice', 'auto') == 'auto': config[name+'_device'] = cloud_plan[name+'_device']
            config['device'] = config['midi_llm_device']
            config['hardware_plan'] = cloud_plan
            config['gpu_index'] = cloud_plan['gpu_index']
        if data['action'] == 'prepare' and 'cuda' in {config[k] for k in ('midi_llm_device', 'midi_gpt_device', 'stem_device')}:
            install_cuda_torch(config, data['job_id'], report, run, windows=os.name == 'nt')
        atomic_json(candidate, config)
        configure(candidate)
        if config['llm_provider'] not in {'llama_cpp', 'ollama'}:
            report('Checking selected cloud API tool calling' if policy != 'disabled' else 'Checking direct-button mode')
            config['chat_check'] = check_chat_backend()
        report('Verifying dependencies, selected devices and actual music models')
        from text2music.agent.doctor import check
        check(candidate, check_chat=False)
        if revision(path) != data['revision']:
            raise RuntimeError('Configuration changed while this task ran; previous settings retained')
        config.update(setup_complete=True, version='1.0.1b', configuration_job=data['job_id'])
        atomic_json(path, config)
        atomic_json(output, {'state': 'complete', 'detail': 'Verified and applied. Devices stay fixed until the next configuration.',
                             'api_requirement': config['api_requirement']})
    except Exception as exc:
        detail = f'{type(exc).__name__}: {exc}'
        if key: detail = detail.replace(key, '[redacted]')
        atomic_json(output, {'state': 'failed', 'detail': detail[-2200:]})
    finally:
        candidate.unlink(missing_ok=True)
        request.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', action='store_true', required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    worker(args.config, args.request, args.report)
