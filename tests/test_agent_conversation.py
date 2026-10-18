import json
from types import SimpleNamespace
import pytest
from text2music.agent.tool_loop import run_tool_loop

class Answer:
    def __init__(self, content=None, tool=None, arguments=None):
        self.content = content
        self.tool_calls = [SimpleNamespace(id="call1", type="function", function=SimpleNamespace(
            name=tool, arguments=json.dumps(arguments or {})))] if tool else []
    def model_dump(self, **kwargs):
        return {"role": "assistant", "content": self.content,
                "tool_calls": [{"id": c.id, "type": "function", "function": {
                "name": c.function.name, "arguments": c.function.arguments}} for c in self.tool_calls]}

class Client:
    def __init__(self, answers):
        self.answers = iter(answers)
        self.requests = []
        self.chat = SimpleNamespace(completions=self)
    def create(self, **kwargs):
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        return SimpleNamespace(choices=[SimpleNamespace(message=next(self.answers))])

def test_chat_does_not_execute_music_tools():
    client = Client([Answer("你好，可以一起讨论编曲。")])
    result = run_tool_loop("你好", client=client, execute=lambda *a: pytest.fail("unexpected mutation"))
    assert result.tool == "chat"
    assert result.reply.startswith("你好")

def test_button_operation_must_execute_before_reporting():
    client = Client([Answer(tool="audio_to_midi"), Answer("已转写。")])
    calls = []
    result = run_tool_loop("Convert the loaded audio to MIDI.", forced_tool="audio_to_midi",
                           client=client, execute=lambda name, args: calls.append(name) or {"midi": "/tmp/out.mid"})
    assert calls == ["audio_to_midi"]
    assert result.trace[0]["state"] == "completed"
    assert client.requests[0]["tool_choice"]["function"]["name"] == "audio_to_midi"
    assert len(client.requests) == 1

def test_button_does_not_accept_a_promise_without_execution():
    with pytest.raises(RuntimeError, match="did not execute"):
        run_tool_loop("Convert audio", forced_tool="audio_to_midi",
                      client=Client([Answer("Converting now.")]))

def test_observe_execute_and_report_actual_results():
    client = Client([Answer(tool="inspect_project"),
                     Answer(tool="transform_midi", arguments={"request": "transpose up 2 semitones", "operations": {"transpose": 2}}),
                     Answer("已完成升高两个半音。")])
    calls = []
    def execute(name, args):
        calls.append((name, args))
        return {"midi": "/tmp/revised.mid", "notes": 8}
    result = run_tool_loop("按之前说的修改", context="Tempo: 120", client=client, execute=execute)
    assert len(calls) == 1
    assert calls[0][1]["request"] == "transpose up 2 semitones"
    assert result.trace[-1]["result"]["notes"] == 8
    assert json.loads(client.requests[-1]["messages"][-1]["content"])["midi"] == "/tmp/revised.mid"

def test_tool_failure_is_returned_to_model_without_fallback():
    client = Client([Answer(tool="audio_to_midi"), Answer("转录失败，缺少模型。")])
    def execute(*args):
        raise RuntimeError("missing model")
    result = run_tool_loop("转录音频", client=client, execute=execute)
    assert result.trace[0]["state"] == "failed"
    assert "missing model" in client.requests[-1]["messages"][-1]["content"]

def test_model_failure_is_not_replaced_with_generation():
    class Broken(Client):
        def create(self, **kwargs):
            raise ConnectionError("offline")
    with pytest.raises(ConnectionError):
        run_tool_loop("你好", client=Broken([]))

def test_unknown_tool_is_rejected():
    with pytest.raises(ValueError, match="Invalid agent tool"):
        run_tool_loop("你好", client=Client([Answer(tool="imaginary_tool")]))


def test_real_midi_analysis_and_structured_edit(tmp_path):
    from mido import MidiFile, MidiTrack, Message
    from text2music.agent.midi_tools import analyze_selection, transform_midi_file
    source = tmp_path / "source.mid"
    output = tmp_path / "output.mid"
    midi = MidiFile(); track = MidiTrack(); midi.tracks.append(track)
    track.append(Message("note_on", note=60, velocity=80))
    track.append(Message("note_off", note=60, time=480))
    midi.save(source)
    assert analyze_selection(source)["notes"] == 1
    analysis = analyze_selection(source)
    assert analysis["pitch_min_name"] == "C4"
    assert analysis["pitch_max_name"] == "C4"
    assert analysis["ticks_per_quarter"] == 480
    assert analysis["key_estimate"] is None
    result = transform_midi_file(source, "降低力度", output, operations={"velocity_delta": -20})
    assert [m.velocity for t in MidiFile(output).tracks for m in t if m.type == "note_on"] == [60]
    with pytest.raises(ValueError, match="No supported"):
        transform_midi_file(source, "change something unspecified", output)


