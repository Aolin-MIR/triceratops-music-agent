# Triceratops VST3

Triceratops is the DAW-neutral front end for the existing local music Agent.
It reuses the Qwen tool loop, persistent Text2Score GPU worker, validation,
self-correction, MIDI/audio analysis, preference memory, and version history.

## Use

1. Rescan VST3 plug-ins in the DAW and insert **Triceratops** on a stereo track.
2. Wait for the status to change from model loading to ready.
3. Type a request in the large message box and press **Send**.
4. Use **Drag MIDI** to drop the result onto any DAW MIDI/instrument track, or
   **Play MIDI** to send it from the plug-in at the next bar.

MIDI and audio can be loaded by button or file drag. **Capture MIDI** records
incoming plug-in MIDI. **Capture audio** records the plug-in input for analysis,
stem separation, or audio-to-MIDI.

Requests such as “make the loaded MIDI more rock, keep the melody”, “extend the
chorus”, “split this audio into stems”, “reject this version”, and “restore the
previous version” are routed by the Agent to the appropriate tool.

## Host boundary

VST3 exposes transport, tempo, time signature, PPQ position, audio input, MIDI
input, and MIDI output. It does not expose a portable API for arbitrary DAW
track creation or direct replacement of another track's clip. Triceratops uses
MIDI output and external drag-and-drop in every host. In REAPER, the optional
`Triceratops - Import from Agent.lua` bridge also creates a new track and imports
the current MIDI or generated stems when **Import to REAPER** or auto-import is
enabled. The bridge must be registered once in REAPER's Action List and its
numeric action ID reported with the supplied setup action.

## Agent foundation

The chat controller uses native model tool calls. It can answer without taking
an action, inspect host/MIDI/audio state, execute several tools in one turn, and
feed every real result or failure back to the model before it replies. There is
no keyword fallback that silently starts generation after an API failure.

Project memory stores explicit constraints, decisions and preferences separately
for each available project identity. Accept and Reject update learned musical
preferences; generating a candidate alone does not count as approval. Long
conversations retain recent turns plus a compact project summary.

The local RAG index covers this manual, the repository README, example plans,
files placed in `knowledge/`, and project notes placed under
`text2music/artifacts/agent_runs/project_notes/`. Retrieval results include their
source path so the agent can cite the basis of an answer. The index is rebuilt
with `KnowledgeBase.rebuild()` after adding or changing documents.

## Local symbolic models

The agent exposes two local symbolic-music backends alongside the original
Text2Score generator. MIDI-LLM generates multi-instrument MIDI from a natural
language request. `generate_draft.backend` accepts `auto`, `midi_llm`, or
`text2score`; `auto` prefers MIDI-LLM only after every local model file is
present. MIDI-GPT fills selected zero-based bar and track ids through the
`infill_midi` tool, while tracks outside the request are explicitly preserved.

Run `bash text2music/agent/install_symbolic_models.sh` inside WSL to install the
pinned checkpoints. The installer uses the Tsinghua/Aliyun Python mirrors and
`beta.hf-mirror.com` first. Chat requests never download a model and a missing
model is never silently replaced with another backend.

## Local debug build

The current Windows build starts the existing WSL backend at
`/mnt/e/text2score/text2music/agent/launch_vst_service.sh`. The model is loaded
once for all active Triceratops instances. It is released when the last editor
closes; a heartbeat watchdog also releases it after an abnormal DAW exit.
