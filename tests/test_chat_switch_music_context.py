import os
import pytest
from text2music.agent.llm_backend import ChatSettings
from text2music.agent.project_memory import ProjectMemory


def test_per_message_backend_keeps_config_environment(monkeypatch):
    monkeypatch.setenv('TRICERATOPS_LLM_PROVIDER', 'remote')
    monkeypatch.setenv('TRICERATOPS_LLM_DEVICE', 'cpu')
    previous = dict(os.environ)
    local = ChatSettings.load('local')
    assert local.provider in {'ollama', 'llama_cpp'}
    assert local.device == 'gpu'
    remote = ChatSettings.load('remote')
    assert remote.provider == 'remote'
    assert ChatSettings.load().provider == 'remote'
    assert dict(os.environ) == previous
    with pytest.raises(ValueError):
        ChatSettings.load('arbitrary')


def test_music_requirements_survive_provider_switch_and_update(tmp_path):
    first = ProjectMemory(tmp_path, 'same-project')
    first.update_music_context({'tempo': 90, 'time_signature': '3/4', 'style': 'sparse piano', 'key': 'D', 'mode': 'minor'}, '90 BPM, 3/4 D minor sparse piano')
    # The next provider creates a fresh store object, not a model-specific memory.
    second = ProjectMemory(tmp_path, 'same-project')
    second.update_music_context({'tempo': 100}, 'Change tempo to 100 BPM')
    context = first.music_context()
    assert context['tempo'] == 100
    assert context['time_signature'] == '3/4'
    assert context['key'] == 'D'
    assert first.load()['music_revision'] == 2
    assert first.load()['music_updates'][1]['previous']['tempo']['value'] == 90
    assert '100' in second.context(include_summary=False)
    assert ProjectMemory(tmp_path, 'other-project').music_context() == {}
    before = first.path.read_bytes()
    with pytest.raises(ValueError):
        first.update_music_context({'tempo': -1}, 'invalid')
    assert first.path.read_bytes() == before
    second.update_music_context({'tempo': None}, 'Forget the saved tempo')
    assert 'tempo' not in first.music_context()
    assert first.music_context()['key'] == 'D'
    assert first.recall('')['music_context'] == first.music_context()
    assert first.recall('')['music_revision'] == 3
