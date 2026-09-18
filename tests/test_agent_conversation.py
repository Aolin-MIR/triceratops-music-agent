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

def test_observe_execute_and_report_actual_results():
    client = Client([Answer(tool="inspect_project"),
                     Answer(tool="transform_midi", arguments={"request": "transpose up 2 semitones"}),
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
    result = transform_midi_file(source, "降低力度", output, operations={"velocity_delta": -20})
    assert [m.velocity for t in MidiFile(output).tracks for m in t if m.type == "note_on"] == [60]
    with pytest.raises(ValueError, match="No supported"):
        transform_midi_file(source, "change something unspecified", output)


def test_cancel_prevents_next_model_or_tool_call():
    result = run_tool_loop("edit", client=Client([]), cancelled=lambda: True)
    assert "取消" in result.reply


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
