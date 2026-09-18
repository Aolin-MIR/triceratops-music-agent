"""DAW-neutral localhost service used by the Triceratops VST3 plug-in."""
from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from text2music.agent.knowledge import KnowledgeBase
from text2music.agent.project_memory import ProjectMemory, project_key

HOST = "0.0.0.0"
PORT = int(os.environ.get("TRICERATOPS_PORT", "49327"))
RUNS_DIR = Path(os.environ.get(
    "TEXT2SCORE_RUNS_DIR",
    "/mnt/e/text2score/text2music/artifacts/agent_runs",
))
STATUS = RUNS_DIR / "reaper-status.txt"
HISTORY = RUNS_DIR / "reaper-history.jsonl"
MEMORY = RUNS_DIR / "agent-memory.json"
STATE = RUNS_DIR / "vst-service-state.json"
CONVERSATION = RUNS_DIR / "vst-conversation.jsonl"
CONVERSATION_ARCHIVE = RUNS_DIR / "vst-conversation-archive.jsonl"
WORKER_STATE = RUNS_DIR / "worker_queue" / "worker-state.txt"
SHUTDOWN = RUNS_DIR / "worker_queue" / "shutdown"
ACTION_ID_FILE = RUNS_DIR / "triceratops-action-id.txt"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Derived from this file so source and runtime copies always agree.
AGENT_DIR = Path(__file__).resolve().parent
WORKER_SCRIPT = AGENT_DIR / "launch_reaper_worker.sh"


def _worker_alive() -> bool:
    try:
        res = subprocess.run(["pgrep", "-f", "[w]arm_worker.py"],
                             capture_output=True, text=True, timeout=5)
        return res.returncode == 0 and res.stdout.strip() != ""
    except Exception:
        return False


def _find_reaper_executable() -> str:
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


def _write_reaper_command(command: str, files: str) -> None:
    """Atomically publish a command for REAPER-side consumers (the one-shot
    import action or the agent panel, whichever claims it first)."""
    cmd_file = RUNS_DIR / "reaper-command.txt"
    try:
        tmp = cmd_file.with_suffix(".txt.tmp")
        tmp.write_text(f"COMMAND: {command}\nFILES: {files}\n", encoding="utf-8")
        os.replace(tmp, cmd_file)
    except OSError:
        pass


def _trigger_reaper_import(command: str, files: str) -> dict[str, Any]:
    """Publish the command file and trigger the registered one-shot import
    action in REAPER via its numeric command id."""
    _write_reaper_command(command, files)
    action_id = ""
    try:
        action_id = ACTION_ID_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    reaper_exe = _find_reaper_executable()
    if action_id.isdigit() and reaper_exe:
        try:
            subprocess.Popen([reaper_exe, action_id], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"triggered": True, "detail": ""}
        except Exception:
            return {"triggered": False,
                    "detail": "Failed to launch REAPER to run the import action"}
    if not action_id.isdigit():
        return {"triggered": False,
                "detail": "REAPER bridge not set up: run the 'Triceratops: Report Import Action ID' action once in REAPER (register 'Triceratops - Import from Agent.lua' via Action List > Add > Load script first)"}
    return {"triggered": False, "detail": "REAPER executable not found"}


def _archive_and_clear_conversation() -> None:
    """Archive existing conversation turns and clear active VST conversation."""
    if CONVERSATION.exists():
        try:
            content = CONVERSATION.read_text(encoding="utf-8", errors="replace").strip()
            if content:
                with CONVERSATION_ARCHIVE.open("a", encoding="utf-8") as archive:
                    archive.write(content + "\n")
            CONVERSATION.write_text("", encoding="utf-8")
        except OSError:
            pass



