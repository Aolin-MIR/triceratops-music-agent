import json
import pytest
from text2music.agent import model_sources as sources
from text2music.agent.hardware import GIB, plan_devices


@pytest.mark.parametrize('country,endpoint', [('CN', sources.CHINA_MIRROR), ('US', sources.OFFICIAL), ('HK', sources.OFFICIAL), ('', sources.OFFICIAL)])
def test_model_route_uses_public_country_only(country, endpoint):
    route = sources.model_sources('auto', {'country': country})
    assert route['hf_endpoint'] == endpoint
    assert route['local_chat_models'] == 'official-model-registry'
    assert route['scope'] == 'model-downloads-only'


def test_manual_model_source_does_not_query_ip(monkeypatch):
    monkeypatch.setattr(sources, 'detect_country', lambda: pytest.fail('manual mode leaked an IP query'))
    assert sources.model_sources('china')['hf_endpoint'] == sources.CHINA_MIRROR
    assert sources.model_sources('official')['hf_endpoint'] == sources.OFFICIAL
    with pytest.raises(ValueError):
        sources.model_sources('arbitrary')


def test_detection_does_not_store_ip_and_bypasses_application_proxy(monkeypatch):
    class Reply:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit): return b'{"country_code":"CN","ip":"203.0.113.12","city":"private"}'
    class Opener:
        def open(self, request, timeout):
            assert timeout <= 4
            return Reply()
    def build(handler):
        assert handler.proxies == {}
        return Opener()
    monkeypatch.setattr(sources, 'build_opener', build)
    result = sources.detect_country()
    assert result['country'] == 'CN'
    assert 'ip' not in result and 'city' not in result


def test_failed_detection_reports_unknown_without_guessing_chinese_locale(monkeypatch):
    class Opener:
        def open(self, *args, **kwargs): raise TimeoutError()
    monkeypatch.setattr(sources, 'build_opener', lambda *a: Opener())
    route = sources.model_sources('auto')
    assert route['geolocation'] == 'unavailable' and route['country'] == ''
    assert route['hf_endpoint'] == sources.OFFICIAL and route['reason']


def hardware(ram=28, free=16):
    return {'system': 'Windows', 'architecture': 'AMD64', 'ram_total': int(ram*GIB),
            'ram_available': int(min(20,ram-3)*GIB), 'nvidia': [{'index': 0, 'name': 'test GPU', 'free': int(free*GIB),
              'total': int(16*GIB), 'compute_capability': 8.6}]}


def test_joint_gpu_budget_and_fixed_cpu_light_models():
    plan = plan_devices(hardware())
    assert plan['llm_device'] == 'gpu' and plan['midi_llm_device'] == 'cuda'
    assert plan['stem_device'] == plan['midi_gpt_device'] == 'cpu'
    assert plan['local_feasible']


def test_cloud_chat_reserves_no_llm_gpu_budget():
    plan = plan_devices(hardware(free=8), local_chat=False)
    assert plan['midi_llm_device'] == 'cuda'
    plan = plan_devices(hardware(free=8))
    assert plan['llm_device'] == 'gpu' and plan['midi_llm_device'] == 'cpu'


def test_local_chat_cannot_be_selected_for_cpu():
    with pytest.raises(ValueError, match='CPU placement is disabled'):
        plan_devices(hardware(ram=15.8, free=8), llm_choice='cpu')
from text2music.agent import model_sources as sources

def test_mirror_redirect_is_reported_as_official(monkeypatch):
    class Reply:
        url = 'https://huggingface.co/repo/resolve/revision/config.json'
        headers = {'X-Repo-Commit': 'revision'}
        def __enter__(self): return self
        def __exit__(self, *args): pass
    class Opener:
        def open(self, *args, **kwargs): return Reply()
    monkeypatch.setattr(sources, 'build_opener', lambda *a: Opener())
    result = sources.resolve_mirror(sources.CHINA_MIRROR, 'repo', 'revision', 'config.json')
    assert result['endpoint'] == sources.OFFICIAL
    assert 'redirects overseas' in result['reason']


