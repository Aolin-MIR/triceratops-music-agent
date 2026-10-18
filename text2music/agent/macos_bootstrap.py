"""Small, verified online bootstrap for the private Apple Silicon chat runtime.

Mirrors transport public release bytes only. They never receive user settings.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import time

OLLAMA_VERSION = '0.40.6'
OLLAMA_URL = f'https://github.com/ollama/ollama/releases/download/v{OLLAMA_VERSION}/ollama-darwin.tgz'
OLLAMA_SHA256 = 'b2b55434865a668decb494110d7fd970eed3ecc8837be2872f672ccbb95df974'
OLLAMA_SIZE = 174459907
PROXIES = ('https://ghfast.top/', 'https://gh-proxy.com/')


def sources(url: str, mode: str = 'auto') -> list[str]:
    if mode not in {'auto', 'official', 'china'}:
        raise ValueError('Download source must be auto, official or china')
    mirrors = [prefix + url for prefix in PROXIES]
    return [url] if mode == 'official' else (mirrors + [url] if mode == 'china' else [url] + mirrors)


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def download(url: str, sha256: str, size: int, cache: Path, mode: str, report=print) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / (sha256 + '.tar.gz')
    if target.is_file() and target.stat().st_size == size and digest(target) == sha256:
        report('Using SHA-256 verified download cache')
        return target
    failures = []
    for source in sources(url, mode):
        descriptor, temporary = tempfile.mkstemp(prefix='.download-', dir=cache)
        os.close(descriptor)
        partial = Path(temporary)
        try:
            report('Downloading runtime: ' + source)
            subprocess.run(['/usr/bin/curl', '--fail', '--location', '--proto', '=https',
                            '--proto-redir', '=https', '--connect-timeout', '15',
                            '--speed-limit', '1024', '--speed-time', '30', '--max-time', '900',
                            '--retry', '1', '--output', str(partial), source], check=True)
            if partial.stat().st_size != size or digest(partial) != sha256:
                raise RuntimeError('Downloaded size or SHA-256 differs from the pinned official release')
            os.replace(partial, target)
            return target
        except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
            failures.append(f'{source}: {type(exc).__name__}: {exc}')
            report('Source failed; trying the next verified source')
        finally:
            partial.unlink(missing_ok=True)
    raise RuntimeError('All runtime download sources failed. Retry the installer or select another source.\n' + '\n'.join(failures))


def extract(archive: Path, destination: Path) -> None:
    """Reject escaping paths/links and special files before extracting any member."""
    root = destination.resolve()
    with tarfile.open(archive, 'r:gz') as stream:
        members = stream.getmembers()
        for member in members:
            path = root / member.name
            if not path.resolve().is_relative_to(root) or member.name.startswith('/'):
                raise ValueError('Unsafe archive path')
            if member.isdev() or member.isfifo():
                raise ValueError('Special archive entries are unsupported')
            if member.issym() or member.islnk():
                link = (path.parent if member.issym() else root) / member.linkname
                if not link.resolve().is_relative_to(root):
                    raise ValueError('Unsafe archive link')
        # The archive has an official pinned hash, and all paths were validated.
        stream.extractall(root, members=members, filter='data')


def install_ollama(data: Path, mode: str = 'auto', report=print) -> Path:
    destination = data / 'runtimes' / ('ollama-' + OLLAMA_VERSION)
    marker = destination / 'triceratops-runtime.json'
    if marker.is_file():
        record = json.loads(marker.read_text())
        if (record.get('archive_sha256') == OLLAMA_SHA256
                and all((destination / name).is_file() and digest(destination / name) == value
                        for name, value in record.get('files', {}).items())
                and record.get('files', {}).get('ollama')):
            return destination
        raise RuntimeError('Installed private runtime changed; keep it for diagnosis and reinstall into a clean directory')
    archive = download(OLLAMA_URL, OLLAMA_SHA256, OLLAMA_SIZE, data / 'downloads', mode, report)
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.ollama-', dir=destination.parent))
    try:
        extract(archive, stage)
        binary = stage / 'ollama'
        architectures = subprocess.check_output(['/usr/bin/lipo', '-archs', str(binary)], text=True)
        if 'arm64' not in architectures.split():
            raise RuntimeError('Downloaded runtime does not contain native ARM64 code')
        subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(binary)], check=True)
        files = {str(path.relative_to(stage)): digest(path) for path in stage.rglob('*') if path.is_file()}
        (stage / marker.name).write_text(json.dumps({'version': OLLAMA_VERSION,
            'archive_sha256': OLLAMA_SHA256, 'files': files, 'installed_at': int(time.time())}, indent=2))
        os.rename(stage, destination)
        return destination
    finally:
        if stage.exists():
            shutil.rmtree(stage)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--source', choices=('auto', 'official', 'china'), default='auto')
    args = parser.parse_args()
    print(install_ollama(args.data, args.source))
