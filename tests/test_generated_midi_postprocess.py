"""Postprocessing unit fixtures are not model-generation acceptance evidence."""
import hashlib
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
