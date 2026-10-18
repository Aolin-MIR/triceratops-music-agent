"""Localhost service shared by the Triceratops VST3 and Audio Unit plug-ins."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from text2music.agent.knowledge import KnowledgeBase
from text2music.agent.project_memory import ProjectMemory, project_key
from text2music.agent.errors import redact_error
from text2music.agent.workspaces import scoped, workspace_scope, storage_path

HOST = "127.0.0.1"
PORT = int(os.environ.get("TRICERATOPS_PORT", "49327"))
RUNS_DIR = Path(os.environ.get(
    "TRICERATOPS_RUNS_DIR",
    str(Path(__file__).resolve().parents[1] / "artifacts" / "agent_runs"),
))
STATUS = RUNS_DIR / "reaper-status.txt"
HISTORY = RUNS_DIR / "reaper-history.jsonl"
MEMORY = RUNS_DIR / "agent-memory.json"
STATE = RUNS_DIR / "vst-service-state.json"
CONVERSATION = RUNS_DIR / "vst-conversation.jsonl"
CONVERSATION_ARCHIVE = RUNS_DIR / "vst-conversation-archive.jsonl"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Derived from this file so source and runtime copies always agree.
AGENT_DIR = Path(__file__).resolve().parent


def _workspace_path(name: str) -> Path:
    return storage_path(name, globals()[name])


def _find_reaper_executable() -> str:
    configured = os.environ.get("TRICERATOPS_REAPER", "")
    if configured:
        return configured if Path(configured).is_file() else ""
    candidates = [
        "/mnt/c/Program Files/REAPER (x64)/reaper.exe",
        "/mnt/c/Program Files/REAPER/reaper.exe",
        "/mnt/d/Program Files/REAPER (x64)/reaper.exe",
        "/mnt/d/Program Files/REAPER/reaper.exe",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return ""


def _import_request_dir(request_id: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{32}", request_id):
        raise ValueError("Invalid import request identifier")
    return _workspace_path("RUNS_DIR") / "reaper_imports" / request_id


def _write_reaper_command(command: str, files: str) -> str:
    """Each importer owns its command, script and receipt; other hosts cannot claim it."""
    request_id = uuid.uuid4().hex
    directory = _import_request_dir(request_id)
    directory.mkdir(parents=True, mode=0o700)
    command_file = directory / "reaper-command.txt"
    temporary = command_file.with_suffix(".txt.tmp")
    temporary.write_text(f"REQUEST_ID: {request_id}\nCOMMAND: {command}\nFILES: {files}\n", encoding="utf-8")
    os.replace(temporary, command_file)
    return request_id


def _prepare_reaper_import(command: str, files: str, expected_project: str = "") -> dict[str, Any]:
    template = AGENT_DIR / "reaper" / "Triceratops - Import from Agent.lua"
    if not template.is_file():
        raise RuntimeError("REAPER import script is missing")
    request_id = _write_reaper_command(command, files)
    directory = _import_request_dir(request_id)
    script = directory / "Triceratops - Import.lua"
    script.write_text(template.read_text(encoding="utf-8").replace(
        "local ROOT = nil -- injected by vst_service",
        "local ROOT = " + json.dumps(_windows_path(directory), ensure_ascii=False)
    ).replace("local EXPECTED_PROJECT = nil -- injected by vst_service",
              "local EXPECTED_PROJECT = " + json.dumps(expected_project, ensure_ascii=False)), encoding="utf-8")
    return {"request_id": request_id, "script_path": _windows_path(script)}


def _read_import_receipt(request_id: str) -> dict[str, Any] | None:
    directory = _import_request_dir(request_id)
    try:
        fields = dict(line.split(": ", 1) for line in
                      (directory / "reaper-import-result.txt").read_text(encoding="utf-8").splitlines()
                      if ": " in line)
    except FileNotFoundError:
        return None
    if fields.get("REQUEST_ID") != request_id:
        return None
    count = int(fields.get("IMPORTED", "0"))
    error = fields.get("ERROR", "")
    return {"request_id": request_id, "imported": count,
            "project_path": fields.get("PROJECT", ""),
            "ok": count > 0 and not error,
            "error": error or ("REAPER imported no media" if count == 0 else "")}


def _discard_reaper_import(request_id: str) -> dict[str, Any]:
    directory = _import_request_dir(request_id)
    receipt = _read_import_receipt(request_id)
    if receipt is not None:
        return receipt
    if (directory / "reaper-command.txt.taken").exists():
        raise RuntimeError("REAPER already claimed this import; verify the host before retrying")
    for name in ("reaper-command.txt", "Triceratops - Import.lua"):
        (directory / name).unlink(missing_ok=True)
    if directory.is_dir():
        (directory / "abandoned.txt").write_text("Owning REAPER project changed before import execution\n", encoding="utf-8")
    return {"request_id": request_id, "ok": False, "imported": 0,
            "error": "REAPER could not run the import. Activate the plug-in's project and retry; this pending request was discarded."}


def _reaper_import_argv(reaper_exe: str, script: Path) -> list[str]:
    if sys.platform == "darwin":
        raise RuntimeError("macOS import requires the plug-in's in-host REAPER API; no additional instance was launched")
    return [reaper_exe, "-nonewinst", _windows_path(script)]


def _trigger_reaper_import(command: str, files: str) -> dict[str, Any]:
    """Legacy command-line route; success requires this request's real receipt."""
    try:
        reaper_exe = _find_reaper_executable()
        if not reaper_exe:
            raise RuntimeError("REAPER executable not found")
        _reaper_import_argv(reaper_exe, _workspace_path("RUNS_DIR") / "Triceratops - Import.lua")  # Validate route before publishing.
        prepared = _prepare_reaper_import(command, files)
        subprocess.Popen(_reaper_import_argv(reaper_exe, Path(prepared["script_path"])),
                         start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline:
            receipt = _read_import_receipt(prepared["request_id"])
            if receipt is not None:
                return {**prepared, **receipt, "triggered": receipt["ok"], "detail": receipt["error"]}
            time.sleep(0.05)
        raise RuntimeError("REAPER did not confirm this import request; check the host before retrying")
    except Exception as exc:
        return {"triggered": False, "detail": redact_error(f"{type(exc).__name__}: {exc}")}


def _archive_and_clear_conversation() -> None:
    """Archive existing conversation turns and clear active VST conversation."""
    if _workspace_path("CONVERSATION").exists():
        try:
            content = _workspace_path("CONVERSATION").read_text(encoding="utf-8", errors="replace").strip()
            if content:
                with _workspace_path("CONVERSATION_ARCHIVE").open("a", encoding="utf-8") as archive:
                    archive.write(content + "\n")
            with _workspace_path("CONVERSATION_ARCHIVE").open("a", encoding="utf-8") as archive:
                archive.write(json.dumps({"event": "conversation_cleared"}) + "\n")
            _workspace_path("CONVERSATION").write_text("", encoding="utf-8")
        except OSError:
            pass


def _windows_to_wsl(path: str) -> Path:
    if os.name == "nt":
        return Path(path)
    match = re.match(r"^([A-Za-z]):[\\/](.*)$", path)
    if match:
        return Path("/mnt") / match.group(1).lower() / match.group(2).replace("\\", "/")
    return Path(path)


def _windows_path(path: Path) -> str:
    raw = str(path)
    match = re.match(r"^([A-Za-z]):[\\/](.*)$", raw)
    if match:
        return match.group(1).upper() + ":\\" + match.group(2).replace("/", "\\")
    parts = path.resolve().parts
    if len(parts) > 3 and parts[1] == "mnt" and len(parts[2]) == 1:
        return parts[2].upper() + ":\\" + "\\".join(parts[3:])
    return str(path)


def _write_status(state: str, progress: str, detail: str) -> None:
    """Persist the running/terminal state so the plug-in never sees a stale
    'planning' status after a request has finished or failed."""
    try:
        _workspace_path("STATUS").parent.mkdir(parents=True, exist_ok=True)
        _workspace_path("STATUS").write_text(
            f"STATE: {state}\nPROGRESS: {progress}\nDETAIL: {detail}\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def _read_status() -> dict[str, str]:
    result: dict[str, str] = {}
    try:
        for line in _workspace_path("STATUS").read_text(encoding="utf-8", errors="replace").splitlines():
            key, separator, value = line.partition(": ")
            if separator:
                result[key.lower()] = value
    except OSError:
        pass
    return result


def _history(limit: int | None = 20) -> list[dict[str, Any]]:
    if not _workspace_path("HISTORY").exists():
        return []
    result = []
    lines = _workspace_path("HISTORY").read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines if limit is None else lines[-limit:]:
        try:
            item = json.loads(line)
            if item.get("midi"):
                item["midi_windows"] = _windows_path(Path(item["midi"]))
            result.append(item)
        except json.JSONDecodeError:
            continue
    return result


def _previous_midi_version(current: Path | None) -> dict[str, Any]:
    """Follow this file's provenance, never the latest unrelated global output."""
    if current is None or not current.is_file():
        raise ValueError("Load the MIDI version whose last change should be undone")
    current_path = current.resolve()
    entry = next((item for item in reversed(_history(limit=None))
                  if item.get("midi") and _windows_to_wsl(str(item["midi"])).resolve() == current_path), None)
    parent = (entry or {}).get("parent_midi") or (entry or {}).get("source")
    if not parent:
        raise ValueError("There is no recorded prior MIDI version for the loaded file")
    previous = _windows_to_wsl(str(parent))
    if not previous.is_file():
        raise FileNotFoundError("Previous MIDI version is missing")
    if previous.resolve() == current_path:
        raise ValueError("MIDI version history contains a self-reference")
    return {"midi": str(previous), "restored_from": str(current)}


def _host_context(host: dict[str, Any]) -> str:
    raw_signature = host.get("time_signature") or [4, 4]
    if isinstance(raw_signature, str):
        numerator, separator, denominator = raw_signature.strip().partition("/")
        if separator != "/" or not numerator.strip() or not denominator.strip():
            raise ValueError("time_signature must use the form 'numerator/denominator'")
        signature = [numerator.strip(), denominator.strip()]
    elif isinstance(raw_signature, (list, tuple)) and len(raw_signature) == 2:
        signature = raw_signature
    else:
        raise ValueError("time_signature must be a two-item list or 'numerator/denominator'")
    numerator_value, denominator_value = int(signature[0]), int(signature[1])
    if numerator_value <= 0 or denominator_value <= 0:
        raise ValueError("time_signature values must be positive integers")
    return (
        f"Host: {host.get('host_application') or host.get('name', 'Audio plug-in host')}\n"
        f"Plugin format: {host.get('name', 'unknown')}\n"
        f"Tempo: {float(host.get('tempo', 120)):.2f} BPM\n"
        f"Time Signature: {numerator_value}/{denominator_value}\n"
        f"PPQ Position: {float(host.get('ppq', 0)):.3f}\n"
        f"Playing: {bool(host.get('playing', False))}\n"
        f"Looping: {bool(host.get('looping', False))}\n"
        f"Sample Rate: {float(host.get('sample_rate', 44100)):.0f} Hz"
    )


def _conversation_history(limit: int | None = None) -> list[dict[str, str]]:
    lines = []
    for path in (_workspace_path("CONVERSATION_ARCHIVE"), _workspace_path("CONVERSATION")):
        if path.exists():
            lines.extend(path.read_text(encoding="utf-8").splitlines())
    if limit is not None:
        lines = lines[-limit:]
    turns: list[dict[str, str]] = []
    for line in lines:
        try:
            item = json.loads(line)
            if item.get("event") == "conversation_cleared":
                turns.clear()
                continue
            if item.get("role") in {"user", "assistant"} and item.get("content"):
                turns.append({"role": str(item["role"]), "content": str(item["content"]),
                              "executions": item.get("executions", [])})
        except json.JSONDecodeError:
            continue
    return turns


def _compact_conversation(keep: int = 40) -> None:
    """Bound the active transcript while preserving the full archive."""
    if not _workspace_path("CONVERSATION").exists():
        return
    lines = _workspace_path("CONVERSATION").read_text(encoding="utf-8", errors="replace").splitlines()
    if len(lines) <= 200:
        return
    with _workspace_path("CONVERSATION_ARCHIVE").open("a", encoding="utf-8") as archive:
        archive.write("\n".join(lines[:-keep]) + "\n")
    temporary = _workspace_path("CONVERSATION").with_suffix(".tmp")
    temporary.write_text("\n".join(lines[-keep:]) + "\n", encoding="utf-8")
    temporary.replace(_workspace_path("CONVERSATION"))



def _persist_execution(event):
    from text2music.agent.context_window import estimate_tokens
    from text2music.agent.tool_results import ToolResultStore
    result = {key:value for key,value in event.get("result", {}).items()
              if key not in {"context_usage","trace","event"}}
    if estimate_tokens(result) > 512:
        result = ToolResultStore(_workspace_path("RUNS_DIR") / "tool-results").save(result)
    return {"tool":event["tool"],"state":event["state"],
            "arguments":event.get("arguments",{}),"result":result}


class TriceratopsState:
    def __init__(self, *, storage_root=None, workspace_id="", parent=None) -> None:
        self.storage_root = storage_root
        self.workspace_id = workspace_id
        self.parent = parent
        self.workspaces = {}
        self.session_workspaces = {}
        self.task_owner = None
        self.sessions: dict[str, float] = {}
        self.lock = threading.RLock()
        self.busy = False
        self.cancel_event = threading.Event()
        self.chat_switches = {}
        self.last_reply = "Ready."
        self.last_error = ""
        self.last_result: dict[str, Any] = {}
        self.server: ThreadingHTTPServer | None = None
        config_path = os.environ.get("TRICERATOPS_CONFIG", "")
        if config_path:
            from text2music.agent.configuration import ConfigurationJobs
            self.configuration = ConfigurationJobs(Path(config_path))
        else:
            self.configuration = None

    def for_request(self, payload):
        if self.workspace_id:
            return self
        session = str(payload.get("session", "")).strip()
        if not session or len(session) > 80:
            raise ValueError("An editor session and explicit workspace are required")
        host = payload.get("host") if isinstance(payload.get("host"), dict) else {}
        with self.lock:
            key = project_key(host) if host else self.session_workspaces.get(session)
            if not key:
                raise ValueError("Project identity is missing; choose a workspace inside the plug-in")
            if key not in self.workspaces:
                state = TriceratopsState(storage_root=RUNS_DIR / "workspaces" / key,
                                        workspace_id=key, parent=self)
                state.configuration = self.configuration
                state.server = self.server
                self.workspaces[key] = state
            self.session_workspaces[session] = key
            return self.workspaces[key]

    def run_accepted_chat(self, payload):
        try:
            self.run_chat(payload)
        finally:
            root = self.parent or self
            with root.lock:
                if root.task_owner is self:
                    root.task_owner = None

    @scoped
    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            data = {
                "service": "ready", "version": "1.0.1b", "app_version": "1.0.1b", "api_version": 3,
                "backend_entry": str(Path(__file__).resolve()), "workspace_id": self.workspace_id, "busy": self.busy, "sessions": len(self.sessions),
                "reply": self.last_reply, "error": self.last_error,
                "result": self.last_result, "history": _history(),
                "chat_switches": dict(self.chat_switches),
            }
        if self.configuration:
            public = self.configuration.snapshot()
            data["setup_required"] = public["setup_required"]
            data["configuration_job"] = public["job"]
            data["api_requirement"] = public["api_requirement"]
        data.update(_read_status())
        return data


    def session_watchdog(self) -> None:
        while self.server is not None:
            time.sleep(10.0)
            now = time.monotonic()
            with self.lock:
                if self.busy:
                    continue
                stale = [session for session, seen in self.sessions.items()
                         if now - seen > 120.0]
                for session in stale:
                    self.sessions.pop(session, None)


    @scoped
    def append_turn(self, role: str, content: str, tool: str = "", executions=None) -> None:
        entry = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "role": role, "content": content}
        if tool:
            entry["tool"] = tool
        if executions:
            entry["executions"] = [_persist_execution(e) for e in executions
                                   if e.get("state") in {"completed", "failed"}]
        with _workspace_path("CONVERSATION").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    @scoped
    def run_chat(self, payload: dict[str, Any]) -> None:
        message = str(payload.get("message", "")).strip()
        language = str(payload.get("language", "zh"))
        host = payload.get("host") if isinstance(payload.get("host"), dict) else {}
        midi_raw = str(payload.get("midi_path", "")).strip()
        audio_raw = str(payload.get("audio_path", "")).strip()
        midi = _windows_to_wsl(midi_raw) if midi_raw else None
        audio = _windows_to_wsl(audio_raw) if audio_raw else None
        try:
            context = _host_context(host)
            context += "\nDefault reply language: " + ("Chinese" if language == "zh" else "English") + ". Follow an explicit user request for another language."
        except (ValueError, TypeError) as exc:
            with self.lock:
                self.last_error = f"Invalid host context: {exc}"
                self.last_reply = self.last_error
                self.busy = False
            _write_status("failed", "100", self.last_error)
            return
        if audio and audio.exists():
            context += f"\nAudio: {audio}"
        if midi and midi.exists():
            context += f"\nAttached MIDI: {midi}"
        with self.lock:
            self.busy = True
            self.last_error = ""
            self.last_reply = ""
            self.last_result = {}
            try:
                _workspace_path("STATUS").parent.mkdir(parents=True, exist_ok=True)
                _workspace_path("STATUS").write_text("STATE: planning\nPROGRESS: 15\nDETAIL: Observing project context and planning the score\n", encoding="utf-8")
            except OSError:
                pass
        conversation = _conversation_history()
        self.append_turn("user", message)

        normalized = message.lower()
        if normalized in {"status", "查看状态", "查看当前状态", "当前状态"}:
            with self.lock:
                self.last_result = {"tool": "status", "trace": ["lightweight status tool"]}
                self.last_reply = "Current state is available in the status panel."
                self.busy = False
            _write_status("completed", "100", self.last_reply)
            self.append_turn("assistant", self.last_reply, "status")
            return

        # Heavy music/ML modules are imported only for requests that need them,
        # after the HTTP server is already listening.
        # Each generation adapter starts only the model needed for that request.
        try:
            from text2music.agent.capabilities import record_feedback, load_memory, memory_context
            from text2music.agent.midi_tools import transform_midi_file
            from text2music.agent.tool_loop import run_tool_loop, FACTUAL_REPORT_TOOLS
            from text2music.agent.model_job import run_model_job as _run_model_job
            def run_model_job(action, parameters, **options):
                return _run_model_job(action, parameters, run_root=_workspace_path("RUNS_DIR"), **options)
            from text2music.agent.symbolic_models import model_status

            project_memory = ProjectMemory(_workspace_path("RUNS_DIR"), self.workspace_id or project_key(host))
            knowledge = KnowledgeBase(
                _workspace_path("RUNS_DIR") / "knowledge-index.json",
                [PROJECT_ROOT / "readme.md", PROJECT_ROOT / "vst3" / "README.md",
                 PROJECT_ROOT / "knowledge", _workspace_path("RUNS_DIR") / "project_notes"],
            )
            context += "\n" + memory_context(load_memory(_workspace_path("MEMORY")))
            context += "\n" + project_memory.context(include_summary=False)
            result: dict[str, Any] = {}
            def execute(tool, arguments):
                nonlocal result, midi
                request_text = str(arguments.get("request") or message)
                musical_context = project_memory.music_context()
                if tool == "generate_draft" and musical_context:
                    request_text += "\nPersistent musical requirements: " + json.dumps(musical_context, ensure_ascii=False)
                result = {"tool": tool, **({"context_usage": result["context_usage"]} if "context_usage" in result else {})}
                if tool == "update_music_context":
                    result.update(project_memory.update_music_context(arguments["updates"], message))
                    reply = "Musical requirements updated."
                elif tool == "status":
                    result["status"] = _read_status()
                    reply = "Current service status retrieved."
                elif tool == "cancel":
                    current = _read_status()
                    run = current.get("run", "")
                    if run:
                        (Path(run) / "cancel").write_text("cancelled from VST3\n", encoding="utf-8")
                    reply = "Cancellation requested."
                elif tool in {"accept", "reject"}:
                    record_feedback(_workspace_path("MEMORY"), _workspace_path("HISTORY"), tool)
                    reply = "Preference saved." if tool == "accept" else "Version rejected and preference saved."
                elif tool == "undo":
                    previous = _previous_midi_version(midi)
                    previous_path = Path(str(previous["midi"]))
                    result["midi"] = str(previous_path)
                    result["midi_windows"] = _windows_path(previous_path)
                    result["restored_version"] = previous
                    reply = "The prior MIDI version is restored in the plug-in."
                elif tool == "transform_midi":
                    if not midi or not midi.exists():
                        raise ValueError("Drop or capture a MIDI clip before asking for an edit")
                    output = _workspace_path("RUNS_DIR") / "vst_midi" / f"revision-{uuid.uuid4().hex}.mid"
                    output.parent.mkdir(parents=True, exist_ok=True)
                    operations = dict(arguments.get("operations") or {})
                    if "protect_melody_track" in operations:
                        operations["preserve_melody"] = operations.pop("protect_melody_track")
                    transformed = transform_midi_file(midi, request_text, output, operations=operations)
                    result.update(transformed)
                    result["midi"] = str(output)
                    result["midi_windows"] = _windows_path(output)
                    reply = "The revised MIDI clip is ready."
                elif tool == "continue_midi":
                    if not midi or not midi.is_file():
                        raise ValueError("Load or capture MIDI before asking for a continuation")
                    output = _workspace_path("RUNS_DIR") / "vst_midi" / f"continuation-{uuid.uuid4().hex}.mid"
                    result.update(run_model_job("continue_midi", dict(source=midi, destination=output,
                        bar_count=arguments.get("bar_count", 4)), cancelled=self.cancel_event.is_set))
                    result["midi_windows"] = _windows_path(output)
                    reply = f"MIDI-GPT generated {result['added_bars']} new bars after the original clip."
                elif tool == "infill_midi":
                    if not midi or not midi.exists():
                        raise ValueError("Drop or capture a MIDI clip before asking for generative infill")
                    output = _workspace_path("RUNS_DIR") / "vst_midi" / f"infill-{uuid.uuid4().hex}.mid"
                    generated = run_model_job("infill_midi", dict(
                        source=midi, destination=output,
                        track_ids=arguments.get("track_ids") or [],
                        bar_ids=arguments.get("bar_ids") or [],
                        seed=int(arguments.get("seed", -1)),
                        temperature=float(arguments.get("temperature", 1.0)),
                    ), cancelled=self.cancel_event.is_set)
                    result.update(generated)
                    result["midi_windows"] = _windows_path(output)
                    reply = "MIDI-GPT infill is ready."
                elif tool == "separate_stems":
                    if not audio or not audio.exists():
                        raise ValueError("Drop an audio file or capture plug-in input first")
                    paths = run_model_job("separate_stems", dict(path=audio,
                        output_dir=_workspace_path("RUNS_DIR") / "vst_stems" / uuid.uuid4().hex),
                        cancelled=self.cancel_event.is_set)["files"]
                    result["files"] = [_windows_path(Path(path)) for path in paths]
                    reply = f"Separated {len(paths)} stems."
                elif tool == "audio_to_midi":
                    if not audio or not audio.exists():
                        raise ValueError("Drop an audio file or capture plug-in input first")
                    paths = run_model_job("audio_to_midi", dict(path=audio,
                        output_dir=_workspace_path("RUNS_DIR") / "vst_audio_midi" / uuid.uuid4().hex),
                        cancelled=self.cancel_event.is_set)["files"]
                    result["midi"] = str(paths[0])
                    result["midi_windows"] = _windows_path(Path(paths[0]))
                    runtime_path = Path(paths[0]).parent / "runtime-device.json"
                    result["runtime"] = json.loads(runtime_path.read_text(encoding="utf-8"))
                    result["note_count"] = result["runtime"]["note_count"]
                    reply = "Audio-to-MIDI conversion is ready."
                elif tool == "generate_draft":
                    requested_backend = str(arguments.get("backend", "auto"))
                    backend = "midi_llm" if requested_backend == "auto" else requested_backend
                    if backend == "midi_llm":
                        entry = run_model_job("generate_draft", dict(
                            prompt=request_text, output_dir=_workspace_path("RUNS_DIR") / "midi_llm" / uuid.uuid4().hex,
                            max_tokens=int(arguments.get("max_tokens", 768)),
                            constraints=arguments.get("constraints"),
                        ), cancelled=self.cancel_event.is_set)
                        history_entry = {**entry, "request": request_text,
                                         "time": time.strftime("%Y-%m-%d %H:%M:%S")}
                        with _workspace_path("HISTORY").open("a", encoding="utf-8") as handle:
                            handle.write(json.dumps(history_entry, ensure_ascii=False) + "\n")
                    else:
                        raise ValueError("Unsupported generation backend; select MIDI-LLM")
                    result.update(entry)
                    if entry.get("midi"):
                        result["midi_windows"] = _windows_path(Path(entry["midi"]))
                    if entry.get("plan"):
                        result["plan_windows"] = _windows_path(Path(entry["plan"]))
                    reply = "Generation cancelled." if entry.get("cancelled") else "The generated MIDI clip is ready."
                elif tool == "search_knowledge":
                    matches = knowledge.search(str(arguments.get("query", "")),
                                               limit=int(arguments.get("limit", 5)))
                    result["matches"] = matches
                    reply = f"Retrieved {len(matches)} knowledge passages."
                elif tool == "remember_fact":
                    result.update(project_memory.remember(str(arguments.get("fact", "")),
                                                         str(arguments.get("category", "constraint"))))
                    reply = "Project memory updated."
                elif tool == "forget_fact":
                    result.update(project_memory.forget(str(arguments.get("text", ""))))
                    reply = "Project memory updated."
                elif tool == "update_fact":
                    result.update(project_memory.update(str(arguments.get("text", "")),
                                                        str(arguments.get("fact", "")),
                                                        str(arguments.get("category", "constraint"))))
                    reply = "Project memory updated."
                elif tool == "recall_facts":
                    result.update(project_memory.recall(str(arguments.get("text", ""))))
                    reply = "Saved project memory read."
                elif tool == "list_capabilities":
                    from text2music.agent.tool_loop import DESCRIPTIONS
                    result["capabilities"] = DESCRIPTIONS
                    result["models"] = model_status()
                    reply = "Current capabilities retrieved."
                else:
                    raise ValueError(f"Unsupported action: {tool}")
                if result.get("midi"):
                    if tool in {"transform_midi", "infill_midi", "continue_midi"}:
                        result["parent_midi"] = str(midi)
                    midi = Path(result["midi"])
                    if tool in {"transform_midi", "infill_midi", "continue_midi", "audio_to_midi"}:
                        entry = {**result, "request": request_text, "time": time.strftime("%Y-%m-%d %H:%M:%S")}
                        with _workspace_path("HISTORY").open("a", encoding="utf-8") as handle:
                            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
                return {**result, "reply": reply}

            execution_events = {}
            def on_event(event):
                execution_events[event["step"], event["tool"]] = dict(event)
                with self.lock:
                    self.last_result = {**result, "event": event, "trace": list(execution_events.values())}
                _write_status("working", "30", f"{event['tool']}: {event['state']}")

            from text2music.agent.direct_actions import run_direct_action
            action = str(payload.get("action", ""))
            if action:
                decision = run_direct_action(action, arguments=payload.get("arguments", {}),
                                             selection=midi, context=context, execute=execute,
                                             on_event=on_event, cancelled=self.cancel_event.is_set)
            else:
                from text2music.agent.tool_results import ToolResultStore
                decision = run_tool_loop(message, result_store=ToolResultStore(_workspace_path("RUNS_DIR") / "tool-results"), context=context,
                                         selection=midi if midi and midi.exists() else None,
                                         conversation=conversation, execute=execute, on_event=on_event,
                                         cancelled=self.cancel_event.is_set,
                                         on_context=lambda report: result.update(context_usage=report),
                                         chat_backend=str(payload.get("chat_backend", "")))
            result["request_session"] = str(payload.get("session", ""))
            result["music_context"] = project_memory.music_context()
            result["trace"] = decision.trace
            reply = decision.reply
            report_error = ""
            failures = [event for event in decision.trace if event.get("state") == "failed"]
            cancelled = self.cancel_event.is_set()
            if cancelled:
                result["cancelled"] = True
                reply = "任务已取消，音乐任务已停止，本地聊天模型保留驻留。" if language == "zh" else "Task cancelled; music task stopped, local chat model stays resident."
            elif failures:
                from text2music.agent.operation_report import operation_report
                reply, report_error = operation_report(failures[-1]["tool"], [failures[-1]], language=language)
            elif payload.get("action") or result.get("tool") in FACTUAL_REPORT_TOOLS:
                from text2music.agent.operation_report import operation_report
                reply, report_error = operation_report(decision.tool, decision.trace, language=language)
            elif not decision.trace:
                result["execution"] = "reply_only"
                prefix = "对话回复（本轮未执行工具）：\n" if language == "zh" else "Conversation reply (no tool executed this turn):\n"
                reply = prefix + reply
            with self.lock:
                self.last_result = result
                self.last_reply = reply
                self.last_error = report_error
            _write_status("cancelled" if cancelled else "failed" if report_error else "completed", "100",
                          result.get("comparison", {}).get("summary", reply)
                          if isinstance(result.get("comparison"), dict) else reply)
            self.append_turn("assistant", reply, decision.tool, executions=decision.trace)
            _compact_conversation()
        except Exception as exc:
            if self.cancel_event.is_set():
                reply = "任务已取消；本地聊天模型保留驻留。" if language == "zh" else "Task cancelled; the local chat model stays resident."
                with self.lock:
                    self.last_error = ""
                    self.last_reply = reply
                    self.last_result = {"cancelled": True}
                _write_status("cancelled", "100", reply)
                self.append_turn("assistant", reply, "cancel")
                return
            import traceback
            tb = traceback.format_exc()
            err_msg = redact_error(f"{type(exc).__name__}: {exc}\n{tb}")
            with self.lock:
                self.last_error = err_msg
                self.last_reply = redact_error(f"Error: {type(exc).__name__}: {exc}")
            _write_status("failed", "100", redact_error(f"{type(exc).__name__}: {exc}"))
            self.append_turn("assistant", self.last_reply, "error")
        finally:
            with self.lock:
                self.busy = False

APP = TriceratopsState()


class Handler(BaseHTTPRequestHandler):
    server_version = "Triceratops/1.0.1b"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _json(self, code: int, data: dict[str, Any]) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _payload(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length < 0 or length > 1024 * 1024:
            raise ValueError("Request body must not exceed 1 MiB")
        if length <= 0:
            return {}
        value = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("Request body must be a JSON object")
        return value

    def do_GET(self) -> None:
        from urllib.parse import urlsplit, parse_qs
        url = urlsplit(self.path)
        if url.path == "/health":
            self._json(200, {"service":"ready", "version":"1.0.1b", "app_version":"1.0.1b", "api_version":3,
                             "busy":APP.task_owner is not None, "pid":os.getpid()})
            return
        if url.path == "/settings":
            self._json(200, APP.configuration.snapshot() if APP.configuration else {"error":"Runtime configuration path is missing"})
            return
        try:
            query = parse_qs(url.query)
            app = APP.for_request({"session":query.get("session", [""])[0]})
        except ValueError as exc:
            self._json(400, {"error":str(exc)})
            return
        with workspace_scope(app.storage_root):
            if url.path == "/status":
                self._json(200, app.snapshot())
            elif url.path == "/history":
                self._json(200, {"history":_history()})
            else:
                self._json(404, {"error":"not found"})

    def do_POST(self) -> None:
        scope = None
        try:
            try:
                payload = self._payload()
            except (ValueError, UnicodeError) as exc:
                self._json(400, {"error": f"Invalid request: {exc}"})
                return
            try:
                app = APP.for_request(payload)
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
                return
            scope = workspace_scope(app.storage_root)
            scope.__enter__()
            root = app.parent or app
            if self.path in {"/discard_import_reaper", "/import_reaper_receipt"}:
                try:
                    _import_request_dir(str(payload.get("request_id", "")))
                except ValueError as exc:
                    self._json(400, {"error": str(exc)})
                    return
            if self.path == "/chat/verify":
                from text2music.agent.llm_backend import check_chat_backend
                session = str(payload.get("session", ""))
                backend = str(payload.get("chat_backend", ""))
                if not session or len(session) > 80 or backend not in {"", "remote", "local"}:
                    self._json(400, {"error": "Invalid chat switch request"})
                    return
                with root.lock, app.lock:
                    if app.busy or root.task_owner is not None or any(v.get("state") == "verifying" for v in app.chat_switches.values()):
                        self._json(409, {"error": "Wait for the current task or model verification"})
                        return
                    if len(app.chat_switches) >= 32 and session not in app.chat_switches:
                        app.chat_switches.pop(next(iter(app.chat_switches)))
                    root.task_owner = app
                    app.chat_switches[session] = {"state": "verifying", "selection": backend}
                def verify():
                    from text2music.agent.errors import redact_error
                    try:
                        report = check_chat_backend(backend)
                        if not report.get("chat"):
                            raise ValueError("Chat is disabled; configure API or local GPU in Settings")
                        switch = {"state": "ready", "selection": backend, "report": report}
                    except Exception as exc:
                        switch = {"state": "failed", "selection": backend, "error": redact_error(str(exc))}
                    with root.lock, app.lock:
                        app.chat_switches[session] = switch
                        if root.task_owner is app:
                            root.task_owner = None
                threading.Thread(target=verify, daemon=True).start()
                self._json(202, {"accepted": True})
            elif self.path == "/settings/cancel":
                if not app.configuration:
                    self._json(503, {"error": "Runtime configuration path is missing"})
                    return
                self._json(200, app.configuration.cancel())
            elif self.path == "/settings/task":
                if not app.configuration:
                    self._json(503, {"error": "Runtime configuration path is missing"})
                    return
                def done(job):
                    with root.lock, app.lock:
                        if job["state"] == "complete":
                            from text2music.agent.runtime import configure
                            configure(app.configuration.path)
                        app.busy = False
                        if root.task_owner is app:
                            root.task_owner = None
                        app.last_result = {}
                        app.last_error = ""
                        app.last_reply = ""
                    with workspace_scope(app.storage_root):
                        _write_status("ready", "0", "Settings: " + job.get("detail", ""))
                    from text2music.agent.configuration import read_config
                    applied = read_config(app.configuration.path).get("configuration_job") == job.get("id")
                    if applied and app.server:
                        def restart():
                            # Release Python's imported device contexts, while the independent
                            # local chat server/model stays resident. The editor reconnects itself.
                            time.sleep(2)
                            app.server.shutdown()
                        threading.Thread(target=restart, daemon=True).start()
                with root.lock, app.lock:
                    if app.busy or root.task_owner is not None or any(v.get("state") == "verifying" for v in app.chat_switches.values()):
                        self._json(409, {"error": "Wait for the active task or chat verification before configuring"})
                        return
                    try:
                        root.task_owner = app
                        app.busy = True
                        result = app.configuration.start(payload, done)
                    except (ValueError, RuntimeError) as exc:
                        app.busy = False
                        root.task_owner = None
                        self._json(409 if isinstance(exc, RuntimeError) else 400, {"error": str(exc)})
                        return
                    except Exception:
                        app.busy = False
                        root.task_owner = None
                        raise
                self._json(202, result)
            elif self.path == "/session/open":
                session = str(payload.get("session") or uuid.uuid4())
                with root.lock, app.lock:
                    app.sessions[session] = time.monotonic()
                # A second editor must observe the existing task and result.
                # Only service startup resets stale status from a prior run.
                self._json(200, {"session": session, **app.snapshot(), "conversation":_conversation_history()})
            elif self.path == "/session/ping":
                session = str(payload.get("session", ""))
                with root.lock, app.lock:
                    if session in app.sessions:
                        app.sessions[session] = time.monotonic()
                self._json(200, app.snapshot())
            elif self.path == "/session/close":
                with root.lock, app.lock:
                    app.sessions.pop(str(payload.get("session", "")), None)

                self._json(200, app.snapshot())
            elif self.path == "/chat/clear":
                with root.lock, app.lock:
                    if app.busy:
                        self._json(409, {**app.snapshot(), "error": "Stop the active task before clearing chat"})
                        return
                    _archive_and_clear_conversation()
                    app.last_reply = "Ready."
                    app.last_error = ""
                    app.last_result = {}
                self._json(200, {"cleared": True, **app.snapshot()})
            elif self.path == "/cancel":
                with root.lock, app.lock:
                    current = _read_status()
                    run = current.get("run", "")
                    if run:
                        try:
                            (Path(run) / "cancel").write_text("cancelled from VST3\n", encoding="utf-8")
                        except OSError:
                            pass
                    try:
                        (_workspace_path("RUNS_DIR") / "cancel").write_text("cancelled from VST3\n", encoding="utf-8")
                    except OSError:
                        pass
                    app.cancel_event.set()
                    app.last_reply = "Cancellation requested; waiting for the active tool to stop."
                _write_status("cancelling" if app.busy else "ready", "0", app.last_reply)
                self._json(200, {"cancelled": True, **app.snapshot()})
            elif self.path == "/discard_import_reaper":
                self._json(200, {**app.snapshot(), **_discard_reaper_import(str(payload.get("request_id", "")))})
            elif self.path == "/import_reaper_receipt":
                receipt = _read_import_receipt(str(payload.get("request_id", "")))
                if receipt is None:
                    self._json(409, {**app.snapshot(), "error": "REAPER did not confirm this import request"})
                else:
                    response = {**app.snapshot(), **receipt}
                    if receipt["ok"]:
                        project = Path(receipt["project_path"]).name or "untitled project"
                        response["reply"] = f"Imported {receipt['imported']} item(s) into {project}."
                    self._json(200 if receipt["ok"] else 503, response)
            elif self.path in {"/import_reaper", "/prepare_import_reaper"}:
                file_path = str(payload.get("file", "")).strip()
                stem_files = payload.get("files", [])
                if not isinstance(stem_files, list) or any(not isinstance(path, str) or not path.strip() for path in stem_files):
                    self._json(400, {"error": "files must be an array of non-empty media paths"})
                    return
                if not file_path and not stem_files:
                    with root.lock, app.lock:
                        file_path = str(app.last_result.get("midi_windows", "")).strip()
                        stem_files = app.last_result.get("files") or []
                if file_path or stem_files:
                    win_path = _windows_path(Path(file_path)) if file_path else "|".join(stem_files)
                    command = "import_midi_file" if file_path else "import_audio_stems"
                    if self.path == "/prepare_import_reaper":
                        prepared = _prepare_reaper_import(command, win_path, str(payload.get("host", {}).get("project_path", "")))
                        self._json(200, {**app.snapshot(), **prepared})
                        return
                    trigger = _trigger_reaper_import(command, win_path)
                    response = {**app.snapshot(), "ok": trigger["triggered"], "file": win_path,
                                "bridge": trigger}
                    if trigger["triggered"] and "imported" in trigger:
                        project = Path(trigger.get("project_path", "")).name or "untitled project"
                        response["reply"] = f"Imported {trigger['imported']} item(s) into {project}."
                    if not trigger["triggered"]:
                        response["error"] = trigger["detail"]
                    self._json(200 if trigger["triggered"] else 503, response)
                else:
                    self._json(400, {**app.snapshot(), "error": "No MIDI file path available to import"})
            elif self.path == "/chat":
                if payload.get("chat_backend", "") not in {"", "remote", "local"}:
                    self._json(400, {"error": "Invalid per-message chat backend"})
                    return
                if app.configuration and app.configuration.snapshot()["setup_required"]:
                    self._json(409, {"error": "Complete model setup inside Settings before using music tools"})
                    return
                from text2music.agent.direct_actions import DIRECT_ACTIONS
                if payload.get("language", "zh") not in ("zh", "en"):
                    self._json(400, {"error": "language must be zh or en"})
                    return
                action = payload.get("action", "")
                if not isinstance(action, str) or (action and action not in DIRECT_ACTIONS):
                    self._json(400, {"error": "action must identify a supported tool"})
                    return
                if action:
                    try:
                        from text2music.agent.direct_actions import action_arguments
                        action_arguments(action, payload.get("arguments", {}))
                    except (ValueError, TypeError) as exc:
                        self._json(400, {"error": str(exc)})
                        return
                if not isinstance(payload.get("message"), str) or not payload["message"].strip():
                    self._json(400, {"error": "message must be a non-empty string"})
                    return
                try:
                    _host_context(payload.get("host") if isinstance(payload.get("host"), dict) else {})
                except (ValueError, TypeError) as exc:
                    self._json(400, {"error": f"Invalid host context: {exc}"})
                    return
                with root.lock, app.lock:
                    if app.busy or root.task_owner is not None or any(v.get("state") == "verifying" for v in app.chat_switches.values()):
                        rejected = True
                    else:
                        root.task_owner = app
                        app.cancel_event.clear()
                        app.busy = True
                        app.last_error = ""
                        app.last_reply = "Understanding your request..."
                        rejected = False
                if rejected:
                    self._json(409, {**app.snapshot(), "error": "agent is busy"})
                    return
                threading.Thread(target=app.run_accepted_chat, args=(payload,), daemon=True).start()
                self._json(202, {"accepted": True, **app.snapshot()})
            else:
                self._json(404, {"error": "not found"})
        except Exception as exc:
            self._json(500, {"error": redact_error(f"{type(exc).__name__}: {exc}")})

        finally:
            if scope is not None:
                scope.__exit__(None, None, None)



class LocalHTTPServer(ThreadingHTTPServer):
    # Windows SO_REUSEADDR can let two backends bind the same port and deliver
    # requests to different state objects. Keep the service port exclusive.
    allow_reuse_address = os.name != "nt"

    def server_bind(self):
        if os.name == "nt":
            import socket
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def main() -> None:
    _workspace_path("RUNS_DIR").mkdir(parents=True, exist_ok=True)
    server = LocalHTTPServer((HOST, PORT), Handler)
    # A competing launcher must acquire the port before publishing status.
    # Otherwise its failed bind can overwrite the active server's music task.
    _write_status("ready", "0", "Service ready")
    APP.server = server
    threading.Thread(target=APP.session_watchdog, daemon=True).start()
    _workspace_path("STATE").write_text(json.dumps({"pid": os.getpid(), "host": HOST, "port": PORT}), encoding="utf-8")
    
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
        _workspace_path("STATE").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
