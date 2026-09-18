"""Audio understanding and optional stem/transcription tools."""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np


MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
PITCH_NAMES = ("C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")
AUDIO_EXTENSIONS = {".wav", ".flac", ".mp3", ".ogg", ".m4a", ".aiff", ".aif"}


def windows_to_wsl(path: str) -> Path:
    match = re.match(r"^([A-Za-z]):[\\/](.*)$", path)
    if match:
        return Path("/mnt") / match.group(1).lower() / match.group(2).replace("\\", "/")
    return Path(path)


def extract_audio_paths(context: str) -> list[Path]:
    candidates = re.findall(r"(?:[A-Za-z]:\\[^\r\n,]+|/[^,\r\n]+)", context)
    result: list[Path] = []
    for candidate in candidates:
        path = windows_to_wsl(candidate.strip())
        if path.suffix.lower() in AUDIO_EXTENSIONS and path.exists() and path not in result:
            result.append(path)
    return result


def analyze_audio(path: Path, *, max_seconds: float = 900) -> dict[str, Any]:
    import librosa
    y, sample_rate = librosa.load(path, sr=22050, mono=True, duration=max_seconds)
    if not len(y):
        raise ValueError("Audio file is empty")
    if float(np.max(np.abs(y))) < 1e-6:
        raise ValueError("Audio file is silent")
    onset_envelope = librosa.onset.onset_strength(y=y, sr=sample_rate)
    tempo, beat_frames = librosa.beat.beat_track(onset_envelope=onset_envelope, sr=sample_rate)
    tempo_value = float(np.asarray(tempo).reshape(-1)[0])
    onset_frames = librosa.onset.onset_detect(onset_envelope=onset_envelope, sr=sample_rate)
    onset_times = librosa.frames_to_time(onset_frames, sr=sample_rate)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sample_rate)
    chroma_mean = chroma.mean(axis=1)
    scores: list[tuple[float, str]] = []
    for root in range(12):
        scores.append((float(np.nan_to_num(np.corrcoef(chroma_mean, np.roll(MAJOR_PROFILE, root))[0, 1])),
                       f"{PITCH_NAMES[root]} major"))
        scores.append((float(np.nan_to_num(np.corrcoef(chroma_mean, np.roll(MINOR_PROFILE, root))[0, 1])),
                       f"{PITCH_NAMES[root]} minor"))
    key = max(scores, key=lambda item: item[0])[1]
    duration = float(librosa.get_duration(y=y, sr=sample_rate))
    segment_count = max(1, min(12, round(duration / 20)))
    boundaries = librosa.segment.agglomerative(chroma, k=segment_count) if chroma.shape[1] >= segment_count else np.array([0])
    section_times = librosa.frames_to_time(boundaries, sr=sample_rate).round(2).tolist()
    rms = librosa.feature.rms(y=y)[0]
    result = {
        "path": str(path), "duration_seconds": round(duration, 2), "tempo_bpm": round(tempo_value, 2),
        "key": key, "beat_count": int(len(beat_frames)), "onset_count": int(len(onset_times)),
        "onset_times": np.round(onset_times[:128], 3).tolist(), "section_boundaries_seconds": section_times,
        "rms_mean": round(float(rms.mean()), 5), "rms_peak": round(float(rms.max()), 5),
    }
    return result


def separate_stems(path: Path, output_dir: Path) -> list[Path]:
    if importlib.util.find_spec("demucs") is None:
        raise RuntimeError("Demucs is not installed")
    output_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-m", "demucs.separate", "-o", str(output_dir), str(path)], check=True)
    files = sorted((output_dir / "htdemucs" / path.stem).glob("*.wav"))
    if not files:
        raise RuntimeError("Stem separation returned no audio files")
    return files


def audio_to_midi(path: Path, output_dir: Path) -> list[Path]:
    if importlib.util.find_spec("basic_pitch") is None:
        raise RuntimeError("Basic Pitch is not installed")
    output_dir.mkdir(parents=True, exist_ok=True)
    from basic_pitch.inference import predict
    _, midi, _ = predict(str(path))
    destination = output_dir / f"{path.stem}_basic_pitch.mid"
    midi.write(str(destination))
    return [destination]


def save_analysis(path: Path, destination: Path) -> dict[str, Any]:
    result = analyze_audio(path)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
