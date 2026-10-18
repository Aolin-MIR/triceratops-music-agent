# Triceratops Music Agent

[中文](readme.md) | [English](README.en.md)

**Keep the next few bars inside your REAPER project.**

Triceratops is a music Agent VST3 for REAPER. Describe an idea in everyday language or use the plug-in's action buttons to generate, continue, edit and analyze MIDI, then import the result into REAPER tracks.

It understands broad descriptions of style, mood and imagery as well as specific musical requests. The Agent preserves your intent and passes it to a music model for MIDI generation. You can chat with it, ask what the plug-in can do, or start directly from an action button.

[![Triceratops feature overview](docs/images/triceratops-0.9-overview.webp)](https://github.com/Aolin-MIR/triceratops-music-agent/releases/download/v0.9.0/Triceratops-0.9.0-Feature-Overview.png)

## What it can do

| Feature | Use |
| --- | --- |
| Chat and new music | Describe style, mood, instruments, rhythm and structure in Chinese or English to generate text-conditioned multitrack MIDI |
| MIDI editing | Transpose, adjust velocity, tighten timing and more while keeping notes editable |
| Continuation and infill | Continue existing MIDI or generate content for selected bars |
| Analysis | Inspect MIDI notes and rhythm; analyze audio tempo, key, onsets and sections |
| Stem separation | Separate vocals, drums, bass and other |
| Audio to MIDI | Extract notes from audio and create MIDI |
| Recording and import | Record MIDI / audio routed into the plug-in and import MIDI or separated audio to new REAPER tracks |
| Feedback and memory | Keep project preferences and conversation summaries, retrieve project notes and local knowledge, and keep, reject or undo generated results |

For example: “Sparse piano and cello for an overcast evening”; “Continue this clip for four bars”; “Tighten the rhythm while keeping the melody.” No JSON or fixed prompt template is needed. Use the **Features** button to browse available actions.

## New in 1.0

Version 1.0 brings chat, model and device settings into the plug-in. On Windows, the chat model can run locally on the GPU without WSL, or you can choose a compatible cloud tool-calling API. Explicit actions such as analysis, separation, transcription and continuation run directly from their buttons without a chat API.

Model downloads select an official source or a China mirror based on network egress, and you can choose a source manually. Chat and music models have separate compute-device settings, with resource recommendations based on each model.

## Download and install

The current public downloads are **v0.9.0**. The release includes the Windows installer, a macOS Apple Silicon archive and release notes.

- [Windows x64 installer (EXE)](https://github.com/Aolin-MIR/triceratops-music-agent/releases/download/v0.9.0/Triceratops-0.9.0-Windows-x64-Setup.exe)
- [macOS Apple Silicon download (ZIP)](https://github.com/Aolin-MIR/triceratops-music-agent/releases/download/v0.9.0/Triceratops-0.9.0-macOS-AppleSilicon.zip)
- [v0.9.0 release notes and assets](https://github.com/Aolin-MIR/triceratops-music-agent/releases/tag/v0.9.0)

Windows: Run the EXE and follow the setup utility to choose the REAPER path, model directory and compute device. Then rescan VST plug-ins in REAPER and insert Triceratops. The installer supplies a dedicated Python environment; model weights are downloaded by setup.

macOS: Requires Apple Silicon, macOS 14 or later, and native ARM64 Python 3.10 or 3.11. Extract the archive, keep its folder, and run `bash setup-macos.sh` in Terminal.

REAPER is the only supported host. Windows uses a native backend and does not require WSL. Use **中文 / English** at the top of the plug-in to switch the interface language; buttons, status and operation results are bilingual.

## How it runs

- **Cloud chat**: Enter a compatible tool-calling API endpoint, model and key in the plug-in for conversation, intent refinement and open-ended music prompts.
- **Windows local chat**: Download and run a local model from plug-in Settings. Inference uses the llama.cpp GPU backend; no cloud key is needed.
- **Direct actions**: Analysis, MIDI editing, continuation, separation and transcription buttons call local tools without a chat API.

Local chat, MIDI-LLM, MIDI-GPT and HTDemucs have separate compute-device settings. Plug-in Settings provides resource detection and device recommendations, so models do not need to be unloaded or moved between tasks.

## System requirements

| Platform | Requirements |
| --- | --- |
| Windows | Windows 10 / 11 x64 and REAPER x64. The installer provides a dedicated Python environment. Local GPU chat requires a compatible NVIDIA GPU; music features can use CPU or GPU according to model settings. |
| macOS | Apple Silicon, macOS 14 or later, native Apple Silicon REAPER, and ARM64 Python 3.10 / 3.11. |

An internet connection is needed for initial runtime and model downloads. See [System requirements](docs/SYSTEM_REQUIREMENTS.md) for platform and resource details.

## Models in use

| Model | Function | License |
| --- | --- | --- |
| [MIDI-LLM](https://huggingface.co/slseanwu/MIDI-LLM_Llama-3.2-1B) | Text-to-multitrack MIDI | Llama 3.2 Community License |
| [MIDI-GPT Yellow Medium](https://huggingface.co/Metacreation/MIDI-GPT) | MIDI continuation and infill | CC BY-NC 4.0, noncommercial use |
| [HTDemucs](https://huggingface.co/adefossez/HTDemucs) | Four-stem audio separation | See model and upstream licenses |
| [Basic Pitch](https://github.com/spotify/basic-pitch) | Audio-to-MIDI transcription | Apache 2.0 |

Model revisions and third-party licenses are listed in [`download_models.py`](text2music/agent/download_models.py) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Data and credits

Models and generated results are stored locally. When cloud chat is enabled, conversation and the project context needed for the task are sent to the API provider you configure. API keys are stored in your local user configuration.

With thanks to [MIDI-LLM](https://github.com/slSeanWU/MIDI-LLM), [MIDI-GPT](https://github.com/Metacreation/MIDI-GPT), [Demucs](https://github.com/facebookresearch/demucs), [Basic Pitch](https://github.com/spotify/basic-pitch), [Anticipation](https://github.com/jthickstun/anticipation), [JUCE](https://github.com/juce-framework/JUCE) and [librosa](https://github.com/librosa/librosa). This repository originated from [Text2Score](https://github.com/keshavbhandari/text2score). Full attribution and licenses are in [NOTICE](NOTICE).

For feedback or issues, visit [GitHub Issues](https://github.com/Aolin-MIR/triceratops-music-agent/issues).
