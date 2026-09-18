from text2music.agent.service import MusicBrief, _compile_qwen_plan, build_plan, validate_plan
import json
from pathlib import Path

from mido import Message, MetaMessage, MidiFile, MidiTrack

from text2music.agent.capabilities import record_feedback, validate_midi
from text2music.agent.midi_tools import analyze_selection, transform_midi_file, transform_selection
from text2music.agent.tool_loop import run_tool_loop


def test_rock_plan_has_required_text2score_fields():
    plan = build_plan(MusicBrief(description="fast rock anthem"))
    assert "Genre: rock" in plan
    assert "Instruments: Electric Guitar, Electric Bass, Drumset" in plan
    assert "Time Signature: 4/4" in plan
    assert validate_plan(plan) == []


def test_validator_rejects_incomplete_plan():
    findings = validate_plan("Total Measures: 16\n")
    assert any("Instruments" in finding for finding in findings)


def test_qwen_prompt_does_not_need_a_key_for_local_planning():
    plan = build_plan(MusicBrief(description="driving hard-rock riff", genre="rock", tempo=155))
    assert "Tempo: 155 BPM" in plan


def test_compiles_qwen_json_to_a_valid_plan():
    sections = []
    for measure in (1, 4, 8, 12, 16):
        sections.append({"measure": measure, "instruments": ["Electric Guitar", "Electric Bass", "Drumset"],
                         "pitch_min": 36, "pitch_max": 88, "density": "Moderate", "tempo": 145,
                         "time_signature": "4/4", "key_signature": 1, "chords": [0, 4, 7],
                         "direction": "riff section"})
    plan = _compile_qwen_plan({"genre": "rock", "instruments": sections[0]["instruments"], "measures": sections},
                              MusicBrief(description="rock", measures=16))
    assert validate_plan(plan) == []


def test_compiler_compacts_per_measure_qwen_output():
    sections = [{"measure": measure, "instruments": ["Piano"], "pitch_min": 40, "pitch_max": 80,
                 "density": "Moderate", "tempo": 120, "time_signature": "4/4", "key_signature": 0,
                 "chords": [0, 4, 7], "direction": "section"} for measure in range(1, 17)]
    plan = _compile_qwen_plan({"genre": "rock", "instruments": ["Piano"], "measures": sections},
                              MusicBrief(description="test", measures=16))
    assert plan.count("Measure:") == 10


def test_selected_midi_analysis_and_in_place_transform(tmp_path: Path):
    selection = tmp_path / "selection.json"
    notes = [
        {"take_guid": "TAKE1", "pitch": pitch, "velocity": 70, "start_ppq": start,
         "end_ppq": start + 100, "channel": 0, "muted": False}
        for start, pitch in ((3, 48), (3, 52), (3, 55), (121, 50))
    ]
    selection.write_text(json.dumps({"start_time": 0, "end_time": 1, "tracks": ["Guitar"], "notes": notes}),
                         encoding="utf-8")
    analysis = analyze_selection(selection)
    assert analysis["roles"][0]["role"] == "chords"
    assert analysis["chord_events"][0]["pitch_classes"] == ["C", "E", "G"]
    replacement = transform_selection(selection, "更摇滚，更紧，延长一遍", tmp_path / "replacement.json")
    assert replacement["quantized"] is True
    assert replacement["extended"] is True
    assert len(replacement["notes"]) > len(notes) * 2
    assert all(note["take_guid"] == "TAKE1" for note in replacement["notes"])


def test_tool_loop_requires_real_model(monkeypatch):
    import pytest
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="QWEN_API_KEY"):
        run_tool_loop("写一段摇滚")


def test_midi_validator_checks_arrangement_quality(tmp_path: Path):
    midi = MidiFile(ticks_per_beat=480)
    track = MidiTrack()
    midi.tracks.append(track)
    track.append(MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    track.append(MetaMessage("set_tempo", tempo=500000, time=0))
    for pitch in (60, 62, 64, 65):
        track.append(Message("note_on", note=pitch, velocity=30, channel=0, time=0))
        track.append(Message("note_off", note=pitch, velocity=0, channel=0, time=120))
    path = tmp_path / "thin.mid"
    midi.save(path)
    plan = ("Genre: rock\nInstruments: Electric Guitar, Electric Bass, Drumset\n"
            "Total Measures: 16\nTempo: 120 BPM\nTime Signature: 4/4\nDensity: High\n")
    findings = validate_midi(path, plan)
    assert any("track" in item.lower() or "layered" in item.lower() for item in findings)
    assert any("drum" in item.lower() for item in findings)
    assert any("density" in item.lower() or "sparse" in item.lower() for item in findings)


def test_explicit_feedback_updates_preference_scores(tmp_path: Path):
    plan = tmp_path / "plan.txt"
    plan.write_text("Genre: rock\nInstruments: Guitar, Drumset\n", encoding="utf-8")
    history = tmp_path / "history.jsonl"
    history.write_text(json.dumps({"plan": str(plan), "request": "rock please"}) + "\n", encoding="utf-8")
    memory = tmp_path / "memory.json"
    learned = record_feedback(memory, history, "accept")
    assert learned["genre_scores"]["rock"] == 1
    learned = record_feedback(memory, history, "reject")
    assert learned["genre_scores"]["rock"] == 0


def test_daw_neutral_midi_transform_preserves_melody_and_adds_rock_layer(tmp_path: Path):
    midi = MidiFile(type=1, ticks_per_beat=480)
    chords = MidiTrack()
    melody = MidiTrack()
    midi.tracks.extend([chords, melody])
    for pitch in (48, 52, 55):
        chords.append(Message("note_on", note=pitch, velocity=55, time=0))
        chords.append(Message("note_off", note=pitch, velocity=0, time=240))
    for pitch in (72, 74):
        melody.append(Message("note_on", note=pitch, velocity=70, time=0))
        melody.append(Message("note_off", note=pitch, velocity=0, time=240))
    source = tmp_path / "source.mid"
    output = tmp_path / "rock.mid"
    midi.save(source)

    result = transform_midi_file(source, "改成更摇滚，量化，但不要改主旋律", output)
    revised = MidiFile(output)
    melody_notes = [
        message.note for message in revised.tracks[1]
        if message.type == "note_on" and message.velocity > 0
    ]
    assert result["quantized"] is True
    assert result["power_chords"] is True
    assert melody_notes == [72, 74]
    assert len(revised.tracks[0]) > len(chords)
