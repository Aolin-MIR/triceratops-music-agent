import json
import pytest
from mido import MidiFile, MidiTrack, Message
from text2music.agent.tool_results import ToolResultStore
from text2music.agent.midi_tools import analyze_selection


def test_large_real_midi_analysis_is_complete_and_pages_are_lossless(tmp_path):
    midi = MidiFile()
    track = MidiTrack()
    midi.tracks.append(track)
    for i in range(600):
        for j, note in enumerate((60, 64, 67)):
            track.append(
                Message("note_on", note=note, velocity=80, time=240 if j == 0 else 0)
            )
        for j, note in enumerate((60, 64, 67)):
            track.append(Message("note_off", note=note, time=120 if j == 0 else 0))
    path = tmp_path / "large.mid"
    midi.save(path)
    analysis = analyze_selection(path)
    assert analysis["notes"] == 1800 and len(analysis["chord_events"]) == 600
    store = ToolResultStore(tmp_path / "workspace-a")
    manifest = store.save(analysis)
    restored = json.loads((store.root / (manifest["result_id"] + ".json")).read_text())
    assert restored == analysis
    pages = []
    for offset in range(0, 600, 128):
        page = store.read(manifest["result_id"], "chord_events", offset, 128)
        assert page["total"] == 600 and page["offset"] == offset
        pages.extend(page["value"])
    assert pages == analysis["chord_events"]
    assert store.read(manifest["result_id"], "notes")["value"] == 1800
    assert store.read(manifest["result_id"])["sha256"] == manifest["sha256"]
    with pytest.raises(FileNotFoundError):
        ToolResultStore(tmp_path / "workspace-b").read(manifest["result_id"])
    with pytest.raises(ValueError):
        store.read("../other")
    with pytest.raises(ValueError):
        store.read(manifest["result_id"], "chord_events", 0, 10000)
    with pytest.raises(ValueError):
        store.read(manifest["result_id"], "absent")


def test_result_integrity_is_checked_before_reading(tmp_path):
    store = ToolResultStore(tmp_path)
    manifest = store.save({"notes": 20})
    (tmp_path / (manifest["result_id"] + ".json")).write_text('{"notes":21}')
    with pytest.raises(ValueError, match="integrity"):
        store.read(manifest["result_id"], "notes")


def test_long_strings_are_retrievable_in_full_without_a_fake_partial_value(tmp_path):
    store = ToolResultStore(tmp_path)
    value = "Preserve this complete abstract musical requirement. " * 1000
    manifest = store.save({"description": value})
    assert manifest["fields"]["description"] == {
        "type": "str",
        "characters": len(value),
    }
    assert store.read(manifest["result_id"], "description")["value"] == value


def test_tool_loop_retrieves_large_analysis_without_truncating_json_or_current_request(tmp_path):
    from types import SimpleNamespace
    from text2music.agent.tool_loop import run_tool_loop
    midi = MidiFile(); track = MidiTrack(); midi.tracks.append(track)
    for i in range(600):
        for j, note in enumerate((60, 64, 67)):
            track.append(Message("note_on", note=note, velocity=80, time=240 if j==0 else 0))
        for j, note in enumerate((60, 64, 67)):
            track.append(Message("note_off", note=note, time=120 if j==0 else 0))
    source = tmp_path/"large.mid"; midi.save(source)
    current = "Analyze all 600 chords, including the last chord; preserve this exact current request."
    store = ToolResultStore(tmp_path/"results")
    seen = []
    class Answer:
        content = ""
        def __init__(self, name, args):
            self.tool_calls = [SimpleNamespace(id=str(len(seen)),function=SimpleNamespace(name=name,arguments=json.dumps(args)))]
        def model_dump(self, **kwargs):
            c = self.tool_calls[0]
            return {"role":"assistant","tool_calls":[{"id":c.id,"type":"function","function":{"name":c.function.name,"arguments":c.function.arguments}}]}
    def create(**kwargs):
        messages = kwargs["messages"]
        assert any(m.get("role")=="user" and m["content"]==current for m in messages)
        seen.append(json.loads(json.dumps(messages)))
        if len(seen)==1:
            answer=Answer("analyze_selected_midi",{})
        elif len(seen)==2:
            manifest=json.loads(messages[-1]["content"])
            assert manifest["representation"]=="full-result-stored-for-retrieval"
            assert manifest["fields"]["chord_events"]["count"]==600
            answer=Answer("read_tool_result",{"result_id":manifest["result_id"],"field":"chord_events","offset":599,"limit":1})
        else:
            page=json.loads(messages[-1]["content"])
            assert page["total"]==600 and page["offset"]==599 and not page["has_more"]
            assert page["value"]==analyze_selection(source)["chord_events"][-1:]
            answer=Answer("respond",{"message":"Read all 600 chord records; retrieved the last one exactly."})
        return SimpleNamespace(choices=[SimpleNamespace(message=answer)])
    client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    decision=run_tool_loop(current,selection=source,client=client,result_store=store)
    assert len(seen)==3
    assert decision.trace[0]["result"]["notes"]==1800
    assert len(decision.trace[0]["result"]["chord_events"])==600
    assert all(e["state"]=="completed" for e in decision.trace)
