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
    if action == "list_capabilities":
        if language == "en":
            capabilities = data.get("capabilities", {})
            labels = {
                "generate_draft": "Create MIDI from a musical idea",
                "transform_midi": "Transpose, change velocity, quantize to sixteenth notes, repeat once, or add power chords",
                "continue_midi": "Continue a loaded MIDI with new bars",
                "infill_midi": "Fill selected MIDI bars/tracks using MIDI-GPT",
                "analyze_selected_midi": "Analyze loaded MIDI",
                "analyze_audio": "Analyze loaded audio",
                "separate_stems": "Separate loaded audio into stems",
                "audio_to_midi": "Transcribe loaded audio to MIDI",
                "inspect_project": "Read REAPER tempo and project context",
                "undo": "Undo the previous MIDI edit",
                "accept": "Keep a result and save feedback",
                "reject": "Reject a result and save feedback",
                "search_knowledge": "Search indexed manuals, project notes, and music knowledge",
                "remember_fact": "Remember an explicit project preference",
                "forget_fact": "Forget a saved project fact",
                "status": "Check task status",
                "cancel": "Cancel an active task",
            }
            items = [label for name, label in labels.items() if name in capabilities]
            reply = "I can help with these REAPER music tasks:\n• " + "\n• ".join(items)
            reply += "\n\nStart with a button, or describe the result you want in your own words. Load MIDI/audio first for file-based actions. I will say when a request is outside this scope."
        else:
            capabilities = data.get("capabilities", {})
            labels = {
                "generate_draft": "根据音乐想法创作 MIDI",
                "transform_midi": "移调、调整力度、十六分音符量化、重复一次或添加强力和弦",
                "continue_midi": "为已载入的 MIDI 续写新小节",
                "infill_midi": "用 MIDI-GPT 填充指定 MIDI 小节或声部",
                "analyze_selected_midi": "分析已载入的 MIDI",
                "analyze_audio": "分析已载入的音频",
                "separate_stems": "将已载入的音频分轨",
                "audio_to_midi": "将已载入的音频转成 MIDI",
                "inspect_project": "读取 REAPER 速度和工程上下文",
                "undo": "撤销上一次 MIDI 修改",
                "accept": "保留结果并记录反馈",
                "reject": "拒绝结果并记录反馈",
                "search_knowledge": "搜索已索引的手册、工程笔记和音乐知识",
                "remember_fact": "记住明确提出的工程偏好",
                "forget_fact": "删除已保存的工程信息",
                "status": "查看任务状态",
                "cancel": "取消正在执行的任务",
            }
            items = [label for name, label in labels.items() if name in capabilities]
            reply = "我可以在 REAPER 音乐工作流中帮你：\n• " + "\n• ".join(items)
            reply += "\n\n可以点功能按钮，也可以直接用自己的话描述目标。处理文件前先载入 MIDI 或音频；超出这些范围的请求我会明确说明。"
    elif action == "continue_midi":
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
    if action == "list_capabilities":
        capabilities = data.get("capabilities", {})
        labels = {
            "generate_draft": "Create MIDI from a musical idea",
            "transform_midi": "Transpose, change velocity, quantize, repeat once, or add power chords",
            "continue_midi": "Continue loaded MIDI with new bars",
            "infill_midi": "Fill selected MIDI bars/tracks using MIDI-GPT",
            "analyze_selected_midi": "Analyze loaded MIDI",
            "analyze_audio": "Analyze loaded audio",
            "separate_stems": "Separate loaded audio into stems",
            "audio_to_midi": "Transcribe loaded audio to MIDI",
            "inspect_project": "Read REAPER tempo and project context",
            "undo": "Undo the previous MIDI edit",
            "accept": "Keep a result and save feedback",
            "reject": "Reject a result and save feedback",
            "search_knowledge": "Search indexed manuals, project notes, and music knowledge",
            "remember_fact": "Remember an explicit project preference",
            "forget_fact": "Forget a saved project fact",
            "status": "Check task status",
            "cancel": "Cancel an active task",
        }
        items = [label for name, label in labels.items() if name in capabilities]
        reply = "I can help with these REAPER music tasks:\n• " + "\n• ".join(items)
        reply += "\n\nUse a button or describe the result in your own words. Load MIDI/audio first for file-based actions. I will state when a request is outside this scope."
    elif action == "continue_midi":
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