def _windows_to_wsl(path: str) -> Path:
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
        STATUS.parent.mkdir(parents=True, exist_ok=True)
        STATUS.write_text(
            f"STATE: {state}\nPROGRESS: {progress}\nDETAIL: {detail}\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def _read_status() -> dict[str, str]:
    result: dict[str, str] = {}
    try:
        for line in STATUS.read_text(encoding="utf-8", errors="replace").splitlines():
            key, separator, value = line.partition(": ")
            if separator:
                result[key.lower()] = value
    except OSError:
        pass
    try:
        for line in WORKER_STATE.read_text(encoding="utf-8", errors="replace").splitlines():
            key, separator, value = line.partition(": ")
            if separator:
                result["worker_" + key.lower()] = value
    except OSError:
        pass
    return result


def _history() -> list[dict[str, Any]]:
    if not HISTORY.exists():
        return []
    result = []
    for line in HISTORY.read_text(encoding="utf-8", errors="replace").splitlines()[-20:]:
        try:
            item = json.loads(line)
            if item.get("midi"):
                item["midi_windows"] = _windows_path(Path(item["midi"]))
            result.append(item)
        except json.JSONDecodeError:
            continue
    return result


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
        f"Host: {host.get('name', 'VST3 host')}\n"
        f"Tempo: {float(host.get('tempo', 120)):.2f} BPM\n"
        f"Time Signature: {numerator_value}/{denominator_value}\n"
        f"PPQ Position: {float(host.get('ppq', 0)):.3f}\n"
        f"Playing: {bool(host.get('playing', False))}\n"
        f"Looping: {bool(host.get('looping', False))}\n"
        f"Sample Rate: {float(host.get('sample_rate', 44100)):.0f} Hz"
    )


def _conversation_history(limit: int = 8) -> list[dict[str, str]]:
    if not CONVERSATION.exists():
        return []
    turns: list[dict[str, str]] = []
    for line in CONVERSATION.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
        try:
            item = json.loads(line)
            if item.get("role") in {"user", "assistant"} and item.get("content"):
                turns.append({"role": str(item["role"]), "content": str(item["content"])})
        except json.JSONDecodeError:
            continue
    return turns


def _compact_conversation(keep: int = 40) -> None:
    """Bound the active transcript while preserving the full archive."""
    if not CONVERSATION.exists():
        return
    lines = CONVERSATION.read_text(encoding="utf-8", errors="replace").splitlines()
    if len(lines) <= 200:
        return
    with CONVERSATION_ARCHIVE.open("a", encoding="utf-8") as archive:
        archive.write("\n".join(lines[:-keep]) + "\n")
    temporary = CONVERSATION.with_suffix(".tmp")
    temporary.write_text("\n".join(lines[-keep:]) + "\n", encoding="utf-8")
    temporary.replace(CONVERSATION)


