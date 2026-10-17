"""Apply explicit constraints to real model output, retaining the raw MIDI."""
from __future__ import annotations

import hashlib
from pathlib import Path
from mido import Message, MidiFile, MidiTrack


def validate_constraints(constraints: dict | None) -> dict:
    constraints = {} if constraints is None else constraints
    if not isinstance(constraints, dict) or set(constraints) - {"exclude_drums", "program"}:
        raise ValueError("Unsupported MIDI generation constraints")
    if "exclude_drums" in constraints and type(constraints["exclude_drums"]) is not bool:
        raise ValueError("exclude_drums must be a boolean")
    if "program" in constraints and (type(constraints["program"]) is not int or not 0 <= constraints["program"] <= 127):
        raise ValueError("program must be a zero-based General MIDI program from 0 to 127")
    return dict(constraints)


def midi_summary(path: Path) -> dict:
    midi = MidiFile(path)
    notes = [event for track in midi.tracks for event in track
             if event.type == "note_on" and event.velocity > 0]
    return {"note_count": len(notes), "duration_seconds": round(midi.length, 3),
            "tracks": len(midi.tracks), "drum_notes": sum(event.channel == 9 for event in notes),
            "programs": sorted({event.program for track in midi.tracks for event in track
                                if event.type == "program_change"})}


def constrain_generated_midi(raw: Path, constraints: dict | None) -> dict:
    """Never synthesize replacement notes or modify an existing source clip."""
    constraints = validate_constraints(constraints)
    before = midi_summary(raw)
    digest = hashlib.sha256(raw.read_bytes()).hexdigest()
    report = {"requested": constraints, "raw_sha256": digest, "raw_validation": before,
              "removed_drum_events": 0, "changed_program_events": 0, "inserted_program_events": 0}
    if not constraints or (not constraints.get("exclude_drums") and "program" not in constraints):
        return {"midi": str(raw), "raw_midi": str(raw), "postprocess": report, "validation": before}
    midi = MidiFile(raw)
    for index, track in enumerate(midi.tracks):
        events = []
        tick = 0
        for event in track:
            tick += event.time
            if constraints.get("exclude_drums") and getattr(event, "channel", None) == 9:
                report["removed_drum_events"] += 1
                continue
            if event.type == "program_change" and event.channel != 9 and "program" in constraints:
                if event.program != constraints["program"]:
                    report["changed_program_events"] += 1
                event = event.copy(program=constraints["program"])
            events.append((tick, event))
        if "program" in constraints:
            channels = {event.channel for _, event in events if event.type == "note_on" and event.velocity > 0 and event.channel != 9}
            initialized = {event.channel for tick, event in events if tick == 0 and event.type == "program_change"}
            injected = [(0, Message("program_change", channel=channel, program=constraints["program"]))
                        for channel in sorted(channels - initialized)]
            report["inserted_program_events"] += len(injected)
            events = injected + events
        replacement = MidiTrack()
        previous = 0
        for tick, event in events:
            replacement.append(event.copy(time=tick - previous))
            previous = tick
        midi.tracks[index] = replacement
    if not any(event.type == "note_on" and event.velocity > 0 for track in midi.tracks for event in track):
        raise RuntimeError("The model produced no usable notes after the requested drum exclusion; raw MIDI retained")
    destination = raw.with_name(raw.stem + "-constrained.mid")
    midi.save(destination)
    after = midi_summary(destination)
    if constraints.get("exclude_drums") and after["drum_notes"]:
        raise RuntimeError("MIDI postprocessing failed to remove drum notes")
    if hashlib.sha256(raw.read_bytes()).hexdigest() != digest:
        raise RuntimeError("Raw model MIDI changed during postprocessing")
    return {"midi": str(destination), "raw_midi": str(raw), "postprocess": report, "validation": after}
