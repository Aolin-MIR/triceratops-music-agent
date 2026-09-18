"""Perception, validation, memory and trace tools for the Text2Score agent."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from mido import MidiFile


def append_trace(run_dir: Path, action: str, detail: str, **data: Any) -> None:
    entry = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "action": action, "detail": detail, **data}
    with (run_dir / "agent-trace.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_memory(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def remember(path: Path, *, request: str, plan: str, outcome: str) -> dict[str, Any]:
    memory = load_memory(path)
    memory.setdefault("recent_requests", [])
    memory.setdefault("preferred_genres", [])
    memory.setdefault("preferred_instruments", [])
    genre = re.search(r"^Genre:\s*(.+)$", plan, re.MULTILINE)
    instruments = re.search(r"^Instruments:\s*(.+)$", plan, re.MULTILINE)
    approved = outcome.startswith("accepted")
    if approved and genre and genre.group(1) not in memory["preferred_genres"]:
        memory["preferred_genres"].append(genre.group(1))
    if approved and instruments:
        for name in (item.strip() for item in instruments.group(1).split(",")):
            if name and name not in memory["preferred_instruments"]:
                memory["preferred_instruments"].append(name)
    memory["recent_requests"].append({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "request": request[-500:], "outcome": outcome})
    memory["recent_requests"] = memory["recent_requests"][-12:]
    memory["preferred_genres"] = memory["preferred_genres"][-12:]
    memory["preferred_instruments"] = memory["preferred_instruments"][-24:]
    path.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")
    return memory


def record_feedback(memory_path: Path, history_path: Path, feedback: str) -> dict[str, Any]:
    """Learn only from an explicit Keep/Reject decision, not from mere generation."""
    memory = load_memory(memory_path)
    memory.setdefault("feedback", [])
    memory.setdefault("genre_scores", {})
    memory.setdefault("instrument_scores", {})
    entry: dict[str, Any] = {}
    try:
        entry = json.loads(history_path.read_text(encoding="utf-8").splitlines()[-1])
    except (OSError, IndexError, json.JSONDecodeError):
        pass
    plan_path = Path(str(entry.get("plan", "")))
    plan = plan_path.read_text(encoding="utf-8", errors="replace") if plan_path.is_file() else ""
    delta = 1 if feedback == "accept" else -1
    genre = re.search(r"^Genre:\s*(.+)$", plan, re.MULTILINE)
    instruments = re.search(r"^Instruments:\s*(.+)$", plan, re.MULTILINE)
    if genre:
        name = genre.group(1).strip()
        memory["genre_scores"][name] = int(memory["genre_scores"].get(name, 0)) + delta
    if instruments:
        for name in (item.strip() for item in instruments.group(1).split(",")):
            if name:
                memory["instrument_scores"][name] = int(memory["instrument_scores"].get(name, 0)) + delta
    memory["preferred_genres"] = [name for name, score in memory["genre_scores"].items() if score > 0][-12:]
    memory["preferred_instruments"] = [name for name, score in memory["instrument_scores"].items() if score > 0][-24:]
    memory["feedback"].append({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "value": feedback,
                               "request": str(entry.get("request", ""))[-500:]})
    memory["feedback"] = memory["feedback"][-40:]
    memory_path.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")
    return memory


def memory_context(memory: dict[str, Any]) -> str:
    genres = ", ".join(memory.get("preferred_genres", [])[-4:])
    instruments = ", ".join(memory.get("preferred_instruments", [])[-8:])
    recent = [str(item.get("request", "")) for item in memory.get("recent_requests", [])[-2:] if isinstance(item, dict)]
    avoid_genres = ", ".join(name for name, score in memory.get("genre_scores", {}).items() if int(score) < 0)
    avoid_instruments = ", ".join(name for name, score in memory.get("instrument_scores", {}).items() if int(score) < 0)
    if not genres and not instruments and not recent:
        return ""
    return (f"Artist preferences from approved prior work: genres={genres or 'none'}; instruments={instruments or 'none'}; "
            f"avoid genres={avoid_genres or 'none'}; avoid instruments={avoid_instruments or 'none'}. "
            f"Recent conversation requests: {' | '.join(recent) or 'none'}. Interpret relative edits such as 'more intense' in this context.")


def validate_midi(path: Path, plan: str) -> list[str]:
    try:
        midi = MidiFile(path)
    except Exception as exc:
        return [f"MIDI cannot be read: {type(exc).__name__}"]
    notes: list[int] = []
    tempos: list[int] = []
    signatures: list[str] = []
    velocities: list[int] = []
    active_tracks = 0
    drum_notes = 0
    max_tick = 0
    for track in midi.tracks:
        ticks = 0
        track_notes = 0
        for message in track:
            ticks += message.time
            if message.type == "note_on" and message.velocity > 0:
                notes.append(message.note)
                velocities.append(message.velocity)
                track_notes += 1
                if getattr(message, "channel", -1) == 9:
                    drum_notes += 1
            elif message.type == "set_tempo":
                tempos.append(round(60_000_000 / message.tempo))
            elif message.type == "time_signature":
                signatures.append(f"{message.numerator}/{message.denominator}")
        if track_notes:
            active_tracks += 1
        max_tick = max(max_tick, ticks)
    findings: list[str] = []
    if not notes:
        findings.append("Generated MIDI has no notes")
    if len(notes) < 8:
        findings.append(f"Generated MIDI is too sparse ({len(notes)} notes)")
    if max_tick <= 0:
        findings.append("Generated MIDI has zero duration")
    if notes:
        ranges = [(int(low), int(high)) for low, high in re.findall(r"Pitch Range:\s*(\d+)\D+(\d+)", plan)]
        if ranges:
            low, high = min(low for low, _ in ranges), max(high for _, high in ranges)
            if sum(note < low - 12 or note > high + 12 for note in notes) > len(notes) * .35:
                findings.append(f"Too many notes fall outside planned range {low}-{high}")
    expected_tempo = re.search(r"Tempo:\s*(\d+)\s*BPM", plan)
    if expected_tempo and tempos and abs(tempos[0] - int(expected_tempo.group(1))) > 15:
        findings.append(f"MIDI tempo {tempos[0]} BPM differs from planned {expected_tempo.group(1)} BPM")
    expected_signature = re.search(r"Time Signature:\s*(\d+/\d+)", plan)
    if expected_signature and signatures and signatures[0] != expected_signature.group(1):
        findings.append(f"MIDI meter {signatures[0]} differs from planned {expected_signature.group(1)}")
    numerator, denominator = map(int, expected_signature.group(1).split("/")) if expected_signature else (4, 4)
    actual_measures = max_tick / max(1, midi.ticks_per_beat * numerator * 4 / denominator)
    expected_measures = re.search(r"Total Measures:\s*(\d+)", plan)
    if expected_measures and actual_measures:
        target = int(expected_measures.group(1))
        if actual_measures < target * .65 or actual_measures > target * 1.5:
            findings.append(f"MIDI length {actual_measures:.1f} measures differs from planned {target}")
    planned_instruments = re.search(r"^Instruments:\s*(.+)$", plan, re.MULTILINE)
    instrument_count = 0
    instrument_text = ""
    if planned_instruments:
        instrument_text = planned_instruments.group(1).lower()
        instrument_count = len([item for item in instrument_text.split(",") if item.strip()])
        if instrument_count >= 2 and active_tracks < 2:
            findings.append(f"Only {active_tracks} active MIDI track(s) for {instrument_count} planned instruments")
    density = re.search(r"Density:\s*(Low|Moderate|High)", plan, re.IGNORECASE)
    notes_per_measure = len(notes) / max(1., actual_measures)
    if density:
        wanted = density.group(1).lower()
        if wanted == "high" and notes_per_measure < 8:
            findings.append(f"Note density is low ({notes_per_measure:.1f}/measure) for planned High density")
        elif wanted == "low" and notes_per_measure > 28:
            findings.append(f"Note density is high ({notes_per_measure:.1f}/measure) for planned Low density")
    genre_match = re.search(r"^Genre:\s*(.+)$", plan, re.MULTILINE)
    genre = genre_match.group(1).lower() if genre_match else ""
    if any(style in genre for style in ("rock", "metal", "punk")):
        if active_tracks < 2:
            findings.append("Rock arrangement lacks layered active parts")
        if any(word in instrument_text for word in ("drum", "kit", "percussion")) and drum_notes == 0:
            findings.append("Rock plan requests drums but no channel-10 drum notes were produced")
        if velocities and sum(velocities) / len(velocities) < 55:
            findings.append("Rock performance has unusually weak average velocity")
    return findings


def midi_stats(path: Path) -> dict[str, Any]:
    midi = MidiFile(path)
    notes: list[int] = []
    ticks = 0
    for track in midi.tracks:
        position = 0
        for message in track:
            position += message.time
            if message.type == "note_on" and message.velocity > 0:
                notes.append(message.note)
        ticks = max(ticks, position)
    return {"notes": len(notes), "pitch_min": min(notes, default=0), "pitch_max": max(notes, default=0), "ticks": ticks, "tracks": len(midi.tracks)}


def compare_versions(current: Path, previous: Path | None) -> dict[str, Any]:
    now = midi_stats(current)
    if previous is None or not previous.exists():
        return {"current": now, "previous": None, "summary": "First generated version"}
    before = midi_stats(previous)
    return {"current": now, "previous": before, "summary": f"notes {before['notes']}→{now['notes']}; range {before['pitch_min']}-{before['pitch_max']}→{now['pitch_min']}-{now['pitch_max']}; tracks {before['tracks']}→{now['tracks']}"}


def summarize_selected_midi(path: Path) -> str:
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        notes = data.get("notes", [])
        pitches = [int(note.get("pitch", 0)) for note in notes if isinstance(note, dict)]
        return (f"Selected REAPER MIDI region: {len(notes)} notes, pitch range {min(pitches, default=0)}-{max(pitches, default=0)}, "
                f"project range {data.get('start_time', 0)}-{data.get('end_time', 0)} seconds, tracks: "
                f"{', '.join(data.get('tracks', [])) or 'selected track'}. Preserve the requested region boundaries and create a revision candidate.")
    midi = MidiFile(path)
    notes = [message.note for track in midi.tracks for message in track if message.type == "note_on" and message.velocity > 0]
    return f"Existing MIDI: {len(notes)} notes, range {min(notes, default=0)}-{max(notes, default=0)}."
