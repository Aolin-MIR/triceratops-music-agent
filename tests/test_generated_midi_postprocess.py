"""Postprocessing unit fixtures are not model-generation acceptance evidence."""
import hashlib
from pathlib import Path
from mido import Message, MidiFile, MidiTrack
import pytest
from text2music.agent.midi_postprocess import constrain_generated_midi


def tonal_events(path):
    result = []
    for track_index, track in enumerate(MidiFile(path).tracks):
        tick = 0
        for event in track:
            tick += event.time
            if event.type in {"note_on", "note_off", "pitchwheel", "control_change"} and event.channel != 9:
                result.append((track_index, tick, event.copy(time=0).dict()))
    return result


def test_explicit_constraints_keep_raw_output_and_tonal_events(tmp_path):
    raw = tmp_path / "raw.mid"
    midi = MidiFile()
    midi.tracks.append(MidiTrack([
        Message("program_change", channel=1, program=25),
        Message("note_on", channel=1, note=60, velocity=80, time=7),
        Message("note_on", channel=9, note=36, velocity=90, time=11),
        Message("control_change", channel=1, control=1, value=50, time=5),
        Message("pitchwheel", channel=1, pitch=123, time=8),
        Message("note_off", channel=1, note=60, time=50),
        Message("note_off", channel=9, note=36, time=17)]))
    midi.save(raw)
    digest = hashlib.sha256(raw.read_bytes()).hexdigest()
    result = constrain_generated_midi(raw, {"exclude_drums": True, "program": 0})
    assert result["raw_midi"] == str(raw)
    assert hashlib.sha256(raw.read_bytes()).hexdigest() == digest
    assert tonal_events(raw) == tonal_events(result["midi"])
    assert result["validation"]["note_count"] == 1
    assert result["validation"]["drum_notes"] == 0
    assert result["validation"]["programs"] == [0]
    assert result["postprocess"]["removed_drum_events"] == 2
    assert result["postprocess"]["raw_validation"]["drum_notes"] == 1


def test_drum_only_output_is_not_replaced_with_invented_notes(tmp_path):
    raw = tmp_path / "drums.mid"
    midi = MidiFile()
    midi.tracks.append(MidiTrack([Message("note_on", channel=9, note=36, velocity=80),
                                  Message("note_off", channel=9, note=36, time=100)]))
    midi.save(raw)
    with pytest.raises(RuntimeError, match="no usable notes"):
        constrain_generated_midi(raw, {"exclude_drums": True})
    assert raw.is_file()
    assert not raw.with_name("drums-constrained.mid").exists()


def test_generated_retriggers_keep_unique_onsets_and_controllers_without_same_key_overlap(tmp_path):
    raw = tmp_path / "duplicate-overlap.mid"
    midi = MidiFile(ticks_per_beat=480)
    midi.tracks.append(MidiTrack([
        Message("note_on", note=60, velocity=80),
        Message("note_on", note=60, velocity=90),
        Message("control_change", control=1, value=70, time=10),
        Message("note_on", note=60, velocity=75, time=10),
        Message("note_off", note=60, time=20),
        Message("note_off", note=60, time=5),
        Message("note_off", note=60, time=5)]))
    midi.save(raw)
    original = raw.read_bytes()
    result = constrain_generated_midi(raw, {}, normalize_retriggers=True)
    rows = tonal_events(result["midi"])
    ons = [(tick, event["note"], event["velocity"]) for _, tick, event in rows if event["type"] == "note_on"]
    assert ons == [(0, 60, 80), (20, 60, 75)]
    assert [(tick, event["value"]) for _, tick, event in rows if event["type"] == "control_change"] == [(10, 70)]
    assert [event["type"] for _, tick, event in rows if tick == 20] == ["note_off", "note_on"]
    active = 0
    for _, _, event in rows:
        if event["type"] == "note_on":
            assert active == 0
            active += 1
        elif event["type"] == "note_off":
            active -= 1
    assert active == 0
    audit = result["postprocess"]["note_retriggers"]
    assert audit["merged_simultaneous_note_ons"] == 1
    assert audit["clipped_overlapping_note_offs"] == 1
    assert raw.read_bytes() == original
    again = constrain_generated_midi(Path(result["midi"]), {}, normalize_retriggers=True)
    assert tonal_events(again["midi"]) == rows


def test_generated_retrigger_cleanup_is_separate_from_existing_explicit_constraint_path(tmp_path):
    raw = tmp_path / "channels.mid"
    midi = MidiFile()
    midi.tracks.append(MidiTrack([
        Message("note_on", channel=0, note=60, velocity=70),
        Message("note_on", channel=1, note=60, velocity=80),
        Message("note_on", channel=9, note=60, velocity=90),
        Message("note_off", channel=0, note=60, time=20),
        Message("note_off", channel=1, note=60),
        Message("note_off", channel=9, note=60)]))
    midi.save(raw)
    plain = constrain_generated_midi(raw, {})
    assert plain["midi"] == str(raw)
    cleaned = constrain_generated_midi(raw, {}, normalize_retriggers=True)
    assert cleaned["validation"]["note_count"] == 3
    assert cleaned["postprocess"]["note_retriggers"]["merged_simultaneous_note_ons"] == 0
