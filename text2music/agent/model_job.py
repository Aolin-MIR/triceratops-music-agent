"""Run a single local model in an owned, cancellable process tree."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import threading
import time
from typing import Callable

from text2music.agent.process_entry import python_module_command


class TaskCancelled(RuntimeError):
    pass


def stop_process_tree(process: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        pass
    if os.name != "nt":
        # A child may outlive a parent which handled SIGTERM first.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    elif process.poll() is None:
        process.kill()
    process.wait(timeout=5)


def run_command(command: list[str], *, cancelled: Callable[[], bool],
                timeout: float = 900) -> None:
    if cancelled():
        raise TaskCancelled("Task cancelled before model launch")
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as log:
        options = ({"creationflags": subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt"
                   else {"start_new_session": True})
        process = subprocess.Popen(command, stdout=log, stderr=log, **options)
        started = time.monotonic()
        try:
            while process.poll() is None:
                if cancelled():
                    raise TaskCancelled("Task cancelled; local model process tree terminated")
                if time.monotonic() - started > timeout:
                    raise TimeoutError(f"Local model exceeded {timeout:g} seconds")
                time.sleep(0.1)
            if cancelled():
                raise TaskCancelled("Task cancelled")
            if process.returncode:
                log.seek(0)
                raise RuntimeError(f"Local model exited with code {process.returncode}: {log.read()[-4000:]}")
        except BaseException:
            stop_process_tree(process)
            raise


def run_model_job(action: str, parameters: dict, *, cancelled: Callable[[], bool]) -> dict:
    with tempfile.TemporaryDirectory(prefix="triceratops-model-") as temporary:
        root = Path(temporary)
        request, result = root / "request.json", root / "result.json"
        request.write_text(json.dumps({"action": action, "parameters": parameters}, default=str), encoding="utf-8")
        run_command(python_module_command("text2music.agent.model_job",
                     "--request", str(request), "--result", str(result),
                     "--parent-pid", str(os.getpid())),
                    cancelled=cancelled, timeout=float(os.environ.get("TRICERATOPS_MODEL_TIMEOUT", "900")))
        if not result.is_file():
            raise RuntimeError("Local model exited without a result")
        payload = json.loads(result.read_text(encoding="utf-8"))
        if "error" in payload:
            raise RuntimeError(payload["error"])
        return payload


def watch_parent(parent_pid: int) -> None:
    """A crashed backend must not leave a detached model consuming memory."""
    import psutil
    try:
        parent = psutil.Process(parent_pid)
        started = parent.create_time()
    except psutil.Error:
        parent = None
        started = None
    while parent is not None:
        try:
            if not parent.is_running() or parent.status() == psutil.STATUS_ZOMBIE or parent.create_time() != started:
                break
        except psutil.Error:
            break
        time.sleep(0.1)
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(os.getpid()), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
                       creationflags=subprocess.CREATE_NO_WINDOW)
        os._exit(1)
    # This worker was started in its own process group by run_command().
    os.killpg(os.getpgrp(), signal.SIGTERM)


def execute(action: str, parameters: dict) -> dict:
    from text2music.agent import symbolic_models, audio_tools
    p = dict(parameters)
    for key in ("source", "destination", "output_dir", "path"):
        if key in p:
            p[key] = Path(p[key])
    if action == "generate_draft":
        return symbolic_models.generate_midi_llm(**p)
    if action == "continue_midi":
        return symbolic_models.continue_midi_gpt(**p)
    if action == "infill_midi":
        return symbolic_models.infill_midi_gpt(**p)
    if action == "separate_stems":
        return {"files": [str(path) for path in audio_tools.separate_stems(**p)]}
    if action == "audio_to_midi":
        return {"files": [str(path) for path in audio_tools.audio_to_midi(**p)]}
    raise ValueError(f"Unsupported model job: {action}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--parent-pid", type=int)
    args = parser.parse_args()
    if args.parent_pid:
        threading.Thread(target=watch_parent, args=(args.parent_pid,), daemon=True).start()
    request = json.loads(args.request.read_text(encoding="utf-8"))
    try:
        result = execute(request["action"], request["parameters"])
    except Exception as exc:
        result = {"error": f"{type(exc).__name__}: {exc}"}
    args.result.write_text(json.dumps(result, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
