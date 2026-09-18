"""Headless bridge invoked by the REAPER ReaScript; it never starts a browser."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from text2music.agent.workflow import RUNS_DIR, STATUS, run_agent, status
from text2music.agent.tool_loop import run_tool_loop
from text2music.agent.midi_tools import transform_selection
from text2music.agent.capabilities import record_feedback
from text2music.agent.audio_tools import audio_to_midi, extract_audio_paths, separate_stems


CONVERSATION = RUNS_DIR / "conversation.jsonl"
LATEST_REPLY = RUNS_DIR / "conversation-latest.txt"
COMMAND = RUNS_DIR / "reaper-command.txt"
LOOP_TRACE = RUNS_DIR / "agent-loop-latest.json"
ACTIVE = {"planning", "loading_model", "sampling", "verifying", "converting", "correcting"}


def field(text: str, key: str) -> str:
    for line in text.splitlines():
        if line.startswith(key + ": "):
            return line.partition(": ")[2]
    return ""


def reaper_path(path: Path) -> str:
    parts = path.resolve().parts
    if len(parts) > 3 and parts[1] == "mnt" and len(parts[2]) == 1:
        return parts[2].upper() + ":\\" + "\\".join(parts[3:])
    return str(path)


def append_turn(role: str, content: str, *, intent: str = "") -> None:
    entry = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "role": role, "content": content}
    if intent:
        entry["intent"] = intent
    CONVERSATION.parent.mkdir(parents=True, exist_ok=True)
    with CONVERSATION.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    if role == "assistant":
        LATEST_REPLY.write_text(content, encoding="utf-8")


def conversation_history() -> list[dict[str, str]]:
    if not CONVERSATION.exists():
        return []
    turns: list[dict[str, str]] = []
    for line in CONVERSATION.read_text(encoding="utf-8", errors="replace").splitlines()[-16:]:
        try:
            item = json.loads(line)
            if item.get("role") in {"user", "assistant"} and item.get("content"):
                turns.append({"role": item["role"], "content": str(item["content"])})
        except json.JSONDecodeError:
            continue
    return turns


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Triceratops music agent for REAPER")
    parser.add_argument("--brief-file", required=True, type=Path)
    parser.add_argument("--context-file", default=None, type=Path)
    parser.add_argument("--source-midi", default=None)
    args = parser.parse_args()

    status_path = STATUS
    status_path.parent.mkdir(parents=True, exist_ok=True)
    brief_text = args.brief_file.read_text(encoding="utf-8").strip()
    if not brief_text:
        status_path.write_text("ERROR: No music description was provided.\n", encoding="utf-8")
        return 2

    try:
        context = args.context_file.read_text(encoding="utf-8", errors="replace").strip() if args.context_file and args.context_file.exists() else ""
        current = status_path.read_text(encoding="utf-8", errors="replace") if status_path.exists() else ""
        current_state = field(current, "STATE")
        source = Path(args.source_midi) if args.source_midi else None
        has_selection = bool(source and source.exists())
        decision = run_tool_loop(brief_text, context=context, selection=source if has_selection else None,
                                 busy_state=current_state, conversation=conversation_history())
        LOOP_TRACE.write_text(json.dumps(decision.trace, ensure_ascii=False, indent=2), encoding="utf-8")
        append_turn("user", brief_text)
        append_turn("assistant", decision.reply, intent=decision.tool)

        if decision.tool == "chat":
            return 0
        if decision.tool == "status":
            detail = field(current, "DETAIL") or "The local music agent is ready."
            append_turn("assistant", f"Current state: {current_state or 'ready'}. {detail}", intent="status")
            return 0
        if decision.tool == "cancel":
            run = field(current, "RUN")
            if run:
                (Path(run) / "cancel").write_text("cancelled from chat\n", encoding="utf-8")
                append_turn("assistant", "Cancellation requested. The GPU model will remain loaded.", intent="cancel")
            else:
                append_turn("assistant", "There is no active generation to cancel.", intent="cancel")
            return 0
        if decision.tool in {"undo", "accept", "reject"}:
            command = "undo" if decision.tool == "reject" else decision.tool
            COMMAND.write_text(f"COMMAND: {command}\n", encoding="utf-8")
            feedback = RUNS_DIR / "preference-feedback.jsonl"
            with feedback.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"time": time.strftime("%Y-%m-%d %H:%M:%S"),
                                         "feedback": decision.tool, "request": brief_text},
                                        ensure_ascii=False) + "\n")
            if decision.tool in {"accept", "reject"}:
                record_feedback(RUNS_DIR / "agent-memory.json", RUNS_DIR / "reaper-history.jsonl", decision.tool)
            append_turn("assistant", "REAPER command queued and your preference was remembered.", intent=decision.tool)
            return 0
        if decision.tool == "transform_midi" and has_selection and source:
            replacement = RUNS_DIR / "midi-replacement.json"
            result = transform_selection(source, brief_text, replacement)
            COMMAND.write_text("COMMAND: replace_selection\n", encoding="utf-8")
            append_turn("assistant",
                        f"Prepared an in-place MIDI revision: {result['original_count']} source notes, "
                        f"{len(result['notes'])} replacement notes. REAPER can undo it.",
                        intent="revise")
            return 0
        if decision.tool in {"separate_stems", "audio_to_midi"}:
            audio_paths = extract_audio_paths(context)
            if not audio_paths:
                append_turn("assistant", "No readable audio item was found in the current REAPER project.",
                            intent=decision.tool)
                return 0
            output = RUNS_DIR / ("stems" if decision.tool == "separate_stems" else "audio_midi")
            status("analyzing_audio", progress=0, detail=f"Running {decision.tool}: {audio_paths[0].name}")
            files = separate_stems(audio_paths[0], output) if decision.tool == "separate_stems" else audio_to_midi(audio_paths[0], output)
            command = "import_audio_stems" if decision.tool == "separate_stems" else "import_midi_file"
            COMMAND.write_text(f"COMMAND: {command}\nFILES: {'|'.join(reaper_path(path) for path in files)}\n", encoding="utf-8")
            status("completed", progress=100, detail=f"{len(files)} file(s) prepared for REAPER")
            append_turn("assistant", f"Prepared and queued {len(files)} file(s) for import into REAPER.",
                        intent=decision.tool)
            return 0

        request = brief_text + ("\n\nREAPER project context:\n" + context if context else "")
        entry = run_agent(request, None)
        if entry.get("cancelled"):
            append_turn("assistant", "Generation cancelled. The previous MIDI versions are unchanged.", intent="cancelled")
        else:
            append_turn("assistant", "The MIDI version is ready and has been sent back to REAPER.",
                        intent=decision.tool)
        return 0
    except Exception as exc:
        status("error", error=f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