class TriceratopsState:
    def __init__(self) -> None:
        self.sessions: dict[str, float] = {}
        self.ever_opened = False
        self.lock = threading.RLock()
        self.busy = False
        self.cancel_event = threading.Event()
        self.last_activity = time.monotonic()
        self.last_reply = "Ready."
        self.last_error = ""
        self.last_result: dict[str, Any] = {}
        self.server: ThreadingHTTPServer | None = None

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            data = {
                "service": "ready", "busy": self.busy, "sessions": len(self.sessions),
                "reply": self.last_reply, "error": self.last_error,
                "result": self.last_result, "history": _history(),
            }
        data.update(_read_status())
        return data

    def start_worker(self) -> None:
        """Idempotently ensure the GPU worker process is alive."""
        if _worker_alive():
            return

        try:
            SHUTDOWN.unlink(missing_ok=True)
            WORKER_STATE.parent.mkdir(parents=True, exist_ok=True)
            WORKER_STATE.write_text("STATE: loading\nPROGRESS: 10\nDETAIL: Starting local GPU music service\n", encoding="utf-8")
        except OSError:
            pass

        script = WORKER_SCRIPT if WORKER_SCRIPT.exists() else None
        if script is None:
            try:
                WORKER_STATE.write_text(
                    "STATE: error\nPROGRESS: 0\nDETAIL: launch_reaper_worker.sh not found next to vst_service.py\n",
                    encoding="utf-8")
            except OSError:
                pass
            return
        try:
            log_file = (RUNS_DIR / "worker_output.log").open("a", encoding="utf-8")
            subprocess.Popen(["bash", str(script)], start_new_session=True,
                             stdout=log_file, stderr=log_file)
        except Exception as exc:
            try:
                WORKER_STATE.write_text(
                    f"STATE: error\nPROGRESS: 0\nDETAIL: Failed to launch worker: {exc}\n",
                    encoding="utf-8")
            except OSError:
                pass

    def open_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        session = str(payload.get("session", ""))
        with self.lock:
            if session:
                self.sessions[session] = time.monotonic()
                self.last_activity = time.monotonic()
            self.ever_opened = True
        # Always trigger worker check/start when a plugin instance opens
        self.start_worker()
        return self.snapshot()

    def stop_when_unused(self) -> None:
        idle_seconds = max(5, int(os.environ.get("TRICERATOPS_GPU_IDLE_SECONDS", "900")))
        deadline = time.monotonic() + idle_seconds
        while time.monotonic() < deadline:
            time.sleep(min(10.0, max(0.1, deadline - time.monotonic())))
            with self.lock:
                if self.sessions or self.busy:
                    return
        with self.lock:
            if self.sessions or self.busy:
                return
            if time.monotonic() - self.last_activity < idle_seconds:
                return
            SHUTDOWN.parent.mkdir(parents=True, exist_ok=True)
            SHUTDOWN.write_text("idle timeout\n", encoding="utf-8")
        _write_status("ready", "0", "Agent ready; GPU model released after idle timeout")

    def session_watchdog(self) -> None:
        while self.server is not None:
            time.sleep(10.0)
            now = time.monotonic()
            became_empty = False
            with self.lock:
                if self.busy:
                    continue
                stale = [session for session, seen in self.sessions.items()
                         if now - seen > 120.0]
                for session in stale:
                    self.sessions.pop(session, None)
                became_empty = bool(stale) and not self.sessions
            if became_empty:
                threading.Thread(target=self.stop_when_unused, daemon=True).start()

    def append_turn(self, role: str, content: str, tool: str = "") -> None:
        entry = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "role": role, "content": content}
        if tool:
            entry["tool"] = tool
        with CONVERSATION.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def run_chat(self, payload: dict[str, Any]) -> None:
        message = str(payload.get("message", "")).strip()
        host = payload.get("host") if isinstance(payload.get("host"), dict) else {}
        midi_raw = str(payload.get("midi_path", "")).strip()
        audio_raw = str(payload.get("audio_path", "")).strip()
        midi = _windows_to_wsl(midi_raw) if midi_raw else None
        audio = _windows_to_wsl(audio_raw) if audio_raw else None
        context = _host_context(host)
        if audio and audio.exists():
            context += f"\nAudio: {audio}"
        with self.lock:
            self.busy = True
            self.last_activity = time.monotonic()
            self.last_error = ""
            self.last_reply = ""
            self.last_result = {}
            try:
                STATUS.parent.mkdir(parents=True, exist_ok=True)
                STATUS.write_text("STATE: planning\nPROGRESS: 15\nDETAIL: Observing project context and planning the score\n", encoding="utf-8")
            except OSError:
                pass
        conversation = _conversation_history(24)
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
        # Make sure the GPU worker survived since the session opened; if it
        # crashed or was stopped, restart it before the request queues work.
        try:
            from text2music.agent.audio_tools import audio_to_midi, separate_stems
            from text2music.agent.capabilities import record_feedback, load_memory, memory_context
            from text2music.agent.midi_tools import transform_midi_file
            from text2music.agent.symbolic_models import (
                generate_midi_llm, infill_midi_gpt, model_status, release_text2score_worker,
            )
            from text2music.agent.tool_loop import run_tool_loop
            from text2music.agent.workflow import run_agent

            project_memory = ProjectMemory(RUNS_DIR, project_key(host))
            knowledge = KnowledgeBase(
                RUNS_DIR / "knowledge-index.json",
                [PROJECT_ROOT / "readme.md", PROJECT_ROOT / "vst3" / "README.md",
                 PROJECT_ROOT / "text2music" / "artifacts" / "example_plans",
                 PROJECT_ROOT / "knowledge", RUNS_DIR / "project_notes"],
            )
            context += "\n" + memory_context(load_memory(MEMORY))
            context += "\n" + project_memory.context()
            result: dict[str, Any] = {}
            def execute(tool, arguments):
                nonlocal result, midi
                request_text = str(arguments.get("request") or message)
                result = {"tool": tool}
                if tool == "status":
                    result["status"] = _read_status()
                    reply = "Current service status retrieved."
                elif tool == "cancel":
                    current = _read_status()
                    run = current.get("run", "")
                    if run:
                        (Path(run) / "cancel").write_text("cancelled from VST3\n", encoding="utf-8")
                    reply = "Cancellation requested."
                elif tool in {"accept", "reject"}:
                    record_feedback(MEMORY, HISTORY, tool)
                    reply = "Preference saved." if tool == "accept" else "Version rejected and preference saved."
                elif tool == "undo":
                    versions = [item for item in _history() if item.get("midi")]
                    previous = versions[-2] if len(versions) >= 2 else None
                    if previous is None:
                        raise ValueError("There is no prior MIDI version to restore")
                    previous_path = Path(str(previous["midi"]))
                    if not previous_path.is_file():
                        raise FileNotFoundError("Previous MIDI version is missing")
                    result["midi"] = str(previous_path)
                    result["midi_windows"] = _windows_path(previous_path)
                    result["restored_version"] = previous
                    reply = "The prior MIDI version is restored in the plug-in."
                elif tool == "transform_midi":
                    if not midi or not midi.exists():
                        raise ValueError("Drop or capture a MIDI clip before asking for an edit")
                    output = RUNS_DIR / "vst_midi" / f"revision-{uuid.uuid4().hex}.mid"
                    output.parent.mkdir(parents=True, exist_ok=True)
                    transformed = transform_midi_file(midi, request_text, output, operations=arguments.get("operations"))
                    result.update(transformed)
                    result["midi"] = str(output)
                    result["midi_windows"] = _windows_path(output)
                    reply = "The revised MIDI clip is ready."
                elif tool == "infill_midi":
                    if not midi or not midi.exists():
                        raise ValueError("Drop or capture a MIDI clip before asking for generative infill")
                    release_text2score_worker(RUNS_DIR)
                    output = RUNS_DIR / "vst_midi" / f"infill-{uuid.uuid4().hex}.mid"
                    generated = infill_midi_gpt(
                        midi, output,
                        track_ids=arguments.get("track_ids") or [],
                        bar_ids=arguments.get("bar_ids") or [],
                        seed=int(arguments.get("seed", -1)),
                        temperature=float(arguments.get("temperature", 1.0)),
                    )
                    result.update(generated)
                    result["midi_windows"] = _windows_path(output)
                    reply = "MIDI-GPT infill is ready."
                elif tool == "separate_stems":
                    if not audio or not audio.exists():
                        raise ValueError("Drop an audio file or capture plug-in input first")
                    paths = separate_stems(audio, RUNS_DIR / "vst_stems" / uuid.uuid4().hex)
                    result["files"] = [_windows_path(path) for path in paths]
                    reply = f"Separated {len(paths)} stems."
                elif tool == "audio_to_midi":
                    if not audio or not audio.exists():
                        raise ValueError("Drop an audio file or capture plug-in input first")
                    paths = audio_to_midi(audio, RUNS_DIR / "vst_audio_midi" / uuid.uuid4().hex)
                    result["midi"] = str(paths[0])
                    result["midi_windows"] = _windows_path(paths[0])
                    reply = "Audio-to-MIDI conversion is ready."
                elif tool == "generate_draft":
                    requested_backend = str(arguments.get("backend", "auto"))
                    installed = model_status()
                    backend = ("midi_llm" if installed["midi_llm"]["ready"] else "text2score") \
                        if requested_backend == "auto" else requested_backend
                    request = request_text + "\n\nVST3 host context:\n" + context
                    if backend == "midi_llm":
                        release_text2score_worker(RUNS_DIR)
                        entry = generate_midi_llm(
                            request_text, RUNS_DIR / "midi_llm" / uuid.uuid4().hex,
                            max_tokens=int(arguments.get("max_tokens", 768)),
                        )
                        history_entry = {**entry, "request": request_text,
                                         "time": time.strftime("%Y-%m-%d %H:%M:%S")}
                        with HISTORY.open("a", encoding="utf-8") as handle:
                            handle.write(json.dumps(history_entry, ensure_ascii=False) + "\n")
                    elif backend == "text2score":
                        self.start_worker()
                        entry = run_agent(request)
                    else:
                        raise ValueError(f"Unknown generation backend: {backend}")
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
                elif tool == "list_capabilities":
                    from text2music.agent.tool_loop import DESCRIPTIONS
                    result["capabilities"] = DESCRIPTIONS
                    result["models"] = model_status()
                    reply = "Current capabilities retrieved."
                else:
                    raise ValueError(f"Unsupported action: {tool}")
                if result.get("midi"):
                    midi = Path(result["midi"])
                    if tool in {"transform_midi", "infill_midi", "audio_to_midi"}:
                        entry = {**result, "request": request_text, "time": time.strftime("%Y-%m-%d %H:%M:%S")}
                        with HISTORY.open("a", encoding="utf-8") as handle:
                            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
                self._queue_reaper_import(result)
                return {**result, "reply": reply}

            def on_event(event):
                with self.lock:
                    self.last_result = {**result, "event": event}
                _write_status("working", "30", f"{event['tool']}: {event['state']}")

            decision = run_tool_loop(message, context=context,
                                     selection=midi if midi and midi.exists() else None,
                                     conversation=conversation, execute=execute, on_event=on_event,
                                     cancelled=self.cancel_event.is_set)
            result["trace"] = decision.trace
            reply = decision.reply
            with self.lock:
                self.last_result = result
                self.last_reply = reply
            _write_status("completed", "100",
                          result.get("comparison", {}).get("summary", reply)
                          if isinstance(result.get("comparison"), dict) else reply)
            self.append_turn("assistant", reply, decision.tool)
            _compact_conversation()
            if len(conversation) >= 20:
                compact = " | ".join(f"{turn['role']}: {turn['content'][:300]}" for turn in conversation[-20:])
                project_memory.set_summary(compact)
        except Exception as exc:
            import traceback
            tb = traceback.format_exc()
            err_msg = f"{type(exc).__name__}: {exc}\n{tb}"
            with self.lock:
                self.last_error = err_msg
                self.last_reply = f"Error: {type(exc).__name__}: {exc}"
            _write_status("failed", "100", f"{type(exc).__name__}: {exc}")
            self.append_turn("assistant", self.last_reply, "error")
        finally:
            with self.lock:
                self.busy = False

    def _queue_reaper_import(self, result: dict[str, Any]) -> None:
        # Write-only on purpose: the explicit /import_reaper endpoint (used by
        # the plug-in) triggers REAPER; triggering here too would double-import
        # when the plug-in auto-import is enabled.
        try:
            if result.get("files"):
                _write_reaper_command("import_audio_stems",
                                      "|".join(str(f) for f in result["files"]))
            elif result.get("midi_windows"):
                _write_reaper_command("import_midi_file", str(result["midi_windows"]))
            elif result.get("midi"):
                _write_reaper_command("import_midi_file",
                                      _windows_path(Path(result["midi"])))
        except OSError:
            pass


