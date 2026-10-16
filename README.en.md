# Triceratops Music Agent · 0.9

[中文](readme.md) | [English](README.en.md)

**Keep the next few bars inside your REAPER project.**

Triceratops is a music Agent VST3 for REAPER. Describe an idea naturally or use the action buttons to generate, continue, edit and analyze MIDI, then import editable results into real REAPER tracks.

**v0.9 supports REAPER only. Windows uses a native Python backend; WSL is not required.** Chat and intent rewriting use your configured Qwen / OpenAI-compatible API. Music generation, continuation, stem separation and transcription run locally.

## Download and install

- [Windows x64 EXE installer](https://github.com/Aolin-MIR/triceratops-music-agent/releases/download/v0.9.0/Triceratops-0.9.0-Windows-x64-Setup.exe)
- [Release notes, checksums and available assets](https://github.com/Aolin-MIR/triceratops-music-agent/releases/tag/v0.9.0)
- macOS: native build and setup scripts are provided as **experimental support**. Download a Mac package only if it appears in the release assets. REAPER on actual Mac hardware has not been verified.

1. Save your project and close REAPER. Run the EXE. The single VST3 installation is `C:\Program Files\Common Files\VST3\Triceratops.vst3`.
2. Open **Configure runtime and download models** at the end of installation or from the Start menu. Select REAPER, a model directory and compute device; enter your own API key. A dedicated native Python seed is included, without modifying system Python.
3. First setup downloads runtime packages and models. It defaults to the Tsinghua PyPI mirror and `hf-mirror.com`. Failed downloads report an error; rerun setup to resume. Missing models never silently select a different generator.
4. In REAPER, open **Preferences → Plug-ins → VST → Re-scan**, then insert **Triceratops**.
5. Rerun configuration to change settings or download missing files. Uninstalling the application retains user models, credentials and generated work for backup or manual removal.

The EXE includes the plug-in, configuration utility and Python seed. **Large weights are downloaded by setup, not embedded in the EXE.** Allow approximately 15 GB of free disk space; model weights total about 4 GB. CPU is the default. At least 16 GB RAM is recommended, with 32 GB preferred for comfortable generation. CUDA requires an NVIDIA GPU, a compatible driver and CUDA-enabled Torch. Setup checks the selected device and reports failure rather than switching devices silently.

Use **中文 / English** in the plug-in header to switch buttons, status text, hints and operation reports. The language preference is remembered; chat defaults to the selected interface language.

## Features

| Action | Implementation |
| --- | --- |
| Chat / New score | Native LLM tool-calling loop, intent rewriting and local MIDI-LLM generation |
| Edit MIDI / More energy / Tighten timing | Explicit transposition, velocity and timing edits |
| Continue 4 bars / bar infill | MIDI-GPT generates new content; continuation appends bars while retaining original MIDI events |
| Analyze | MIDI note and rhythm statistics; estimated audio tempo/key, onsets and sections |
| Stem split | Demucs HTDemucs: vocals, drums, bass and other |
| Audio → MIDI | Basic Pitch ONNX transcription |
| Rec MIDI / Rec audio | Capture signals routed into the plug-in |
| Auto-Import / Import to REAPER | Add generated MIDI or separated audio to new REAPER tracks; automatic import can be disabled |
| Keep / Reject / Undo | Store preference feedback and restore the previous MIDI version; this does not delete previously imported host tracks |
| Memory / RAG | Persist project constraints, preferences and conversation summaries; retrieve local knowledge and project notes |

Examples: “Sparse piano and cello for an overcast evening”, “Continue this clip for four bars”, or “Tighten the rhythm while keeping the melody.” No JSON or rigid prompt template is required. Editing operations are limited to the transformations exposed by the tools.

MIDI needs an instrument in REAPER to produce sound. Transcription and separation can contain model errors; reported audio key is an estimate.

## Models and licenses

| Model | Purpose / download | License |
| --- | --- | --- |
| [MIDI-LLM](https://huggingface.co/slseanwu/MIDI-LLM_Llama-3.2-1B) | Text-to-MIDI, approximately 3.45 GB, pinned revision | Llama 3.2 Community License; Built with Llama |
| [MIDI-GPT Yellow Medium](https://huggingface.co/Metacreation/MIDI-GPT) | Continuation / infill, approximately 351 MB, pinned revision | Weights: CC BY-NC 4.0, noncommercial use |
| [HTDemucs](https://huggingface.co/adefossez/HTDemucs) | Four-stem separation | See model card and Demucs upstream license |
| [Basic Pitch](https://github.com/spotify/basic-pitch) | ONNX weights installed with the package | Apache 2.0 |

The downloader checks SHA-256 for MIDI-LLM and MIDI-GPT. Exact repositories, revisions and hashes are in [`download_models.py`](text2music/agent/download_models.py). Source availability does not give every model the same license. In particular, MIDI-GPT weights have a noncommercial restriction. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Configuration and privacy

Windows settings: `%APPDATA%\Triceratops\runtime.json`; dedicated Python and weights: `%LOCALAPPDATA%\Triceratops\`; generated work and memory: `%APPDATA%\Triceratops\runs\`. Keys stay in the user-owned configuration and are excluded from packages and repository commits. Chat API calls send conversation and necessary project/analysis context to your chosen provider, which may charge for usage. The backend listens only on `127.0.0.1:49327`.

## Development and verification

```bash
git clone --recurse-submodules https://github.com/Aolin-MIR/triceratops-music-agent.git
cd triceratops-music-agent
```

Windows VST3 builds require Visual Studio 2022 and CMake 3.22+. In Developer PowerShell:

```powershell
cmake -S vst3 -B vst3/build-msvc -G "Visual Studio 17 2022" -A x64
cmake --build vst3/build-msvc --config Release --target Triceratops_VST3
```

Backend dependencies: [`requirements-runtime.txt`](vst3/installer/requirements-runtime.txt). Run tests with `python -m pytest -q`. See the [installer build instructions](vst3/installer/README.txt). Upstream training directories are retained for research and are excluded from the desktop distribution.

Real REAPER verification covers audio analysis, four stems, Basic Pitch, track import, MIDI/audio capture, timing edits, MIDI-GPT continuation and project reopening. Release notes distinguish native Windows validation from earlier WSL validation; historical validator results are not presented as certification of this release.

## Testing feedback

Open an [issue](https://github.com/Aolin-MIR/triceratops-music-agent/issues) with OS, REAPER version, CPU/GPU, reproduction steps, expected behavior and actual behavior. Exclude API keys and private recordings. A short shareable MIDI/audio fixture is helpful.

## Credits

This project originated from [Keshav Bhandari/Text2Score](https://github.com/keshavbhandari/text2score). Triceratops Agent, REAPER integration and desktop distribution work are maintained here. Upstream research material and third-party components retain their authors' rights; see [NOTICE](NOTICE).
