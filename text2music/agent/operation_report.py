"""Factual completion reports for explicit plug-in operations."""
from __future__ import annotations
import json


def operation_report(action: str, trace: list[dict]) -> tuple[str, str]:
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
    else:
        reply = str(data.get("reply") or json.dumps(data, ensure_ascii=False, default=str))
    midi = data.get("midi_windows") or data.get("midi")
    if midi:
        reply += "\nMIDI：" + str(midi)
    return reply, ""
