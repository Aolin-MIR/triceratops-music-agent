import json
import os
import sys
from pathlib import Path
import pytest
from text2music.agent import configuration as config, hardware, model_sources, doctor, llm_backend, local_runtime


@pytest.fixture
def profile(tmp_path, monkeypatch):
    monkeypatch.setattr(os, 'environ', dict(os.environ))
    monkeypatch.setattr(sys, 'path', list(sys.path))
    path = tmp_path / 'runtime.json'
    config.atomic_json(path, dict(python=str(tmp_path/'runtime'/'python.exe'), reaper='/test/reaper', runs_dir=str(tmp_path/'runs'),
        model_home=str(tmp_path/'models'), device='cpu', llm_provider='disabled', setup_complete=False,
        chat_policy='auto', model_source='official'))
    monkeypatch.setattr(hardware, 'inspect_hardware', lambda: dict(system='Windows', architecture='AMD64',
        ram_total=32*hardware.GIB, ram_available=24*hardware.GIB,
        nvidia=[dict(index=0, name='Test GPU', total=16*hardware.GIB, free=15*hardware.GIB, compute_capability=8.6)]))
    monkeypatch.setattr(doctor, 'check', lambda path, **kwargs: None)
    monkeypatch.setattr(local_runtime, 'ensure_llama_cpp', lambda *args, **kwargs: None)
    return path


def invoke(path, changes, action='apply'):
    request = path.parent/'request.json'
    report = path.parent/'report.json'
    config.atomic_json(request, dict(changes=changes, action=action, revision=config.revision(path), job_id='unit-job'))
    config.worker(path, request, report)
    assert not request.exists() and not (path.parent/'candidate.json').exists()
    return config.read_config(report)


def test_public_settings_never_returns_api_key(profile):
    raw = config.read_config(profile)
    raw['api_key'] = 'private-unit-key'
    config.atomic_json(profile, raw)
    public = config.public_config(profile)
    assert public['api_key_configured']
    assert 'private-unit-key' not in json.dumps(public)
    assert public['setup_required']


@pytest.mark.parametrize('changes', [{'python': 'arbitrary'}, {'api_key': 42}, {'llm_choice': 'dynamic'},
    {'llm_choice': 'cpu'},
    {'ollama_url': 'http://remote.invalid:11434'}, {'base_url': 'https://user:key@provider.invalid'}, {'local_model': '../ bad'}])
def test_settings_validate_before_jobs(changes):
    with pytest.raises(ValueError): config.validate_changes(changes)


def test_local_compatibility_success_makes_api_optional(profile, monkeypatch):
    monkeypatch.setattr(llm_backend, 'check_chat_backend', lambda: {'provider': 'llama_cpp', 'native_tools': True})
    report = invoke(profile, {})
    saved = config.read_config(profile)
    assert report['state'] == 'complete' and saved['setup_complete']
    assert saved['llm_provider'] == 'llama_cpp' and saved['llm_device'] == 'gpu' and saved['api_requirement'] == 'optional'
    assert saved['midi_gpt_device'] == saved['stem_device'] == 'cpu'


def test_auto_local_failure_requires_api_without_committing(profile, monkeypatch):
    previous = profile.read_bytes()
    def unavailable(*args, **kwargs): raise RuntimeError('Local model could not load')
    monkeypatch.setattr(local_runtime, 'ensure_llama_cpp', unavailable)
    result = invoke(profile, {})
    assert result['state'] == 'needs_api' and result['api_requirement'] == 'required'
    assert 'could not load' in result['local_error']
    assert profile.read_bytes() == previous


def test_auto_checks_cloud_only_after_local_failure_and_redacts_key(profile, monkeypatch):
    def unavailable(*args): raise RuntimeError('Local unavailable private-unit-key')
    monkeypatch.setattr(local_runtime, 'ensure_llama_cpp', unavailable)
    calls = []
    def check():
        calls.append(os.environ['TRICERATOPS_LLM_PROVIDER'])
        return {'native_tools': True}
    monkeypatch.setattr(llm_backend, 'check_chat_backend', check)
    result = invoke(profile, {'api_key': 'private-unit-key'})
    assert result['state'] == 'complete' and calls == ['remote']
    assert config.read_config(profile)['api_requirement'] == 'required'
    assert 'private-unit-key' not in json.dumps(config.public_config(profile))


def test_explicit_local_never_attempts_cloud_on_failure(profile, monkeypatch):
    def unavailable(*args): raise RuntimeError('local failure')
    monkeypatch.setattr(local_runtime, 'ensure_llama_cpp', unavailable)
    monkeypatch.setattr(llm_backend, 'check_chat_backend', lambda: pytest.fail('cloud called'))
    previous = profile.read_bytes()
    result = invoke(profile, {'chat_policy': 'local', 'api_key': 'private-unit-key'})
    assert result['state'] == 'failed' and profile.read_bytes() == previous


def test_direct_mode_needs_no_local_runtime_and_no_api(profile, monkeypatch):
    monkeypatch.setattr(local_runtime, 'ensure_llama_cpp', lambda *a, **k: pytest.fail('local server started'))
    result = invoke(profile, {'chat_policy': 'disabled'})
    assert result['state'] == 'complete'
    assert config.read_config(profile)['api_requirement'] == 'unused'


