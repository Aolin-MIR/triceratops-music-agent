from text2music.agent.vst_service import _host_context


def test_host_context_accepts_vst_string_time_signature():
    context = _host_context({"tempo": 96, "time_signature": "4/4", "sample_rate": 48000})

    assert "Tempo: 96.00 BPM" in context
    assert "Time Signature: 4/4" in context


def test_host_context_accepts_structured_time_signature():
    context = _host_context({"time_signature": [6, 8]})

    assert "Time Signature: 6/8" in context
