"""Local symbolic-music model adapters.

The adapters intentionally use local, revision-pinned model files.  They never
silently fall back to a different generator when a requested model is missing.
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIDI_LLM_ROOT = Path(os.environ.get("MIDI_LLM_ROOT", PROJECT_ROOT / "third_party" / "MIDI-LLM"))
MIDI_LLM_MODEL = Path(os.environ.get("MIDI_LLM_MODEL", PROJECT_ROOT / "models" / "midi-llm"))
MIDI_GPT_MODEL = Path(os.environ.get(
    "MIDI_GPT_MODEL", PROJECT_ROOT / "models" / "midi-gpt" / "yellow_medium-final.safetensors"
))
PYTHON = Path(os.environ.get("TEXT2SCORE_PYTHON", PROJECT_ROOT / ".venv" / "bin" / "python"))
MIDI_LLM_BYTES = 3_447_788_104
MIDI_GPT_BYTES = 350_508_072


def model_status() -> dict[str, dict[str, Any]]:
    """Return honest local readiness instead of attempting network downloads."""
    llm_metadata = [MIDI_LLM_MODEL / name for name in (
        "config.json", "tokenizer.json", "tokenizer_config.json"
    )]
    llm_weights = MIDI_LLM_MODEL / "model.safetensors"
    return {
        "midi_llm": {
            "ready": MIDI_LLM_ROOT.joinpath("generate_transformers.py").is_file()
            and all(path.is_file() and path.stat().st_size > 0 for path in llm_metadata)
            and llm_weights.is_file() and llm_weights.stat().st_size == MIDI_LLM_BYTES,
            "model": str(MIDI_LLM_MODEL),
            "purpose": "text-conditioned multi-instrument MIDI generation",
        },
        "midi_gpt": {
            "ready": MIDI_GPT_MODEL.is_file() and MIDI_GPT_MODEL.stat().st_size == MIDI_GPT_BYTES,
            "model": str(MIDI_GPT_MODEL),
            "purpose": "multi-track MIDI infill and continuation",
        },
    }


def _require_model(name: str) -> None:
    status = model_status()[name]
    if not status["ready"]:
        raise RuntimeError(f"{name} is not installed completely at {status['model']}")


def release_text2score_worker(runs_dir: Path, timeout: float = 30.0) -> None:
    """Release the warm Text2Score worker before another CUDA model is loaded."""
    shutdown = runs_dir / "worker_queue" / "shutdown"
    shutdown.parent.mkdir(parents=True, exist_ok=True)
    shutdown.write_text("switching symbolic model\n", encoding="utf-8")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        check = subprocess.run(
            ["pgrep", "-f", "[w]arm_worker.py"], capture_output=True, text=True, timeout=5
        )
        if check.returncode != 0:
            return
        time.sleep(0.5)
    raise RuntimeError("Text2Score GPU worker did not release before model switch")


def generate_midi_llm(prompt: str, output_dir: Path, *, max_tokens: int = 768,
                      temperature: float = 1.0, top_p: float = 0.98) -> dict[str, Any]:
    """Run the official Transformers inference script against the local model."""
    _require_model("midi_llm")
    if not prompt.strip():
        raise ValueError("MIDI-LLM requires a non-empty musical description")
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    before = set(output_dir.rglob("*.mid"))
    command = [
        str(PYTHON), str(MIDI_LLM_ROOT / "generate_transformers.py"),
        "--model", str(MIDI_LLM_MODEL), "--prompt", prompt,
        "--output_root", str(output_dir), "--n_outputs", "1", "--no-synthesize",
        "--max_tokens", str(max(96, min(2046, int(max_tokens)))),
        "--temperature", str(float(temperature)), "--top_p", str(float(top_p)),
    ]
    started = time.monotonic()
    completed = subprocess.run(
        command, cwd=MIDI_LLM_ROOT, capture_output=True, text=True,
        timeout=int(os.environ.get("MIDI_LLM_TIMEOUT_SECONDS", "900")),
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout)[-4000:]
        raise RuntimeError(f"MIDI-LLM generation failed: {detail}")
    created = sorted(set(output_dir.rglob("*.mid")) - before, key=lambda path: path.stat().st_mtime)
    if not created:
        raise RuntimeError("MIDI-LLM completed without producing a MIDI file")
    midi = created[-1]
    return {"backend": "midi_llm", "midi": str(midi),
            "elapsed_seconds": round(time.monotonic() - started, 2)}


def infill_midi_gpt(source: Path, destination: Path, *, track_ids: list[int],
                    bar_ids: list[int], seed: int = -1, temperature: float = 1.0) -> dict[str, Any]:
    """Use MIDI-GPT to fill requested bars while preserving the rest of a score."""
    _require_model("midi_gpt")
    if not source.is_file():
        raise FileNotFoundError(source)
    if not track_ids or not bar_ids:
        raise ValueError("MIDI-GPT requires at least one track id and one bar id")
    from midigpt import Score
    from midigpt.inference import InferenceConfig, InferenceEngine, GenerationRequest, TrackPrompt

    score = Score.from_midi(str(source))
    track_count = len(score.tracks)
    selected_tracks = sorted(set(int(item) for item in track_ids))
    selected_bars = sorted(set(int(item) for item in bar_ids))
    if min(selected_tracks) < 0 or max(selected_tracks) >= track_count:
        raise ValueError(f"Track ids must be between 0 and {track_count - 1}")
    if min(selected_bars) < 0:
        raise ValueError("Bar ids must be zero-based non-negative integers")
    prompts = [
        TrackPrompt(id=track, bars=selected_bars) if track in selected_tracks
        else TrackPrompt(id=track, bars=[], ignore=True)
        for track in range(track_count)
    ]
    config = InferenceConfig(seed=int(seed), temperature=float(temperature),
                             model_dim=4, mask_mode="attention")
    started = time.monotonic()
    engine = InferenceEngine.from_checkpoint(str(MIDI_GPT_MODEL), device="cuda")
    generated = engine.session(score, GenerationRequest(tracks=prompts, config=config)).run()
    destination.parent.mkdir(parents=True, exist_ok=True)
    generated.to_midi(str(destination))
    if not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError("MIDI-GPT completed without producing a MIDI file")
    return {"backend": "midi_gpt", "midi": str(destination),
            "tracks": selected_tracks, "bars": selected_bars,
            "elapsed_seconds": round(time.monotonic() - started, 2)}
