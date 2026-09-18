"""Deterministic MIDI analysis and selection transformations."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from mido import MetaMessage, MidiFile, MidiTrack


PITCH_CLASSES = ("C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")


def analyze_selection(path: Path) -> dict[str, Any]:
    if path.suffix.lower() in {".mid", ".midi"}:
        midi = MidiFile(path)
        notes = []
        for index, track in enumerate(midi.tracks):
            tick = 0
            active = {}
            for event in track:
                tick += event.time
                if event.type == "note_on" and event.velocity > 0:
                    note = {"pitch": event.note, "velocity": event.velocity, "channel": event.channel,
                            "start_ppq": tick, "end_ppq": tick, "take_guid": str(index)}
                    notes.append(note)
                    active.setdefault((event.channel, event.note), []).append(note)
                elif event.type == "note_off" or (event.type == "note_on" and event.velocity == 0):
                    pending = active.get((event.channel, event.note), [])
                    if pending:
                        pending.pop(0)["end_ppq"] = tick
        data = {"notes": notes, "tracks": [track.name or str(i) for i, track in enumerate(midi.tracks)],
                "start_time": 0, "end_time": midi.length}
    else:
        data = json.loads(path.read_text(encoding="utf-8"))
    notes = [note for note in data.get("notes", []) if isinstance(note, dict)]
    pitches = [int(note["pitch"]) for note in notes]
    starts = sorted(float(note["start_ppq"]) for note in notes)
    intervals = [round(starts[index + 1] - starts[index], 3) for index in range(len(starts) - 1)]
    pitch_classes = Counter(pitch % 12 for pitch in pitches)
    likely_root = pitch_classes.most_common(1)[0][0] if pitch_classes else 0
    channels = Counter(int(note.get("channel", 0)) for note in notes)
    by_take: dict[str, list[dict[str, Any]]] = {}
    for note in notes:
        by_take.setdefault(str(note.get("take_guid", "unknown")), []).append(note)
    roles: list[dict[str, Any]] = []
    for take, take_notes in by_take.items():
        take_pitches = [int(note["pitch"]) for note in take_notes]
        channel = Counter(int(note.get("channel", 0)) for note in take_notes).most_common(1)[0][0]
        average = sum(take_pitches) / len(take_pitches)
        simultaneous = Counter(round(float(note["start_ppq"]), 3) for note in take_notes)
        polyphony = max(simultaneous.values(), default=1)
        role = "drums" if channel == 9 else "bass" if average < 48 else "chords" if polyphony >= 3 else "melody"
        roles.append({"take_guid": take, "role": role, "notes": len(take_notes),
                      "pitch_min": min(take_pitches), "pitch_max": max(take_pitches),
                      "max_polyphony": polyphony})
    grouped: dict[float, list[int]] = {}
    for note in notes:
        grouped.setdefault(round(float(note["start_ppq"]), 3), []).append(int(note["pitch"]))
    chord_events = [{"start_ppq": start, "pitch_classes": [PITCH_CLASSES[pc] for pc in sorted({pitch % 12 for pitch in chord})]}
                    for start, chord in sorted(grouped.items()) if len({pitch % 12 for pitch in chord}) >= 3]
    drum_pattern = Counter(int(note["pitch"]) for note in notes if int(note.get("channel", 0)) == 9)
    return {
        "notes": len(notes),
        "pitch_min": min(pitches, default=0),
        "pitch_max": max(pitches, default=0),
        "likely_root": PITCH_CLASSES[likely_root],
        "dominant_channel": channels.most_common(1)[0][0] if channels else 0,
        "median_onset_gap_ppq": sorted(intervals)[len(intervals) // 2] if intervals else 0,
        "start_time": data.get("start_time", 0),
        "end_time": data.get("end_time", 0),
        "tracks": data.get("tracks", []),
        "roles": roles,
        "chord_events": chord_events[:32],
        "drum_pitch_counts": dict(drum_pattern.most_common(16)),
    }


def _transpose_amount(request: str) -> int:
    match = re.search(r"(?:up|raise|transpose up|升高|上移)\s*(\d+)", request, re.IGNORECASE)
    if match:
        return min(24, int(match.group(1)))
    match = re.search(r"(?:down|lower|transpose down|降低|下移)\s*(\d+)", request, re.IGNORECASE)
    if match:
        return -min(24, int(match.group(1)))
    return 0


def transform_selection(source: Path, request: str, destination: Path) -> dict[str, Any]:
    """Create an explicit REAPER note replacement command from a selected region."""
    data = json.loads(source.read_text(encoding="utf-8"))
    original = [dict(note) for note in data.get("notes", []) if isinstance(note, dict)]
    if not original:
        raise ValueError("No selected MIDI notes were supplied")
    transpose = _transpose_amount(request)
    intense = bool(re.search(r"rock|heavy|intense|harder|更摇滚|更重|更强|力度", request, re.IGNORECASE))
    extend = bool(re.search(r"extend|longer|repeat|延长|加长|重复|再来", request, re.IGNORECASE))
    power = bool(re.search(r"power.?chord|更摇滚|更重|强力和弦", request, re.IGNORECASE))
    preserve_pitch = bool(re.search(r"preserve.*melody|keep.*melody|不要改.*旋律|保持.*旋律", request, re.IGNORECASE))
    quantize = bool(re.search(r"quantize|tight(?:er)?|更紧|对齐|量化", request, re.IGNORECASE))
    softer = bool(re.search(r"softer|gentler|lighter|更轻|柔和|力度小", request, re.IGNORECASE))

    starts = [float(note["start_ppq"]) for note in original]
    ends = [float(note["end_ppq"]) for note in original]
    region_start, region_end = min(starts), max(ends)
    span = max(1.0, region_end - region_start)
    transformed: list[dict[str, Any]] = []
    for note in original:
        item = dict(note)
        if transpose and not preserve_pitch and int(item.get("channel", 0)) != 9:
            item["pitch"] = max(0, min(127, int(item["pitch"]) + transpose))
        if intense:
            item["velocity"] = max(1, min(127, int(item.get("velocity", 90)) + 18))
        elif softer:
            item["velocity"] = max(1, min(127, int(item.get("velocity", 90)) - 16))
        if quantize:
            grid = 120.0
            duration = max(grid / 4, float(item["end_ppq"]) - float(item["start_ppq"]))
            item["start_ppq"] = round(float(item["start_ppq"]) / grid) * grid
            item["end_ppq"] = item["start_ppq"] + duration
        transformed.append(item)
        if power and not preserve_pitch and int(item.get("channel", 0)) != 9 and int(item["pitch"]) <= 115:
            fifth = dict(item)
            fifth["pitch"] = int(item["pitch"]) + 7
            fifth["velocity"] = max(1, int(item["velocity"]) - 8)
            transformed.append(fifth)
    if extend:
        repeated = []
        for note in transformed:
            copy = dict(note)
            copy["start_ppq"] = float(copy["start_ppq"]) + span
            copy["end_ppq"] = float(copy["end_ppq"]) + span
            repeated.append(copy)
        transformed.extend(repeated)

    command = {
        "command": "replace_selection",
        "request": request,
        "analysis": analyze_selection(source),
        "original_count": len(original),
        "notes": transformed,
        "region_start_ppq": region_start,
        "region_end_ppq": region_end,
        "extended": extend,
        "preserved_melody": preserve_pitch,
        "quantized": quantize,
    }
    destination.write_text(json.dumps(command, ensure_ascii=False), encoding="utf-8")
    return command


def transform_midi_file(source: Path, request: str, destination: Path, *, operations: dict | None = None) -> dict[str, Any]:
    """Apply the same deterministic edit vocabulary to a DAW-neutral MIDI file."""
    midi = MidiFile(source)
    transpose = _transpose_amount(request)
    intense = bool(re.search(r"rock|heavy|intense|harder|更摇滚|更重|更强|力度", request, re.IGNORECASE))
    softer = bool(re.search(r"softer|gentler|lighter|更轻|柔和|力度小", request, re.IGNORECASE))
    extend = bool(re.search(r"extend|longer|repeat|延长|加长|重复|再来", request, re.IGNORECASE))
    power = bool(re.search(r"power.?chord|更摇滚|更重|强力和弦", request, re.IGNORECASE))
    preserve_melody = bool(re.search(r"preserve.*melody|keep.*melody|不要改.*旋律|保持.*旋律", request, re.IGNORECASE))
    quantize = bool(re.search(r"quantize|tight(?:er)?|更紧|对齐|量化", request, re.IGNORECASE))
    velocity_delta = 18 if intense else -16 if softer else 0
    if operations is not None:
        allowed = {"transpose", "velocity_delta", "quantize", "extend", "power_chords", "preserve_melody"}
        if not isinstance(operations, dict) or set(operations) - allowed:
            raise ValueError("Unsupported MIDI operations")
        for key, value in operations.items():
            if key in {"transpose", "velocity_delta"}:
                limit = 24 if key == "transpose" else 126
                if type(value) is not int or not -limit <= value <= limit:
                    raise ValueError(f"Invalid {key}")
            elif type(value) is not bool:
                raise ValueError(f"Invalid {key}")
        transpose = operations.get("transpose", 0)
        velocity_delta = operations.get("velocity_delta", 0)
        quantize = operations.get("quantize", False)
        extend = operations.get("extend", False)
        power = operations.get("power_chords", False)
        preserve_melody = operations.get("preserve_melody", False)
    if not any((transpose, velocity_delta, quantize, extend, power)):
        raise ValueError("No supported MIDI edit was specified; no file was changed")
    grid = max(1, midi.ticks_per_beat // 4)

    pitch_averages: list[float] = []
    for track in midi.tracks:
        pitches = [message.note for message in track
                   if message.type == "note_on" and message.velocity > 0 and message.channel != 9]
        pitch_averages.append(sum(pitches) / len(pitches) if pitches else -1)
    melody_track = max(range(len(pitch_averages)), key=pitch_averages.__getitem__) if pitch_averages else -1

    output = MidiFile(type=midi.type, ticks_per_beat=midi.ticks_per_beat)
    original_notes = 0
    output_notes = 0
    for track_index, track in enumerate(midi.tracks):
        absolute = 0
        events: list[tuple[int, int, Any]] = []
        note_events: list[tuple[int, int, Any]] = []
        for order, message in enumerate(track):
            absolute += message.time
            if message.type == "end_of_track":
                continue
            item = message.copy(time=0)
            event_time = round(absolute / grid) * grid if quantize and message.type in {"note_on", "note_off"} else absolute
            if message.type in {"note_on", "note_off"} and getattr(message, "channel", -1) != 9:
                is_melody = preserve_melody and track_index == melody_track
                if transpose and not is_melody:
                    item.note = max(0, min(127, item.note + transpose))
                if message.type == "note_on" and message.velocity > 0:
                    original_notes += 1
                    output_notes += 1
                    item.velocity = max(1, min(127, item.velocity + velocity_delta))
                events.append((event_time, order * 2, item))
                note_events.append((event_time, order * 2, item.copy()))
                if power and not is_melody and item.note <= 120:
                    fifth = item.copy(note=item.note + 7)
                    if fifth.type == "note_on" and fifth.velocity > 0:
                        fifth.velocity = max(1, fifth.velocity - 8)
                        output_notes += 1
                    events.append((event_time, order * 2 + 1, fifth))
                    note_events.append((event_time, order * 2 + 1, fifth.copy()))
            else:
                events.append((absolute, order * 2, item))
                if message.type == "note_on" and message.velocity > 0:
                    original_notes += 1
                    output_notes += 1
                if message.type in {"note_on", "note_off"}:
                    note_events.append((event_time, order * 2, item.copy()))
        if extend and note_events:
            span = max(time_value for time_value, _, _ in events)
            for event_time, order, message in note_events:
                events.append((event_time + span, order, message.copy()))
                if message.type == "note_on" and message.velocity > 0:
                    output_notes += 1
        events.sort(key=lambda event: (event[0], event[1]))
        result_track = MidiTrack()
        previous = 0
        for event_time, _, message in events:
            result_track.append(message.copy(time=max(0, event_time - previous)))
            previous = event_time
        result_track.append(MetaMessage("end_of_track", time=0))
        output.tracks.append(result_track)
    destination.parent.mkdir(parents=True, exist_ok=True)
    output.save(destination)
    return {
        "source": str(source), "midi": str(destination), "original_notes": original_notes,
        "output_notes": output_notes, "tracks": len(output.tracks), "transposed": transpose,
        "quantized": quantize, "extended": extend, "power_chords": power,
        "preserved_melody": preserve_melody,
    }
