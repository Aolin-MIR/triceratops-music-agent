"""Register a native runtime at install time; all setup controls live in the VST3."""
from __future__ import annotations
import hashlib
import json
import os
import shutil
import signal
import subprocess
import time
import sys
from pathlib import Path


def stop_previous_backend(data: Path) -> None:
    launcher_path = data/'backend.json'
    if not launcher_path.is_file(): return
    launcher = json.loads(launcher_path.read_text(encoding='utf-8-sig'))
    config_path = Path(launcher['config'])
    if not config_path.is_file(): return
    config = json.loads(config_path.read_text(encoding='utf-8-sig'))
    state_path = Path(config['runs_dir'])/'vst-service-state.json'
    if not state_path.is_file(): return
    from urllib.request import build_opener, ProxyHandler
    try:
        with build_opener(ProxyHandler({})).open('http://127.0.0.1:49327/health', timeout=2) as response:
            state = json.load(response)
    except OSError:
        return
    if state.get('busy'):
        raise RuntimeError('A music/configuration task is still running. Stop it in the plug-in before updating.')
    pid = int(json.loads(state_path.read_text())['pid'])
    if os.name == 'nt':
        result = subprocess.run(['powershell.exe', '-NoProfile', '-Command',
            f'(Get-CimInstance Win32_Process -Filter "ProcessId = {pid}").CommandLine'],
            capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
        command = result.stdout
        if result.returncode or str(config_path).lower() not in command.lower() or 'runtime.py' not in command:
            raise RuntimeError('An existing service could not be identified as this installation; it was left running.')
    else:
        command = subprocess.check_output(['ps', '-p', str(pid), '-o', 'command='], text=True)
        if str(config_path) not in command or 'runtime.py' not in command:
            raise RuntimeError('An existing service could not be identified as this installation; it was left running.')
    os.kill(pid, signal.SIGTERM)
    for _ in range(20):
        try:
            with build_opener(ProxyHandler({})).open('http://127.0.0.1:49327/health', timeout=.5): pass
        except OSError:
            return
        time.sleep(.1)
    raise RuntimeError('The previous backend did not stop; restart the plug-in after installation.')


def initialize(install: Path, data: Path, local: Path, reaper: str) -> dict:
    data.mkdir(parents=True, exist_ok=True)
    stop_previous_backend(data)
    path = data / 'runtime.json'
    old = json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}
    runtime = local / 'runtime-1.0'
    previous_python = Path(old['python']) if old.get('python') else None
    if os.name == 'nt':
        seed_python = install / 'python' / 'python.exe'
        if previous_python and previous_python.resolve().is_relative_to(local.resolve()) and previous_python.is_file() and previous_python.name.lower() == 'python.exe' and hashlib.sha256(previous_python.read_bytes()).digest() == hashlib.sha256(seed_python.read_bytes()).digest():
            runtime = previous_python.parent
        if not (runtime / 'python.exe').is_file():
            shutil.copytree(install / 'python', runtime, dirs_exist_ok=True)
        python = runtime / 'python.exe'
        (runtime / 'python311._pth').write_text('python311.zip\n.\nLib\\site-packages\n'+str(install/'backend')+'\nimport site\n', encoding='utf-8')
    else:
        # The Mac installer supplies its own dedicated Python environment.
        python = Path(old.get('python', sys.executable))
    config = {**old, 'python': str(python), 'runs_dir': old.get('runs_dir', str(data/'runs')),
              'model_home': old.get('model_home', str(local/'models')), 'reaper': old.get('reaper', reaper),
              'device': old.get('device', 'cpu'), 'midi_llm_device': old.get('midi_llm_device', old.get('device', 'cpu')), 'midi_gpt_device': old.get('midi_gpt_device', 'cpu'), 'stem_device': old.get('stem_device', 'cpu'),
              'llm_provider': 'llama_cpp' if old.get('llm_provider') == 'ollama' else old.get('llm_provider', 'disabled'), 'chat_policy': old.get('chat_policy', {'ollama': 'local', 'llama_cpp': 'local', 'remote': 'remote', 'disabled': 'disabled'}.get(old.get('llm_provider'), 'auto')), 'llm_choice': old.get('llm_choice', 'auto'), 'llm_device': old.get('llm_device', 'gpu' if old.get('llm_provider') in {'ollama', 'llama_cpp'} else 'cpu'),
              'midi_llm_choice': old.get('midi_llm_choice', old.get('midi_llm_device', old.get('device', 'auto'))), 'midi_gpt_choice': old.get('midi_gpt_choice', 'auto'), 'stem_choice': old.get('stem_choice', 'auto'),
              'model_source': old.get('model_source', 'auto'), 'setup_complete': False,
              'base_url': old.get('base_url', 'https://dashscope.aliyuncs.com/compatible-mode/v1'),
              'chat_model': old.get('chat_model', 'qwen-plus'),
              'llama_cpp_url': old.get('llama_cpp_url', 'http://127.0.0.1:1234/v1'),
              'local_model': old.get('local_model', 'qwen3.5:4b-q4_K_M')}
    # Preserve credentials but require verification against the new runtime.
    from text2music.agent.configuration import atomic_json
    atomic_json(path, config)
    launcher = {'python': str(python), 'entry': str(install/'backend/text2music/agent/runtime.py'), 'config': str(path)}
    atomic_json(data/'backend.json', launcher)
    return launcher


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root/'backend'))
    if os.name != 'nt':
        raise RuntimeError('Run first_run.initialize from the Mac installer with its dedicated Python paths')
    initialize(root, Path(os.environ['APPDATA'])/'Triceratops', Path(os.environ['LOCALAPPDATA'])/'Triceratops',
               str(Path(os.environ.get('ProgramFiles', 'C:/Program Files'))/'REAPER (x64)/reaper.exe'))
