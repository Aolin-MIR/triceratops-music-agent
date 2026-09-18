"""Planning and execution tools used by the local Text2Score music agent."""

from __future__ import annotations

import re
import subprocess
import sys
import uuid
import os
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INFERENCE_DIR = PROJECT_ROOT / "text2music" / "inference"
RUNS_DIR = Path(os.environ.get("TEXT2SCORE_RUNS_DIR", PROJECT_ROOT / "text2music" / "artifacts" / "agent_runs"))

KEY_SIGNATURES = {
    "c": 0, "a minor": 0, "g": 1, "e minor": 1, "d": 2, "b minor": 2,
    "a": 3, "f# minor": 3, "e": 4, "c# minor": 4, "b": 5, "g# minor": 5,
    "f#": 6, "d# minor": 6, "f": -1, "d minor": -1, "bb": -2,
    "g minor": -2, "eb": -3, "c minor": -3,
}


@dataclass(frozen=True)
class MusicBrief:
    description: str
    genre: str = "rock"
    tempo: int = 140
    key: str = "E minor"
    time_signature: str = "4/4"
    measures: int = 32
    instruments: str = "Electric Guitar, Electric Bass, Drumset"
    density: str = "Moderate"


QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
QWEN_MODEL = "qwen-plus"
QWEN_SYSTEM_PROMPT = """You are the musical planning component of Text2Score, a sheet-music generation system.
Return one JSON object only, with no Markdown or explanation. Its keys are genre, instruments, measures.
instruments is an array of MuseScore instrument names. measures contains 5 to 10 objects, each with measure
(integer), instruments (array), pitch_min (integer MIDI note), pitch_max (integer MIDI note), density (Low,
Moderate, or High), tempo (integer BPM), time_signature (e.g. 4/4), key_signature (integer accidental count),
chords (an array of sorted unique integer MIDI pitch classes 0-11, or null), and direction (short text).
Respect the requested length, key, tempo and time signature. For rock and metal create a coherent riff, verse,
chorus, bridge and ending plan with explicit guitar, bass and drum roles. Do not describe unnotatable audio effects."""


def _key_signature(key: str) -> int:
    normalized = key.strip().lower().replace(" major", "")
    return KEY_SIGNATURES.get(normalized, KEY_SIGNATURES.get(key.strip().lower(), 0))


def _rock_chords(key_signature: int) -> list[list[int]]:
    # Power-chord-friendly progressions; exact pitch classes are what Text2Score expects.
    if key_signature == 3:  # E major / C# minor
        return [[4, 8, 11], [1, 4, 8], [2, 6, 9], [4, 7, 11]]
    if key_signature == 2:  # D major / B minor
        return [[2, 6, 9], [7, 11, 2], [9, 1, 4], [2, 5, 9]]
    return [[4, 7, 11], [0, 4, 7], [2, 7, 9], [2, 6, 11]]  # E minor default


