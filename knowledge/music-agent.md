# Triceratops music-agent knowledge

## Reliable operation

- Treat the DAW transport, attached MIDI and attached audio as live evidence.
- Analyze a source before editing it. Report only changes confirmed by the tool result.
- A generated score is a candidate. Learn a positive or negative preference only after explicit Keep/Accept or Reject feedback.
- Preserve an explicit melody, rhythm, range, instrumentation or section constraint through every later tool call.
- If a requested MIDI transformation is outside the declared structured operations, ask for clarification instead of claiming it was performed.

## Host integration

- Every host can receive MIDI through the plug-in output or by dragging the generated MIDI file.
- REAPER can additionally import MIDI and stems into new tracks through the supplied ReaScript bridge.
- A VST3 plug-in cannot portably enumerate or rewrite arbitrary tracks in every DAW. Host-specific bridges extend this boundary where available.

## Available local audio capabilities

- Audio analysis estimates duration, tempo, key, onsets, section boundaries and level statistics.
- Demucs performs stem separation and returns only files produced by the current request.
- Basic Pitch performs audio-to-MIDI transcription. Its result is a draft and should be inspected before arrangement work.
