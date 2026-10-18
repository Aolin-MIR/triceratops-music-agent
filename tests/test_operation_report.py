from text2music.agent.operation_report import operation_report


def test_continuation_reports_only_verified_counts_and_file():
    reply, error = operation_report("continue_midi", [{"tool": "continue_midi", "state": "completed",
        "result": {"original_bars": 3, "added_bars": 4, "midi_windows": "E:\\out.mid"}}])
    assert "总计 7 小节" in reply and "E:\\out.mid" in reply
    assert not error and "major" not in reply


def test_midi_report_uses_exact_note_names_and_time_resolution():
    reply, error = operation_report("analyze_selected_midi", [{"tool": "analyze_selected_midi", "state": "completed",
        "result": {"notes": 12, "pitch_min_name": "F4", "pitch_min": 65, "pitch_max_name": "Eb5", "pitch_max": 75,
                   "ticks_per_quarter": 220, "median_onset_gap_ppq": 97, "most_common_pitch_class": "Bb"}}])
    assert "F4（65）" in reply and "Eb5（75）" in reply and "220 ticks" in reply
    assert "不足以确定调性" in reply and not error


def test_failed_button_operation_cannot_report_success():
    reply, error = operation_report("audio_to_midi", [{"tool": "audio_to_midi", "state": "failed",
                                                   "result": {"error": "No audio attached"}}])
    assert error == "No audio attached" and reply.startswith("操作未完成")
    assert operation_report("audio_to_midi", [])[1]


def test_english_continuation_report_keeps_verified_counts():
    reply,error=operation_report("continue_midi",[{"tool":"continue_midi","state":"completed",
        "result":{"original_bars":3,"added_bars":4,"midi_windows":"C:/out.mid"}}],language="en")
    assert "total: 7 bars" in reply and "C:/out.mid" in reply and not error
    assert "原" not in reply


def test_english_failure_never_claims_success():
    reply,error=operation_report("audio_to_midi",[{"tool":"audio_to_midi","state":"failed",
        "result":{"error":"No audio attached"}}],language="en")
    assert reply.startswith("Operation did not complete") and error=="No audio attached"


def test_capability_report_is_bilingual_and_limited_to_installed_tools():
    trace = [{"tool": "list_capabilities", "state": "completed", "result": {
        "capabilities": {"generate_draft": "Generate MIDI", "transform_midi": "Edit MIDI",
                         "analyze_audio": "Analyze audio"}}}]
    zh, error = operation_report("list_capabilities", trace, language="zh")
    en, english_error = operation_report("list_capabilities", trace, language="en")
    assert "创作 MIDI" in zh and "调整力度" in zh and "音频" in zh
    assert "歌词" not in zh and "lyrics" not in en.lower()
    assert "Create MIDI" in en and "velocity" in en.lower() and "audio" in en.lower()
    assert not error and not english_error
