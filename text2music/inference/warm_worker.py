"""Long-lived Text2Score GPU worker with automatic progress tracking & error reporting."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Add current inference directory to sys.path so samplings, config, utils can always be imported cleanly
sys.path.insert(0, str(Path(__file__).parent))

import torch
from inference import generate_with_loaded_model, load_model_once

queue = Path(os.environ.get("TEXT2SCORE_WORKER_QUEUE", "/mnt/e/text2score/text2music/artifacts/agent_runs/worker_queue"))
queue.mkdir(parents=True, exist_ok=True)
state_file = queue / "worker-state.txt"

def update_worker_state(phase: str, progress: int, detail: str) -> None:
    text = f"STATE: {phase}\nPROGRESS: {progress}\nDETAIL: {detail}\n"
    state_file.write_text(text, encoding="utf-8")

def atomic_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)

update_worker_state("loading", 10, "Checking GPU CUDA availability...")

try:
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        update_worker_state("loading", 30, f"Initializing PyTorch CUDA on {gpu_name}...")
    else:
        update_worker_state("loading", 30, "CUDA unavailable. Initializing PyTorch model...")

    update_worker_state("loading", 60, "Loading 3.4GB score model checkpoint into GPU VRAM...")
    model, device = load_model_once()
    
    device_desc = f"NVIDIA GPU ({device})" if str(device).startswith("cuda") else f"CPU ({device})"
    update_worker_state("ready", 100, f"Model warm and ready on {device_desc}")
except Exception as exc:
    import traceback
    tb = traceback.format_exc()
    update_worker_state("error", 0, f"{type(exc).__name__}: {exc}\n{tb}")
    raise

while True:
    shutdown = queue / "shutdown"
    if shutdown.exists():
        shutdown.unlink(missing_ok=True)
        update_worker_state("stopped", 0, "Worker stopped when the VST3 instance closed")
        break
    for request in sorted(queue.glob("*.request.json")):
        working = request.with_suffix(".working")
        try:
            os.replace(request, working)
        except FileNotFoundError:
            continue
        payload = json.loads(working.read_text(encoding="utf-8"))
        response = queue / f"{payload['id']}.response.json"
        progress = queue / f"{payload['id']}.progress.json"
        cancel = Path(payload["cancel_path"])
        try:
            update_worker_state("generating", 30, "Composing with the warm GPU model...")
            atomic_json(progress, {"phase": "sampling", "patches": 0, "context_limit": 0, "elapsed_seconds": 0})
            def on_progress(event: dict) -> None:
                atomic_json(progress, event)
            generate_with_loaded_model(model, device, payload["plan"], payload["output_folder"],
                                       progress_callback=on_progress, cancel_callback=cancel.exists)
            response.write_text(json.dumps({"ok": True}), encoding="utf-8")
            update_worker_state("ready", 100, f"Model warm and ready on {device_desc}")
        except InterruptedError:
            response.write_text(json.dumps({"ok": False, "cancelled": True, "error": "Generation cancelled"}), encoding="utf-8")
            update_worker_state("ready", 100, "Generation cancelled; GPU model remains warm")
        except Exception as exc:
            import traceback
            tb = traceback.format_exc()
            response.write_text(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}\n{tb}"}), encoding="utf-8")
            update_worker_state("ready", 100, f"Last task failed ({type(exc).__name__}); worker still warm")
        finally:
            working.unlink(missing_ok=True)
    time.sleep(0.2)
