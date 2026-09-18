"""Observe-plan-act-verify loop used by the REAPER music agent."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from music21 import converter

from text2music.agent.audio_tools import extract_audio_paths, save_analysis
from text2music.agent.capabilities import (
    append_trace, compare_versions, load_memory, memory_context,
    summarize_selected_midi, validate_midi,
)
from text2music.agent.service import (
    PROJECT_ROOT, RUNS_DIR, MusicBrief, build_plan, plan_with_qwen, run_generation,
)

STATUS = RUNS_DIR / "reaper-status.txt"
HISTORY = RUNS_DIR / "reaper-history.jsonl"
MEMORY = RUNS_DIR / "agent-memory.json"


def status(stage: str, **fields):
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(
        "\n".join([f"STATE: {stage}"] + [f"{key.upper()}: {value}" for key, value in fields.items()]) + "\n",
        encoding="utf-8",
    )


def clean_abci(source: Path, destination: Path):
    data = source.read_text(encoding="utf-8", errors="replace")
    data = re.sub(r"%\d+", "", data)
    data = re.sub(r"(?<!\n)(\[V:\d+\])", r"\n\1", data)
    destination.write_text("\n".join(line.strip() for line in data.splitlines() if line.strip()), encoding="utf-8")


def postprocess(run_dir: Path, files: list[str]) -> tuple[Path, Path, Path]:
    source = next(Path(filename) for filename in files if "interleaved" in filename)
    abc = run_dir / "score.abc"
    xml_dir = run_dir / "xml"
    xml_dir.mkdir()
    clean_abci(source, abc)
    command = PROJECT_ROOT / "text2music/data/utils/abc_helper/abc2xml.py"
    result = subprocess.run([sys.executable, str(command), "-o", str(xml_dir), str(abc)],
                            text=True, capture_output=True)
    xmls = list(xml_dir.glob("*.xml"))
    if result.returncode or not xmls:
        raise RuntimeError("ABC→MusicXML failed: " + result.stderr[-500:])
    xml = xmls[0]
    midi = run_dir / "score.mid"
    converter.parse(str(xml)).write("midi", fp=str(midi))
    if not midi.exists() or midi.stat().st_size < 32:
        raise RuntimeError("MusicXML→MIDI produced no usable MIDI file")
    return abc, xml, midi


def correction_direction(findings: list[str], attempt: int) -> str:
    joined = " ".join(findings).lower()
    actions: list[str] = []
    if "sparse" in joined or "density is low" in joined:
        actions.append("increase rhythmic activity and note density")
    if "density is high" in joined:
        actions.append("reduce ornamental and repeated notes")
    if "length" in joined or "zero duration" in joined:
        actions.append("honor Total Measures exactly and complete every section")
    if "range" in joined:
        actions.append("keep every non-drum voice inside its stated pitch range")
    if "track" in joined or "layered" in joined:
        actions.append("emit distinct active voices for every planned instrument")
    if "drum" in joined:
        actions.append("include a complete drumset part with kick, snare and cymbal pattern")
    if "tempo" in joined or "meter" in joined:
        actions.append("write the planned tempo and time signature into the score")
    if "velocity" in joined:
        actions.append("use assertive playable dynamics")
    actions.append("simplify the arrangement while preserving the user's melody and stated genre"
                   if attempt > 1 else "keep the musical idea coherent and playable")
    return "; ".join(actions)


def run_agent(request: str, source_midi: str | None = None) -> dict:
    memory = load_memory(MEMORY)
    revision = summarize_selected_midi(Path(source_midi)) if source_midi else ""
    remembered = memory_context(memory)
    audio_analysis = None
    audio_context = ""
    audio_paths = extract_audio_paths(request)
    if audio_paths:
        status("analyzing_audio", progress=0,
               detail=f"Analyzing tempo, key, onsets and sections: {audio_paths[0].name}")
        analysis_dir = RUNS_DIR / "audio_analysis"
        analysis_dir.mkdir(parents=True, exist_ok=True)
        audio_analysis = save_analysis(audio_paths[0], analysis_dir / f"{audio_paths[0].stem}.json")
        audio_context = (
            f"Audio analysis: {audio_analysis['tempo_bpm']} BPM, {audio_analysis['key']}, "
            f"{audio_analysis['onset_count']} onsets, sections at "
            f"{audio_analysis['section_boundaries_seconds']} seconds."
        )
    tempo_match = re.search(r"Tempo:\s*(\d+)\s*BPM", request, re.IGNORECASE)
    signature_match = re.search(r"Time Signature:\s*(\d+\s*/\s*\d+)", request, re.IGNORECASE)
    brief = MusicBrief(
        description="\n".join(part for part in (
            remembered, audio_context, revision + "\nRevision request:" if revision else "", request
        ) if part),
        tempo=int(tempo_match.group(1)) if tempo_match else 140,
        time_signature=signature_match.group(1).replace(" ", "") if signature_match else "4/4",
    )
    status("planning", progress=8, detail=f"Observing DAW project context ({brief.tempo} BPM, {brief.time_signature}) & structuring arrangement plan", request=request)
    plan = plan_with_qwen(brief)
    current_plan = RUNS_DIR / "current-plan.txt"
    current_plan.write_text(plan, encoding="utf-8")

    def report(stage: str, progress: int, detail: str, run: str, plan_path: str):
        status(stage, progress=progress, detail=detail, run=run, plan=plan_path)

    status("loading_model", progress=15, detail="Checking GPU memory & warming local notation model", plan=str(current_plan))
    attempts = 0
    validation: list[str] = []
    while True:
        run, files, message = run_generation(plan, report)
        if message == "Generation cancelled":
            status("cancelled", progress=0, detail="Generation cancelled; warm GPU model available",
                   run=run, plan=str(current_plan))
            return {"cancelled": True, "run": run, "plan": str(current_plan)}
        if not files:
            raise RuntimeError(message)
        run_dir = Path(run)
        (run_dir / "plan.txt").write_text(plan, encoding="utf-8")
        append_trace(run_dir, "observe", "Read REAPER context, selection, audio and preference memory",
                     source_midi=source_midi or "", memory_used=bool(remembered), audio_analysis=audio_analysis)
        append_trace(run_dir, "plan", "Compiled structured Triceratops arrangement plan",
                     plan=str(run_dir / "plan.txt"))
        status("converting", progress=90, detail="Translating notation (ABC score) into multi-track MIDI clip",
               run=run, plan=str(run_dir / "plan.txt"))
        abc, xml, midi = postprocess(run_dir, files)
        status("verifying", progress=95, detail="Checking musical constraints (pitch ranges, polyphony, rhythm density)",
               run=run, plan=str(run_dir / "plan.txt"))
        validation = validate_midi(midi, plan)
        append_trace(run_dir, "verify", "Validated generated MIDI", findings=validation, midi=str(midi))
        if not validation or attempts >= 2:
            break
        attempts += 1
        correction = correction_direction(validation, attempts)
        append_trace(run_dir, "correct", "Validation requested corrective regeneration", findings=validation)
        status("correcting", progress=50, detail=f"Self-correction pass {attempts}: {correction}",
               run=run, plan=str(run_dir / "plan.txt"))
        plan += (
            f"\nCreative Direction: Correction pass {attempts}: {correction}. "
            f"Evidence: {'; '.join(validation)}.\n"
        )
        current_plan.write_text(plan, encoding="utf-8")
    outcome = "candidate" if not validation else "candidate with warnings: " + "; ".join(validation)
    # Candidate generation is not approval. Preference learning happens only
    # after an explicit accept/reject action in the conversation tool loop.
    append_trace(run_dir, "remember", "Updated persistent musical preferences", outcome=outcome)
    previous = None
    if HISTORY.exists():
        try:
            old = json.loads(HISTORY.read_text(encoding="utf-8").splitlines()[-1])
            previous = Path(old["midi"]) if old.get("midi") else None
        except (IndexError, json.JSONDecodeError):
            pass
    comparison = compare_versions(midi, previous)
    append_trace(run_dir, "compare", "Compared this MIDI version with the previous take", comparison=comparison)
    entry = {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"), "request": request, "run": run,
        "plan": str(run_dir / "plan.txt"), "abc": str(abc), "xml": str(xml), "midi": str(midi),
        "validation": validation, "attempts": attempts, "source_midi": source_midi or "",
        "comparison": comparison,
    }
    with HISTORY.open("a", encoding="utf-8") as output:
        output.write(json.dumps(entry, ensure_ascii=False) + "\n")
    status("completed", progress=100, detail="MIDI imported. " + comparison["summary"], **entry)
    return entry