def test_full_clip_transposition_keeps_timing_and_velocity_even_if_quality_is_preserved(tmp_path):
    from mido import MidiFile, MidiTrack, Message
    from text2music.agent.midi_tools import transform_midi_file
    from text2music.agent.tool_loop import tool_schemas
    schema = next(item['function']['parameters'] for item in tool_schemas()
                  if item['function']['name'] == 'transform_midi')
    assert 'protect_melody_track' in schema['properties']['operations']['properties']
    assert 'preserve_melody' not in schema['properties']['operations']['properties']
    source, output = tmp_path/'before.mid', tmp_path/'after.mid'
    midi = MidiFile(ticks_per_beat=480)
    midi.tracks.append(MidiTrack([Message('note_on', note=60, velocity=73),
                                  Message('note_off', note=60, velocity=0, time=120)]))
    midi.save(source)
    transform_midi_file(source, 'transpose all notes up two semitones; keep timing and velocity', output,
                        operations={'transpose': 2, 'preserve_melody': False})
    before = [(m.type, m.time, getattr(m, 'note', None), getattr(m, 'velocity', None))
              for track in MidiFile(source).tracks for m in track]
    after = [(m.type, m.time, getattr(m, 'note', None), getattr(m, 'velocity', None))
             for track in MidiFile(output).tracks for m in track]
    assert len(before) == len(after)
    assert all(a[0:2] == b[0:2] and a[2] + 2 == b[2] and a[3] == b[3]
               for a, b in zip(before, after) if a[2] is not None)


def test_cancel_prevents_next_model_or_tool_call():
    result = run_tool_loop("edit", client=Client([]), cancelled=lambda: True)
    assert "取消" in result.reply


def test_repeat_preserves_multi_track_alignment_and_trailing_rest(tmp_path):
    from mido import MidiFile, MidiTrack, Message, MetaMessage
    from text2music.agent.midi_tools import transform_midi_file
    source = tmp_path / "duet.mid"
    output = tmp_path / "repeat.mid"
    midi = MidiFile(ticks_per_beat=480)
    for duration in (240, 480):
        track = MidiTrack([
            Message("note_on", note=60, velocity=80),
            Message("note_off", note=60, time=duration),
            MetaMessage("end_of_track", time=960-duration),
        ])
        midi.tracks.append(track)
    midi.save(source)
    transform_midi_file(source, "repeat", output)
    for track in MidiFile(output).tracks:
        tick = 0
        onsets = []
        for event in track:
            tick += event.time
            if event.type == "note_on" and event.velocity:
                onsets.append(tick)
        assert onsets == [0, 960]


def test_broad_prompt_is_rewritten_into_actionable_generation_request():
    rewritten = "A melancholic solo piano piece at a slow tempo in a minor key, with a gentle 4/4 pulse."
    client = Client([
        Answer(tool="generate_draft", arguments={"request": rewritten, "backend": "auto"}),
        Answer("已经按这个情绪生成好了。"),
    ])
    calls = []
    result = run_tool_loop(
        "来点伤感钢琴",
        context="Tempo: 92 BPM\nTime Signature: 4/4",
        client=client,
        execute=lambda name, args: calls.append((name, args)) or {"midi": "/tmp/sad.mid"},
    )
    assert calls == [("generate_draft", {"request": rewritten, "backend": "auto"})]
    assert result.reply == "已经按这个情绪生成好了。"
    system = client.requests[0]["messages"][0]["content"]
    assert "Never require a prompt template" in system
    assert "sensible defaults" in system


def test_generation_schema_requires_rewritten_request():
    client = Client([Answer("ok")])
    run_tool_loop("随便来点", client=client)
    generate = next(item for item in client.requests[0]["tools"]
                    if item["function"]["name"] == "generate_draft")
    assert generate["function"]["parameters"]["required"] == ["request"]

def test_tool_prompt_has_explicit_host_file_availability(tmp_path):
    from text2music.agent.tool_loop import run_tool_loop
    client = Client([Answer('请先加载音频。')])
    result = run_tool_loop('把附件分轨', client=client, context='Tempo: 120',
                           execute=lambda *args: pytest.fail('missing file executed'))
    system = client.requests[0]['messages'][0]['content']
    assert 'Audio available: False' in system and 'MIDI available: False' in system
    assert 'A user saying attached does not create an attachment' in system
    assert result.reply == '请先加载音频。'


def test_new_real_midi_updates_file_availability_for_later_agent_steps(tmp_path):
    from mido import MidiFile, MidiTrack, Message
    generated = tmp_path/'generated.mid'
    client = Client([Answer(tool='generate_draft', arguments={'request':'Sparse piano'}), Answer('Done')])
    def execute(name, arguments):
        midi = MidiFile()
        midi.tracks.append(MidiTrack([Message('note_on', note=60, velocity=70), Message('note_off', note=60, time=480)]))
        midi.save(generated)
        return {'midi':str(generated)}
    run_tool_loop('Generate sparse piano', client=client, execute=execute)
    assert 'MIDI available: False' in client.requests[0]['messages'][0]['content']
    assert 'MIDI available: True' in client.requests[1]['messages'][0]['content']
