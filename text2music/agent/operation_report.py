"""Factual completion reports for explicit plug-in operations."""
from __future__ import annotations
import json


def operation_report(action: str, trace: list[dict], *, language: str = "zh") -> tuple[str, str]:
    if language not in {"zh", "en"}:
        raise ValueError("language must be zh or en")
    if language == "en":
        return _english_report(action, trace)
    events = [event for event in trace if event.get("tool") == action]
    if not events or events[-1].get("state") != "completed":
        detail = str(events[-1].get("result", {}).get("error", "工具没有执行完成")) if events else "工具没有执行完成"
        return "操作未完成：" + detail, detail
    data = events[-1]["result"]
    if action == "continue_midi":
        reply = (f"MIDI-GPT 已新生成 {data['added_bars']} 小节。原片段 {data['original_bars']} 小节，"
                 f"总计 {data['original_bars'] + data['added_bars']} 小节。\n"
                 "原 MIDI 事件流完整保留，新生成内容追加在原片段之后。")
    elif action == "transform_midi":
        reply = f"MIDI 修改完成：{data['original_notes']} → {data['output_notes']} 个音符。"
        if data.get("quantized"):
            reply += "\n音符起点和终点已对齐十六分音符网格。"
        if data.get("transposed"):
            reply += f"\n移调：{data['transposed']} 个半音。"
    elif action == "separate_stems":
        reply = f"分轨完成，已保存 {len(data['files'])} 个真实音频文件：\n" + "\n".join(data["files"])
    elif action == "audio_to_midi":
        reply = "音频转 MIDI 已完成。"
    elif action == "analyze_audio":
        reply = (f"音频分析完成：时长 {data['duration_seconds']} 秒。\n"
                 f"估计速度：{data['tempo_bpm']} BPM；估计调性：{data['key']}。\n"
                 f"检测到 {data['beat_count']} 个节拍、{data['onset_count']} 个起音。\n"
                 f"RMS 均值：{data['rms_mean']}；峰值：{data['rms_peak']}。\n"
                 "分段边界（秒）：" + json.dumps(data["section_boundaries_seconds"]))
    elif action == "analyze_selected_midi":
        reply = (f"MIDI 分析完成：{data['notes']} 个音符。\n"
                 f"音域：{data['pitch_min_name']}（{data['pitch_min']}）至 "
                 f"{data['pitch_max_name']}（{data['pitch_max']}）。\n"
                 f"每四分音符 {data['ticks_per_quarter']} ticks；起音间隔中位数 "
                 f"{data['median_onset_gap_ppq']} ticks。\n"
                 "最常出现的音级：" + str(data['most_common_pitch_class']) + "。这不足以确定调性。")
    elif action in {"accept", "reject", "undo"}:
        reply = {"accept": "已保留这个版本，并记录偏好。", "reject": "已记录不喜欢此版本的反馈。",
                 "undo": "已在插件中恢复上一个 MIDI 版本。"}[action]
    else:
        reply = str(data.get("reply") or json.dumps(data, ensure_ascii=False, default=str))
    midi = data.get("midi_windows") or data.get("midi")
    if midi:
        reply += "\nMIDI：" + str(midi)
    return reply, ""


def _english_report(action: str, trace: list[dict]) -> tuple[str, str]:
    events = [event for event in trace if event.get("tool") == action]
    if not events or events[-1].get("state") != "completed":
        detail = str(events[-1].get("result", {}).get("error", "The tool did not complete")) if events else "The tool did not complete"
        return "Operation did not complete: " + detail, detail
    data = events[-1]["result"]
    if action == "continue_midi":
        reply = (f"MIDI-GPT generated {data['added_bars']} new bars. Original: {data['original_bars']} bars; "
                 f"total: {data['original_bars'] + data['added_bars']} bars.\n"
                 "Original MIDI event streams were preserved; new content was appended.")
    elif action == "transform_midi":
        reply = f"MIDI edit complete: {data['original_notes']} -> {data['output_notes']} notes."
        if data.get("quantized"):
            reply += "\nNote starts and ends were aligned to the sixteenth-note grid."
        if data.get("transposed"):
            reply += f"\nTransposition: {data['transposed']} semitones."
    elif action == "separate_stems":
        reply = f"Separation complete. Saved {len(data['files'])} audio files:\n" + "\n".join(data["files"])
    elif action == "audio_to_midi":
        reply = "Audio-to-MIDI transcription complete."
    elif action == "analyze_audio":
        reply = (f"Audio analysis complete. Duration: {data['duration_seconds']} seconds.\n"
                 f"Estimated tempo: {data['tempo_bpm']} BPM; estimated key: {data['key']}.\n"
                 f"Detected {data['beat_count']} beats and {data['onset_count']} onsets.\n"
                 f"RMS mean: {data['rms_mean']}; peak: {data['rms_peak']}.\n"
                 "Section boundaries (seconds): " + json.dumps(data["section_boundaries_seconds"]))
    elif action == "analyze_selected_midi":
        reply = (f"MIDI analysis complete: {data['notes']} notes.\n"
                 f"Range: {data['pitch_min_name']} ({data['pitch_min']}) to {data['pitch_max_name']} ({data['pitch_max']}).\n"
                 f"Ticks per quarter: {data['ticks_per_quarter']}; median onset gap: {data['median_onset_gap_ppq']} ticks.\n"
                 f"Most frequent pitch class: {data['most_common_pitch_class']}. This does not establish the key.")
    elif action in {"accept", "reject", "undo"}:
        reply = {"accept": "Version kept; preference saved.", "reject": "Version rejected; feedback saved.",
                 "undo": "The previous MIDI version is restored in the plug-in."}[action]
    else:
        reply = str(data.get("reply") or json.dumps(data, ensure_ascii=False, default=str))
    midi = data.get("midi_windows") or data.get("midi")
    if midi:
        reply += "\nMIDI: " + str(midi)
    return reply, ""
