"""Safety and source routing tests; real network checks are recorded separately."""
import io
import json
import subprocess
import tarfile
from pathlib import Path
import pytest
from text2music.agent import macos_bootstrap as bootstrap


def test_source_choices_retain_fixed_official_asset():
    url = bootstrap.OLLAMA_URL
    assert bootstrap.sources(url, 'official') == [url]
    assert bootstrap.sources(url, 'auto')[0] == url
    assert bootstrap.sources(url, 'china')[-1] == url
    assert all(source.endswith(url) for source in bootstrap.sources(url, 'china'))
    with pytest.raises(ValueError): bootstrap.sources(url, 'unknown')


@pytest.mark.parametrize('name,link', [('../escape', None), ('/absolute', None), ('link', '../../escape')])
def test_extractor_rejects_escaping_members_before_writing(tmp_path, name, link):
    archive = tmp_path/'bad.tar.gz'
    with tarfile.open(archive, 'w:gz') as stream:
        member = tarfile.TarInfo(name)
        if link:
            member.type = tarfile.SYMTYPE; member.linkname = link
        stream.addfile(member)
    target = tmp_path/'extract'; target.mkdir()
    with pytest.raises(ValueError): bootstrap.extract(archive, target)
    assert not list(target.iterdir())


def test_corrupt_download_never_becomes_executable_cache(tmp_path, monkeypatch):
    calls = []
    def fake_curl(command, **kwargs):
        calls.append(command[-1])
        Path(command[command.index('--output')+1]).write_bytes(b'corrupt')
    monkeypatch.setattr(subprocess, 'run', fake_curl)
    with pytest.raises(RuntimeError, match='All runtime download sources failed'):
        bootstrap.download(bootstrap.OLLAMA_URL, 'a'*64, 7, tmp_path, 'china', lambda _: None)
    assert len(calls) == 3
    assert not list(tmp_path.iterdir())


def test_corrupt_mirror_can_fall_back_but_only_matching_hash_is_kept(tmp_path, monkeypatch):
    data = b'official bytes'; calls = []
    def fake_curl(command, **kwargs):
        calls.append(command[-1]); path = Path(command[command.index('--output')+1])
        path.write_bytes(b'wrong' if len(calls)==1 else data)
    monkeypatch.setattr(subprocess, 'run', fake_curl)
    import hashlib
    result = bootstrap.download(bootstrap.OLLAMA_URL, hashlib.sha256(data).hexdigest(), len(data), tmp_path, 'china', lambda _: None)
    assert result.read_bytes() == data
    assert len(calls) == 2


def test_modified_installed_runtime_is_rejected(tmp_path):
    root = tmp_path/'runtimes'/('ollama-'+bootstrap.OLLAMA_VERSION);root.mkdir(parents=True)
    (root/'ollama').write_bytes(b'changed')
    (root/'triceratops-runtime.json').write_text(json.dumps({'archive_sha256': bootstrap.OLLAMA_SHA256, 'files': {'ollama': '0'*64}}))
    with pytest.raises(RuntimeError, match='runtime changed'):
        bootstrap.install_ollama(tmp_path)
