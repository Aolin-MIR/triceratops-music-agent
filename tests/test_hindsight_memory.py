import json

import pytest

from text2music.agent.project_memory import ProjectMemory


def test_legacy_facts_move_once_and_keep_exact_music_state(tmp_path, fake_hindsight):
    memory = ProjectMemory(tmp_path, 'one-project')
    memory.path.parent.mkdir(parents=True)
    memory.path.write_text(json.dumps({
        'facts': [{'fact': 'Keep the guitar clean', 'category': 'constraint'}],
        'music_context': {'tempo': {'value': 92, 'source': 'user', 'revision': 1}},
        'music_revision': 1,
    }), encoding='utf-8')
    assert memory.recall('')['facts'][0]['fact'] == 'Keep the guitar clean'
    assert 'facts' not in memory.load()
    assert memory.music_context() == {'tempo': 92}
    assert len(fake_hindsight['one-project'].documents()) == 1
    assert ProjectMemory(tmp_path, 'other-project').recall('')['facts'] == []


def test_failed_migration_retains_source_data(tmp_path, fake_hindsight, monkeypatch):
    memory = ProjectMemory(tmp_path, 'one-project')
    memory.path.parent.mkdir(parents=True)
    memory.path.write_text(json.dumps({'facts': [{'fact': 'No drums'}]}), encoding='utf-8')
    bank = memory._store()
    monkeypatch.setattr(bank, 'retain', lambda *args: (_ for _ in ()).throw(RuntimeError('retain failed')))
    with pytest.raises(RuntimeError, match='retain failed'):
        memory.recall('')
    assert memory.load()['facts'][0]['fact'] == 'No drums'
