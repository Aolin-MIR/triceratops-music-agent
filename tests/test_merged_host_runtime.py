"""Regression boundaries introduced by combining Windows 1.0 and Mac AU runtime."""
import os
import subprocess
import sys
from pathlib import Path
import pytest
from text2music.agent import hardware, configuration


def test_host_absolute_runtime_launch_needs_no_inherited_pythonpath(tmp_path):
    runtime = Path(__file__).parents[1] / 'text2music/agent/runtime.py'
    env = {k: v for k,v in os.environ.items() if k != 'PYTHONPATH'}
    result = subprocess.run([sys.executable, str(runtime), '--help'], cwd=tmp_path,
                            env=env, text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert '--config' in result.stdout


def test_mac_explicit_mps_plan_is_per_model_and_cpu_is_auto():
    measured = dict(system='Darwin', architecture='arm64', ram_total=8*hardware.GIB,
                    ram_available=4*hardware.GIB, nvidia=[])
    plan = hardware.plan_devices(measured, local_chat=False,
                                 music_choices={'midi_gpt':'mps'})
    assert plan['midi_gpt_device'] == 'mps'
    assert plan['midi_llm_device'] == plan['stem_device'] == 'cpu'
    with pytest.raises(ValueError, match='Insufficient local-chat GPU memory'):
        hardware.plan_devices(measured, local_chat=True)


def test_settings_precision_validation_and_secret_redaction(tmp_path):
    configuration.validate_changes({'midi_llm_dtype':'float16'})
    with pytest.raises(ValueError):
        configuration.validate_changes({'midi_llm_dtype':'int8'})
    path = tmp_path/'runtime.json'
    configuration.atomic_json(path, {'api_key':'private-unit-only', 'midi_llm_dtype':'float16'})
    public = configuration.public_config(path)
    assert public['settings']['midi_llm_dtype'] == 'float16'
    assert 'private-unit-only' not in str(public)
