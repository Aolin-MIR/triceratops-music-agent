"""Explicit, validated button operations that never instantiate a chat client."""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
from typing import Callable

# Presets are identified by action IDs, never inferred from translated button text.
DIRECT_ACTIONS = {
    "inspect_project": ("inspect_project", {}),
    "analyze_selected_midi": ("analyze_selected_midi", {}),
    "analyze_audio": ("analyze_audio", {}),
    "continue_midi": ("continue_midi", {"bar_count": 4}),
    "more_energy": ("transform_midi", {"request": "Increase velocity by 12; preserve pitch and melody",
                                      "operations": {"velocity_delta": 12}}),
    "tighten_timing": ("transform_midi", {"request": "Quantize to sixteenth notes; preserve pitches",
                                         "operations": {"quantize": True}}),
    "transform_midi": ("transform_midi", {}),
    "infill_midi": ("infill_midi", {}),
    "separate_stems": ("separate_stems", {}),
    "audio_to_midi": ("audio_to_midi", {}),
    "undo": ("undo", {}), "accept": ("accept", {}), "reject": ("reject", {}),
    "status": ("status", {}), "list_capabilities": ("list_capabilities", {}),
}


def validate_arguments(tool: str, arguments: dict) -> None:
    from jsonschema import Draft202012Validator
    from text2music.agent.tool_loop import tool_schemas
    schema = next((s["function"]["parameters"] for s in tool_schemas() if s["function"]["name"] == tool), None)
    if schema is None or not isinstance(arguments, dict):
        raise ValueError(f"Invalid tool arguments: {tool}")
    errors = sorted(Draft202012Validator(schema).iter_errors(arguments), key=lambda error: str(error.path))
    if errors:
        raise ValueError(f"Invalid {tool} arguments: {errors[0].message}")


def action_arguments(action: str, arguments: dict) -> tuple[str, dict]:
    if action not in DIRECT_ACTIONS:
        raise ValueError("Unknown direct action; free-form requests must use chat")
    if not isinstance(arguments, dict):
        raise ValueError("arguments must be a JSON object")
    tool, preset = DIRECT_ACTIONS[action]
    if preset and arguments:
        raise ValueError("Fixed button presets cannot be overridden; use a structured tool operation")
    values = deepcopy(preset or arguments)
    validate_arguments(tool, values)
    return tool, values


def execute_observation(tool: str, *, selection: Path | None = None, context: str = "", busy_state: str = ""):
    if tool == "inspect_project":
        return {"context": context, "busy_state": busy_state}
    if tool == "analyze_selected_midi":
        if not selection or not selection.is_file():
            raise ValueError("No MIDI file is attached")
        from text2music.agent.midi_tools import analyze_selection
        return analyze_selection(selection)
    if tool == "analyze_audio":
        from text2music.agent.audio_tools import analyze_audio, extract_audio_paths
        paths = extract_audio_paths(context)
        if not paths:
            raise ValueError("No audio file is attached")
        return analyze_audio(paths[0])
    raise ValueError(f"Unknown observation: {tool}")


def run_direct_action(action: str, *, arguments: dict, selection: Path | None = None,
                      context: str = "", execute: Callable, on_event=None, cancelled=None):
    from text2music.agent.tool_loop import OBSERVATION_TOOLS, ToolDecision
    tool, values = action_arguments(action, arguments)
    event = {"step": 1, "tool": tool, "arguments": values, "state": "running", "dispatch": "direct"}
    if on_event:
        on_event(dict(event))
    try:
        if cancelled and cancelled():
            raise RuntimeError("Operation cancelled before execution")
        if tool in OBSERVATION_TOOLS:
            result = execute_observation(tool, selection=selection, context=context)
        else:
            result = execute(tool, values)
        event.update(state="completed", result=result)
    except Exception as exc:
        event.update(state="failed", result={"error": f"{type(exc).__name__}: {exc}"})
    if on_event:
        on_event(dict(event))
    return ToolDecision(tool, values, trace=[event])
