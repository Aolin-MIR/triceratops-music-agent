"""macOS installer settings preservation and local file permissions."""
import importlib.util
import json
import os
from pathlib import Path
import pytest


@pytest.mark.skipif(os.name == "nt", reason="macOS installer permissions")
def test_installer_preserves_settings_and_restricts_config_and_backup(tmp_path):
    script = Path(__file__).parents[1] / 'vst3/installer/configure_macos.py'
    spec = importlib.util.spec_from_file_location('configure_macos', script)
    module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    original = dict(python='/custom/arm-python', runs_dir='/custom/runs', model_home='/custom/models',
                    device='mps', api_key='local-test-value', base_url='https://example.test/v1',
                    chat_model='custom-model', extra_python_paths=['/custom/lib'])
    config = tmp_path/'runtime.json';config.write_text(json.dumps(original))
    result = module.write_config(tmp_path, Path('/new/python'))
    assert all(result[k] == v for k,v in original.items())
    assert config.stat().st_mode & 0o777 == 0o600
    backup = next(tmp_path.glob('runtime.backup-*.json'))
    assert json.loads(backup.read_text()) == original
    assert backup.stat().st_mode & 0o777 == 0o600