APP = TriceratopsState()


class Handler(BaseHTTPRequestHandler):
    server_version = "Triceratops/1.0"

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
        if length <= 0:
            return {}
        value = json.loads(self.rfile.read(length).decode("utf-8"))
        return value if isinstance(value, dict) else {}

    def do_GET(self) -> None:
        if self.path in {"/health", "/status"}:
            self._json(200, APP.snapshot())
        elif self.path == "/history":
            self._json(200, {"history": _history()})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        try:
            payload = self._payload()
            if self.path == "/session/open":
                session = str(payload.get("session") or uuid.uuid4())
                with APP.lock:
                    APP.sessions[session] = time.monotonic()
                    APP.ever_opened = True
                    APP.last_reply = "Ready."
                    APP.last_error = ""
                    APP.last_result = {}
                # Clear any stale status file from a previous session so the
                # plug-in does not inherit a phantom "planning" state.
                _write_status("ready", "0", "Service ready")
                APP.start_worker()
                self._json(200, {"session": session, **APP.snapshot()})
            elif self.path == "/session/ping":
                session = str(payload.get("session", ""))
                with APP.lock:
                    if session in APP.sessions:
                        APP.sessions[session] = time.monotonic()
                        APP.last_activity = time.monotonic()
                self._json(200, APP.snapshot())
            elif self.path == "/session/close":
                with APP.lock:
                    APP.sessions.pop(str(payload.get("session", "")), None)
                    APP.last_activity = time.monotonic()
                    empty = not APP.sessions
                if empty:
                    threading.Thread(target=APP.stop_when_unused, daemon=True).start()
                self._json(200, APP.snapshot())
            elif self.path == "/chat/clear":
                _archive_and_clear_conversation()
                self._json(200, {"cleared": True, **APP.snapshot()})
            elif self.path == "/cancel":
                with APP.lock:
                    current = _read_status()
                    run = current.get("run", "")
                    if run:
                        try:
                            (Path(run) / "cancel").write_text("cancelled from VST3\n", encoding="utf-8")
                        except OSError:
                            pass
                    try:
                        (RUNS_DIR / "cancel").write_text("cancelled from VST3\n", encoding="utf-8")
                    except OSError:
                        pass
                    APP.cancel_event.set()
                    APP.last_reply = "Cancellation requested; waiting for the active tool to stop."
                _write_status("ready", "0", "Generation cancelled by user")
                self._json(200, {"cancelled": True, **APP.snapshot()})
            elif self.path == "/import_reaper":
                file_path = str(payload.get("file", "")).strip()
                if not file_path:
                    with APP.lock:
                        file_path = str(APP.last_result.get("midi_windows", "")).strip()
                if file_path:
                    win_path = _windows_path(Path(file_path))
                    trigger = _trigger_reaper_import("import_midi_file", win_path)
                    with APP.lock:
                        if trigger["triggered"]:
                            APP.last_error = ""
                            APP.last_reply = f"Importing {Path(win_path).name} into a new REAPER track..."
                        else:
                            APP.last_error = trigger["detail"]
                    self._json(200, {"ok": trigger["triggered"], "file": win_path,
                                      "bridge": trigger, **APP.snapshot()})
                else:
                    self._json(400, {"error": "No MIDI file path available to import", **APP.snapshot()})
            elif self.path == "/chat":
                with APP.lock:
                    if APP.busy:
                        rejected = True
                    else:
                        APP.cancel_event.clear()
                        APP.busy = True
                        APP.last_error = ""
                        APP.last_reply = "Understanding your request..."
                        rejected = False
                if rejected:
                    self._json(409, {"error": "agent is busy", **APP.snapshot()})
                    return
                threading.Thread(target=APP.run_chat, args=(payload,), daemon=True).start()
                self._json(202, {"accepted": True, **APP.snapshot()})
            else:
                self._json(404, {"error": "not found"})
        except Exception as exc:
            self._json(500, {"error": f"{type(exc).__name__}: {exc}"})


def main() -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    _write_status("ready", "0", "Service ready")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    APP.server = server
    threading.Thread(target=APP.session_watchdog, daemon=True).start()
    STATE.write_text(json.dumps({"pid": os.getpid(), "host": HOST, "port": PORT}), encoding="utf-8")
    
    # Automatically boot GPU worker and load PyTorch model into VRAM immediately on startup
    APP.start_worker()

    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
        STATE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