def build_plan(brief: MusicBrief) -> str:
    """Compile a user brief into the strict measure-wise plan Text2Score consumes."""
    measures = max(8, min(int(brief.measures), 128))
    tempo = max(40, min(int(brief.tempo), 240))
    key_signature = _key_signature(brief.key)
    genre = brief.genre.strip().lower() or "rock"
    instruments = brief.instruments.strip() or "Electric Guitar, Electric Bass, Drumset"
    chords = _rock_chords(key_signature) if "rock" in genre or "metal" in genre else [[0, 4, 7], [5, 9, 0], [7, 11, 2], [0, 4, 7]]
    marks = sorted({1, max(2, measures // 4), max(3, measures // 2), max(4, measures * 3 // 4), measures})
    sections = [
        ("introductory riff; leave space for the groove", "Low", 38, 72),
        ("verse; lock guitar, bass, and drums into a clear pulse", brief.density, 36, 82),
        ("chorus; broaden the register and reinforce the hook", "High", 32, 90),
        ("bridge; briefly reduce density before returning", "Moderate", 34, 86),
        ("final cadence; resolve decisively", "Moderate", 32, 88),
    ]
    lines = [
        f"Total Measures: {measures}",
        f"Genre: {genre}",
        f"Instruments: {instruments}",
        f"Creative Direction: {brief.description.strip()}",
    ]
    for index, measure in enumerate(marks):
        direction, density, low, high = sections[index]
        chord = chords[index % len(chords)]
        lines.extend([
            "", f"Measure: {measure}", f"Instruments: {instruments}",
            f"Pitch Range: {low}–{high}", f"Note Density: {density}",
            f"Tempo: {tempo} BPM", f"Time Signature: {brief.time_signature}",
            f"Key Signature: {key_signature}", f"Chords: {chord}",
            f"Direction: {direction}",
        ])
    return "\n".join(lines) + "\n"


def _compile_qwen_plan(payload: dict, brief: MusicBrief) -> str:
    """Convert Qwen's JSON into the exact textual grammar consumed by Text2Score."""
    instruments = payload.get("instruments") or [item.strip() for item in brief.instruments.split(",")]
    if not isinstance(instruments, list) or not all(isinstance(item, str) and item.strip() for item in instruments):
        raise ValueError("instruments must be a non-empty array of names")
    instrument_text = ", ".join(item.strip() for item in instruments)
    raw_measures = payload.get("measures")
    if not isinstance(raw_measures, list) or len(raw_measures) < 5:
        raise ValueError("measures must contain at least 5 sections")
    # Qwen may describe every bar. Text2Score benefits more from a compact set of
    # structural change points, so retain at most ten evenly-spaced sections.
    if len(raw_measures) > 10:
        selected = [round(index * (len(raw_measures) - 1) / 9) for index in range(10)]
        raw_measures = [raw_measures[index] for index in selected]
    total = max(8, min(int(brief.measures), 128))
    lines = [f"Total Measures: {total}", f"Genre: {str(payload.get('genre') or brief.genre).lower()}",
             f"Instruments: {instrument_text}", f"Creative Direction: {brief.description.strip()}"]
    previous_measure = 0
    for section in raw_measures:
        if not isinstance(section, dict):
            raise ValueError("each measure section must be an object")
        measure = int(section["measure"])
        if not previous_measure < measure <= total:
            raise ValueError("measure numbers must be increasing and within Total Measures")
        previous_measure = measure
        density = str(section.get("density", brief.density)).title()
        if density not in {"Low", "Moderate", "High"}:
            density = brief.density
        tempo = max(40, min(int(section.get("tempo", brief.tempo)), 240))
        pitch_min, pitch_max = int(section["pitch_min"]), int(section["pitch_max"])
        if not 0 <= pitch_min < pitch_max <= 127:
            raise ValueError("pitch range must be ordered MIDI values between 0 and 127")
        key_signature = max(-7, min(int(section.get("key_signature", _key_signature(brief.key))), 7))
        chords = section.get("chords")
        if chords is None:
            chord_text = "None"
        elif isinstance(chords, list) and chords and all(isinstance(note, int) and 0 <= note <= 11 for note in chords):
            chord_text = str(sorted(set(chords)))
        else:
            raise ValueError("chords must be null or MIDI pitch classes from 0 to 11")
        section_instruments = section.get("instruments") or instruments
        if not isinstance(section_instruments, list) or not all(isinstance(item, str) for item in section_instruments):
            raise ValueError("section instruments must be an array of names")
        lines.extend(["", f"Measure: {measure}", f"Instruments: {', '.join(section_instruments)}",
                      f"Pitch Range: {pitch_min}–{pitch_max}", f"Note Density: {density}",
                      f"Tempo: {tempo} BPM", f"Time Signature: {section.get('time_signature', brief.time_signature)}",
                      f"Key Signature: {key_signature}", f"Chords: {chord_text}",
                      f"Direction: {str(section.get('direction', '')).strip()}"])
    return "\n".join(lines) + "\n"


def plan_with_qwen(brief: MusicBrief, *, api_key: str | None = None,
                   model: str | None = None) -> str:
    """Ask Qwen for a richer plan, while keeping credentials out of project files."""
    key = api_key or os.environ.get("QWEN_API_KEY")
    if not key:
        raise RuntimeError("QWEN_API_KEY is not set. Set it in your shell before using Qwen planning.")
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - deployment dependency
        raise RuntimeError("The openai package is required for Qwen planning.") from exc

    payload = {
        "description": brief.description,
        "genre": brief.genre,
        "tempo_bpm": brief.tempo,
        "key": brief.key,
        "time_signature": brief.time_signature,
        "measures": brief.measures,
        "instruments": brief.instruments,
        "note_density": brief.density,
    }
    client = OpenAI(api_key=key, base_url=os.environ.get("QWEN_BASE_URL", QWEN_BASE_URL),
                    timeout=60.0, max_retries=2)
    try:
        response = client.chat.completions.create(
            model=model or os.environ.get("QWEN_MODEL", QWEN_MODEL),
            messages=[
                {"role": "system", "content": QWEN_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.35,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        raise RuntimeError(f"Qwen planning request failed: {type(exc).__name__}: {exc}") from exc
    content = (response.choices[0].message.content or "").strip()
    try:
        plan = _compile_qwen_plan(json.loads(content), brief)
    except (json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
        raise RuntimeError(f"Qwen returned an unusable structured plan: {exc}") from exc
    findings = validate_plan(plan)
    if findings:
        raise RuntimeError("Qwen returned an invalid plan: " + "; ".join(findings))
    return plan + "\n"


def validate_plan(plan: str) -> list[str]:
    """Return human-readable validation findings before expensive inference begins."""
    findings: list[str] = []
    required = ("Total Measures:", "Instruments:", "Measure:", "Tempo:", "Time Signature:", "Key Signature:", "Chords:")
    for marker in required:
        if marker not in plan:
            findings.append(f"Missing required field: {marker.rstrip(':')}")
    for tempo in re.findall(r"Tempo:\s*(\d+)\s*BPM", plan):
        if not 40 <= int(tempo) <= 240:
            findings.append(f"Tempo {tempo} BPM is outside the supported 40–240 BPM guardrail.")
    if not re.search(r"Time Signature:\s*\d+/\d+", plan):
        findings.append("Time Signature must look like 4/4 or 6/8.")
    return findings


def run_generation(plan: str, progress_callback: Callable[[str, int, str, str, str], None] | None = None) -> tuple[str, list[str], str]:
    """Run Text2Score in an isolated directory and return logs plus produced files."""
    findings = validate_plan(plan)
    if findings:
        return "", [], "Plan validation failed:\n- " + "\n- ".join(findings)
    run_dir = RUNS_DIR / uuid.uuid4().hex
    run_dir.mkdir(parents=True, exist_ok=False)
    plan_path = run_dir / "plan.txt"
    plan_path.write_text(plan, encoding="utf-8")
    output_dir = run_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    def report(stage: str, percent: int, detail: str) -> None:
        if progress_callback:
            progress_callback(stage, percent, detail, str(run_dir), str(plan_path))

    worker_queue = RUNS_DIR / "worker_queue"
    worker_queue.mkdir(parents=True, exist_ok=True)
    req_id = f"req-{uuid.uuid4().hex[:8]}"

    wsl_output = f"/mnt/e/text2score/text2music/artifacts/agent_runs/{run_dir.name}/output" if os.name == "nt" else str(output_dir)
    wsl_cancel = f"/mnt/e/text2score/text2music/artifacts/agent_runs/{run_dir.name}/cancel" if os.name == "nt" else str(run_dir / "cancel")

    req_file = worker_queue / f"{req_id}.request.json"
    resp_file = worker_queue / f"{req_id}.response.json"
    prog_file = worker_queue / f"{req_id}.progress.json"

    request_data = {
        "id": req_id,
        "plan": plan,
        "output_folder": wsl_output,
        "cancel_path": wsl_cancel,
    }

    report("loading_model", 18, "Submitting score plan to local GPU worker...")
    # Clean up any stale response/progress from previous runs
    resp_file.unlink(missing_ok=True)
    prog_file.unlink(missing_ok=True)
    req_file.write_text(json.dumps(request_data, ensure_ascii=False), encoding="utf-8")

    started = time.monotonic()
    last_heartbeat = -1
    worker_restarted = False
    while True:
        if resp_file.exists():
            try:
                resp = json.loads(resp_file.read_text(encoding="utf-8"))
                resp_file.unlink(missing_ok=True)
                prog_file.unlink(missing_ok=True)
                if not resp.get("ok"):
                    return str(run_dir), [], f"Worker error: {resp.get('error')}"
                files = [str(path) for path in sorted(output_dir.rglob("*.abc"))] if output_dir.exists() else []
                report("verifying", 88, "Checking generated notation")
                return str(run_dir), files, "Generation completed successfully on GPU worker."
            except Exception:
                pass

        cancel_file = run_dir / "cancel"
        if cancel_file.exists():
            req_file.unlink(missing_ok=True)
            return str(run_dir), [], "Generation cancelled"

        elapsed = int(time.monotonic() - started)
        if prog_file.exists():
            try:
                prog = json.loads(prog_file.read_text(encoding="utf-8"))
                phase = prog.get("phase", "")
                if phase == "sampling":
                    current_step = int(prog.get("step", 0))
                    total_steps = int(prog.get("total_steps", 0))
                    if total_steps > 0:
                        pct = min(88, 30 + int(current_step * 58 / total_steps))
                        detail_msg = f"Sampling score tokens with warm GPU model ({current_step}/{total_steps} tokens, {elapsed}s)"
                    else:
                        pct = min(88, 30 + elapsed // 2)
                        detail_msg = f"Sampling score tokens with warm GPU model... ({elapsed}s elapsed)"
                    report("sampling", pct, detail_msg)
            except Exception:
                pass
        elif elapsed != last_heartbeat:
            last_heartbeat = elapsed
            report("loading_model", min(30, 15 + elapsed // 4), f"Waiting for GPU model worker... ({elapsed}s)")
            # Self-heal: if the worker died or was stopped, relaunch it once
            # instead of waiting out the full queue timeout.
            if not worker_restarted and elapsed >= 30 and os.name != "nt":
                try:
                    worker_text = (worker_queue / "worker-state.txt").read_text(
                        encoding="utf-8", errors="replace")
                except OSError:
                    worker_text = ""
                worker_state = ""
                for line in worker_text.splitlines():
                    if line.startswith("STATE: "):
                        worker_state = line.partition(": ")[2].strip()
                        break
                if worker_state in {"error", "stopped", ""}:
                    script = Path(__file__).resolve().parent / "launch_reaper_worker.sh"
                    if script.exists():
                        try:
                            subprocess.Popen(["bash", str(script)], start_new_session=True,
                                             stdout=subprocess.DEVNULL,
                                             stderr=subprocess.DEVNULL)
                            worker_restarted = True
                            report("loading_model", 20, "GPU worker was not running; restarting it...")
                        except OSError:
                            pass

        if time.monotonic() - started > 600:
            req_file.unlink(missing_ok=True)
            break
        time.sleep(0.3)

    # Fallback to direct process if warm worker queue did not respond
    log_path = run_dir / "generation.log"
    report("loading_model", 18, "Starting isolated score model process")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    if os.name == "nt":
        wsl_plan = f"/mnt/e/text2score/text2music/artifacts/agent_runs/{run_dir.name}/plan.txt"
        command = ["wsl.exe", "-e", "bash", "-c",
                   f"export TMP=/tmp TEMP=/tmp TMPDIR=/tmp && cd /mnt/e/text2score/text2music/inference && /usr/bin/python3 inference.py --plan_path '{wsl_plan}' --output_folder '{wsl_output}'"]
    else:
        command = [sys.executable, "inference.py", "--plan_path", str(plan_path), "--output_folder", str(output_dir)]

    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=INFERENCE_DIR, text=True, stdout=log, stderr=subprocess.STDOUT, env=env)
        previous = ""
        started = time.monotonic()
        heartbeat = -1
        while process.poll() is None:
            time.sleep(0.5)
            try:
                text = log_path.read_text(encoding="utf-8", errors="replace")[-16000:]
            except OSError:
                continue
            if text != previous:
                previous = text
                if "T2S_STATUS: generating notation" in text:
                    bars = re.findall(r"\[r:(\d+)/(\d+)\]", text)
                    if bars:
                        remaining, denominator = map(int, bars[-1])
                        total = max(int(left) + int(right) for left, right in bars)
                        written = max(0, total - remaining)
                        percent = min(85, 65 + int(20 * written / max(total, 1)))
                        report("generating", percent, f"Composing notation: bar {written + 1} of about {total}")
                    else:
                        report("generating", 65, "Composing notation on the GPU")
                elif "T2S_STATUS: loading checkpoint" in text:
                    report("loading_model", 42, "Loading trained musical knowledge")
                elif "T2S_STATUS: preparing model" in text:
                    report("loading_model", 28, "Preparing the score model")
                continue
            elapsed = int(time.monotonic() - started)
            if elapsed != heartbeat:
                heartbeat = elapsed
                pulse = min(38, 18 + elapsed // 3)
                report("loading_model", pulse, f"Loading score model ({elapsed}s elapsed)")
        returncode = process.returncode
    logs = log_path.read_text(encoding="utf-8", errors="replace").strip()
    files = [str(path) for path in sorted(output_dir.rglob("*.abc"))] if output_dir.exists() else []
    if returncode:
        return str(run_dir), files, f"Generation failed (exit {returncode}).\n{logs[-4000:]}"
    report("verifying", 88, "Checking generated notation")
    return str(run_dir), files, logs[-4000:] or "Generation completed."
