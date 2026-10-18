import json

from text2music.agent import runtime
from text2music.agent.model_policy import resolve_policy


def test_low_memory_auto_policy_is_conservative():
    resolved = resolve_policy({}, {
        "platform": "Darwin", "architecture": "arm64", "chip": "Apple A18 Pro",
        "unified_memory_gb": 8.0, "profile": "mac-low-memory",
    })
    assert resolved["midi_llm_device"] == "cpu"
    assert resolved["midi_llm_dtype"] == "float16"
    assert resolved["midi_gpt_device"] == "cpu"
    assert resolved["chat_deployment"] == "remote"


def test_custom_policy_can_split_devices_per_model():
    resolved = resolve_policy({
        "model_policy": "custom", "device": "cpu", "midi_gpt_device": "mps",
        "midi_llm_dtype": "float32", "audio_device": "cpu",
    }, {"profile": "mac-low-memory"})
    assert resolved["midi_llm_device"] == "cpu"
    assert resolved["midi_gpt_device"] == "mps"
    assert resolved["midi_llm_dtype"] == "float32"


def test_custom_policy_keeps_auto_for_unpinned_models():
    resolved = resolve_policy({"model_policy": "custom", "device": "auto",
                               "midi_llm_device": "auto", "midi_gpt_device": "auto",
                               "midi_llm_dtype": "auto"},
                              {"profile": "mac-low-memory"})
    assert resolved["midi_llm_device"] == "cpu"
    assert resolved["midi_gpt_device"] == "cpu"
    assert resolved["midi_llm_dtype"] == "float16"


def test_legacy_device_override_treats_auto_gpt_as_unpinned():
    resolved = resolve_policy({"model_policy": "custom", "device": "cpu",
                               "midi_gpt_device": "auto"},
                              {"profile": "mac-balanced"})
    assert resolved["midi_llm_device"] == "cpu"
    assert resolved["midi_gpt_device"] == "cpu"


def test_verified_local_qwen_endpoint_can_be_selected_explicitly():
    resolved = resolve_policy({
        "model_policy": "auto", "local_chat_available": True,
        "local_chat_model": "Qwen3.5-4B", "local_chat_base_url": "http://127.0.0.1:8000/v1",
    }, {"profile": "mac-low-memory"})
    assert resolved["chat_deployment"] == "local-openai"


def test_runtime_exports_resolved_per_model_devices(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime.os, "environ", dict(runtime.os.environ))
    monkeypatch.setattr(runtime.sys, "path", list(runtime.sys.path))
    config = tmp_path / "runtime.json"
    config.write_text(json.dumps({
        "python": "/custom/python", "runs_dir": str(tmp_path / "runs"),
        "model_home": str(tmp_path / "models"), "reaper": "/custom/reaper",
        "device": "auto", "model_policy": "auto",
    }))
    result = runtime.configure(config)
    assert result["resolved_model_policy"]["midi_llm_device"] == "cpu"
    assert runtime.os.environ["TRICERATOPS_DEVICE"] == "cpu"
    assert runtime.os.environ["TRICERATOPS_MIDI_GPT_DEVICE"] in {"cpu", "mps"}


def test_runtime_selects_verified_local_qwen_endpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime.os, "environ", dict(runtime.os.environ))
    monkeypatch.setattr(runtime.sys, "path", list(runtime.sys.path))
    config = tmp_path / "runtime.json"
    config.write_text(json.dumps({
        "python": "/custom/python", "runs_dir": str(tmp_path / "runs"),
        "model_home": str(tmp_path / "models"), "reaper": "/custom/reaper",
        "device": "auto", "model_policy": "auto", "local_chat_available": True,
        "local_chat_base_url": "http://127.0.0.1:9123/v1", "local_chat_model": "Qwen4B-local",
    }))
    result = runtime.configure(config)
    assert result["resolved_model_policy"]["chat_deployment"] == "local-openai"
    assert runtime.os.environ["QWEN_BASE_URL"] == "http://127.0.0.1:9123/v1"
    assert runtime.os.environ["QWEN_MODEL"] == "Qwen4B-local"
    assert runtime.os.environ["QWEN_API_KEY"] == "local"
