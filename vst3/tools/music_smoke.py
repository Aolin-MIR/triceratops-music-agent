"""Real local model smoke test; no substituted generator or mocked MIDI."""
from pathlib import Path
import json
import time

from mido import MidiFile
from text2music.agent.midi_tools import analyze_selection, transform_midi_file
from text2music.agent.symbolic_models import generate_midi_llm


def main():
    destination = Path("text2music/artifacts/agent_runs") / ("review-smoke-" + time.strftime("%Y%m%d-%H%M%S"))
    result = generate_midi_llm(
        "A sparse piano and cello duet in D minor at 90 BPM, gentle dynamics, 4/4 time.",
        destination, max_tokens=192,
    )
    source = Path(result["midi"])
    analysis = analyze_selection(source)
    if analysis["notes"] == 0:
        raise RuntimeError("Model output contains no playable notes")
    edited = destination / "transposed.mid"
    transform_midi_file(source, "transpose", edited, operations={"transpose": 2})
    before = [event.note for track in MidiFile(source).tracks for event in track
              if event.type == "note_on" and event.velocity > 0 and event.channel != 9]
    after = [event.note for track in MidiFile(edited).tracks for event in track
             if event.type == "note_on" and event.velocity > 0 and event.channel != 9]
    if after != [min(127, note + 2) for note in before]:
        raise RuntimeError("MIDI edit did not produce the requested pitches")
    print(json.dumps({**result, "analysis": analysis, "edited": str(edited),
                      "verified": "real model output + analysis + transpose"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