def test_mirror_must_serve_the_exact_pinned_revision(monkeypatch):
    class Reply:
        url = 'https://hf-mirror.com/repo/resolve/revision/config.json'
        headers = {'X-Repo-Commit': 'wrong-revision'}
        def __enter__(self): return self
        def __exit__(self, *args): pass
    class Opener:
        def open(self, *args, **kwargs): return Reply()
    monkeypatch.setattr(sources, 'build_opener', lambda *a: Opener())
    assert sources.resolve_mirror(sources.CHINA_MIRROR, 'repo', 'revision', 'config.json')['endpoint'] == sources.OFFICIAL
    Reply.headers = {'X-Repo-Commit': 'revision'}
    assert sources.resolve_mirror(sources.CHINA_MIRROR, 'repo', 'revision', 'config.json')['endpoint'] == sources.CHINA_MIRROR


def test_manual_cpu_music_is_budgeted_before_local_chat_is_accepted():
    measured = hardware(ram=16, free=16)
    measured['ram_available'] = int(8*GIB)
    plan = plan_devices(measured, music_choices={'midi_llm': 'cpu'})
    assert plan['midi_llm_device'] == 'cpu'
    assert plan['budgets']['system_ram'] == int(10*GIB)
    assert not plan['local_feasible']


def test_manual_cuda_music_has_priority_over_automatic_chat_allocation():
    plan = plan_devices(hardware(free=8), local_chat=False, music_choices={'midi_llm': 'cuda'})
    assert plan['midi_llm_device'] == 'cuda' and plan['llm_device'] == 'cpu'


def test_combined_explicit_gpu_choices_cannot_overcommit():
    with pytest.raises(ValueError, match='local-chat GPU'):
        plan_devices(hardware(free=8), llm_choice='gpu', music_choices={'midi_llm': 'cuda'})


def test_explicit_cuda_cannot_be_silently_changed_to_cpu():
    measured = hardware()
    measured['nvidia'] = []
    with pytest.raises(ValueError, match='CUDA device'):
        plan_devices(measured, music_choices={'stem': 'cuda'})


def test_remote_mode_does_not_budget_cpu_ram_for_unused_local_model():
    plan = plan_devices(hardware(), local_chat=False, music_choices={'midi_llm': 'cpu'})
    assert plan['budgets']['local_llm'] == 0
    assert plan['budgets']['system_ram'] == int(9*GIB)


def test_resident_llama_cpp_weights_are_credited_once_in_the_joint_plan(monkeypatch, tmp_path):
    import os
    from text2music.agent.configuration import include_resident_gpu
    from text2music.agent import llm_backend
    model_path = tmp_path/'qwen.gguf'
    with model_path.open('wb') as model_file:
        model_file.truncate(3*GIB)
    config_path = tmp_path/'native-models'
    marker_path = tmp_path/'llama-cpp-gpu-server.json'
    marker_path.write_text(json.dumps({'pid': os.getpid(), 'model': 'qwen3.5:4b-q4_K_M',
        'model_path': str(model_path), 'resident_gpu_bytes': model_path.stat().st_size,
        'gpu_index': 0, 'gpu_name': 'test GPU', 'all_layers_on_gpu': True}))
    monkeypatch.setattr(llm_backend, 'residency', lambda settings: {
        'provider':'llama_cpp', 'model':settings.model, 'resident':True})
    measured = hardware(free=10.5)
    adjusted = include_resident_gpu(measured, {'llm_provider':'llama_cpp',
        'local_model':'qwen3.5:4b-q4_K_M', 'model_home':str(config_path),
        'llama_cpp_url':'http://127.0.0.1:1234/v1'})
    assert measured['nvidia'][0]['free'] == int(10.5*GIB)
    assert adjusted['nvidia'][0]['resident_local_bytes'] == model_path.stat().st_size
    plan = plan_devices(adjusted)
    assert plan['llm_device'] == 'gpu' and plan['midi_llm_device'] == 'cuda'
    assert plan['budgets']['local_llm'] == int(5.5*GIB)


def test_no_resident_credit_is_given_for_unidentifiable_multi_gpu_placement(monkeypatch):
    from text2music.agent.configuration import include_resident_gpu
    from text2music.agent import llm_backend
    monkeypatch.setattr(llm_backend, 'residency', lambda *args: pytest.fail('ambiguous placement queried'))
    measured = hardware()
    measured['nvidia'].append(dict(measured['nvidia'][0], index=1))
    assert include_resident_gpu(measured, {}) == measured