def test_revision_conflict_never_launches_a_worker(profile):
    jobs = config.ConfigurationJobs(profile)
    with pytest.raises(RuntimeError, match='another editor'):
        jobs.start({'action': 'apply', 'settings': {}, 'revision': 'stale'}, lambda _: None)
    assert jobs.process is None


def test_prepare_installs_cuda_after_local_failure_changes_the_final_music_plan(profile, monkeypatch):
    measured = dict(system='Windows', architecture='AMD64', ram_total=32*hardware.GIB,
        ram_available=24*hardware.GIB, nvidia=[dict(index=0, name='GPU', total=16*hardware.GIB,
        free=8*hardware.GIB, compute_capability=8.6)])
    monkeypatch.setattr(hardware, 'inspect_hardware', lambda: measured)
    monkeypatch.setattr(config, 'include_resident_gpu', lambda actual, settings: actual)
    commands = []
    class Process:
        stdout = []
        def __init__(self, command, **kwargs): commands.append(command)
        def wait(self): return 0
    monkeypatch.setattr(config.subprocess, 'Popen', Process)
    from text2music.agent import download_models
    monkeypatch.setattr(download_models, 'install', lambda *args, **kwargs: None)
    def unavailable(*args): raise RuntimeError('local compatibility rejected')
    monkeypatch.setattr(local_runtime, 'ensure_llama_cpp', unavailable)
    monkeypatch.setattr(llm_backend, 'check_chat_backend', lambda: {'provider':'remote'})
    result = invoke(profile, {'api_key': 'private-unit-key'}, action='prepare')
    assert result['state'] == 'complete'
    saved = config.read_config(profile)
    assert saved['llm_provider'] == 'remote' and saved['midi_llm_device'] == 'cuda'
    assert saved['gpu_index'] == 0
    assert commands[-1][-1] == 'https://download.pytorch.org/whl/cu130'


def test_committed_verification_feedback_survives_service_restart(profile):
    job_id = 'a'*32
    saved = config.read_config(profile)
    saved.update(configuration_job=job_id, setup_complete=True)
    config.atomic_json(profile, saved)
    config.atomic_json(profile.parent/'configuration'/job_id/'report.json',
        {'state':'complete', 'detail':'Verified and applied. Devices stay fixed until the next configuration.'})
    jobs = config.ConfigurationJobs(profile)
    assert jobs.snapshot()['job']['state'] == 'complete'
    assert jobs.snapshot()['job']['id'] == job_id
    assert 'Verified and applied' in jobs.snapshot()['job']['detail']


def test_windows_cuda_setup_uses_a_new_private_target_without_overwriting_live_torch(tmp_path):
    settings = {'python':str(tmp_path/'python.exe'), 'extra_python_paths':['other-tools']}
    commands = []
    config.install_cuda_torch(settings, 'first-install', lambda detail: None, commands.append, windows=True)
    target = tmp_path/'torch-runtimes/first-install'
    assert commands[0][commands[0].index('--target')+1] == str(target)
    assert settings['extra_python_paths'] == [str(target), 'other-tools']
    metadata = target/'torch-2.13.0+cu130.dist-info/METADATA'
    metadata.parent.mkdir()
    metadata.write_text('Metadata-Version: 2.1\nName: torch\nVersion: 2.13.0+cu130\n')
    config.install_cuda_torch(settings, 'second-install', lambda detail: None,
        lambda command: pytest.fail('resident runtime was overwritten'), windows=True)
    assert not (tmp_path/'torch-runtimes/second-install').exists()


def test_failed_worker_launch_clears_sensitive_request_and_marks_failed(profile, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError('launch failure')
    monkeypatch.setattr(config.subprocess, 'Popen', fail)
    jobs = config.ConfigurationJobs(profile)
    with pytest.raises(RuntimeError, match='Could not start'):
        jobs.start({'action':'apply', 'settings':{'api_key':'private-unit-key'},
                    'revision':config.revision(profile)}, lambda _: None)
    assert jobs.process is None
    assert jobs.snapshot()['job']['state'] == 'failed'
    assert not list(profile.parent.glob('configuration/*/request.json'))


def test_cancelling_status_is_not_replaced_by_old_progress(profile):
    jobs = config.ConfigurationJobs(profile)
    jobs.job = {'state':'cancelling', 'detail':'Stopping configuration'}
    jobs.process = type('Running', (), {'poll':lambda self: None})()
    jobs.progress = profile.parent/'progress.json'
    config.atomic_json(jobs.progress, {'state':'running', 'detail':'Downloading'})
    assert jobs.snapshot()['job']['state'] == 'cancelling'


def test_corrupt_worker_report_finishes_job_and_notifies_service(profile, monkeypatch):
    import threading
    class Process:
        def __init__(self, command, **kwargs):
            Path(command[command.index('--report')+1]).write_text('{broken')
        def wait(self): return 1
        def poll(self): return 1
    monkeypatch.setattr(config.subprocess, 'Popen', Process)
    jobs = config.ConfigurationJobs(profile)
    finished = threading.Event()
    received = []
    def done(result):
        received.append(result)
        finished.set()
    jobs.start({'action':'apply', 'settings':{}, 'revision':config.revision(profile)}, done)
    assert finished.wait(5)
    assert jobs.process is None
    assert received[0]['state'] == 'failed'
    assert not list(profile.parent.glob('configuration/*/request.json'))
