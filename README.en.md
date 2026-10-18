<p align="center"><img src="docs/images/triceratops-mark.svg" width="88" alt="Triceratops mark"></p>

<h1 align="center">Triceratops Music Agent</h1>
<p align="center">🦕 Music tools for Windows / macOS · REAPER / Logic Pro</p>

[中文](readme.md) · [English](README.en.md) · [Downloads](https://github.com/Aolin-MIR/triceratops-music-agent/releases/latest)

<p align="center"><img src="docs/images/windows.png" height="24" alt="Windows"> Windows &nbsp; <img src="docs/images/apple.png" height="24" alt="macOS"> macOS &nbsp; <img src="docs/images/reaper.png" height="24" alt="REAPER"> REAPER &nbsp; <img src="docs/images/logic-pro.png" height="24" alt="Logic Pro"> Logic Pro</p>

## 🎹 Platforms

| System | Host | Format |
| --- | --- | --- |
| Windows 10 / 11 x64 | REAPER x64 | VST3 |
| macOS 14+ · Apple Silicon | REAPER | VST3 |
| macOS 14+ · Apple Silicon | Logic Pro | MIDI FX AU + Audio FX AU |

Describe style, mood, instruments and structure in Chinese or English without JSON or a fixed prompt format.

The Mac installer downloads native ARM64 Python and the local-chat runtime when needed. Intel / Rosetta model backends are unsupported. Audio devices are selected in the host.

## ✨ From 1.0 to 1.0.1

- **Logic Pro support:** separate MIDI and Audio AUs, MIDI capture/output and audio recording.
- **Local or cloud conversation:** native tool calling and compatibility checks; custom configuration remains available.
- **Improved intent handling:** creation, edits, analysis and conversation use the appropriate route; results reflect actual tools.
- **Direct actions:** continue four bars, increase energy, tighten rhythm, separate stems and transcribe without a chat round trip.
- **Hardware-aware deployment:** inspect memory and devices, configure each function separately, verify before applying.
- **Complete note overview:** fit both timeline and pitch range.
- **Workflow fixes:** isolated import requests, duplicate-click protection, version rollback, service reconnection and cancellation.


<details>
<summary>View plug-in screenshots</summary>

![Triceratops MIDI in Logic Pro](docs/images/triceratops-1.0.1-logic.png)

![Functions, sizes and deployment settings](docs/images/triceratops-1.0.1-settings.png)

</details>

## 🎼 Features

Text-to-MIDI composition; continuation and infill; quantization, velocity and transposition; four audio stems; monophonic transcription; audio analysis; MIDI/audio recording; feedback and local knowledge retrieval. REAPER supports manual/automatic import; Logic supports file import, MIDI output and recording.

Generated music and transcription may contain errors. Successful file generation does not certify musical quality. Full project isolation for conversation and memory remains unverified; explicitly load the material to edit. Automated acceptance of Logic cross-window drag remains incomplete; file import and recording are available.

## ⚙️ Install and configure

Choose an actual platform attachment from [Releases](https://github.com/Aolin-MIR/triceratops-music-agent/releases). On Mac, extract and double-click `Install Triceratops.command`. Download sources are selected automatically, with verified alternatives on failure. The installer downloads and verifies Python and the local-chat runtime; use plug-in Settings to download and verify dependencies and model weights. Large runtimes and weights stay outside the small installer ZIP. Public-file proxies must match the pinned official SHA-256. Music weights support Hugging Face and HF-Mirror; local chat weights use the official registry. Windows uses its native installer without WSL.

| Function | Default weights | Recommended deployment |
| --- | --- | --- |
| Text composition | ~3.2 GiB | Hardware checked; CPU by default on Mac, GPU verified separately |
| Continuation / infill | ~334 MiB | Start with CPU; verify GPU separately |
| Four audio stems | ~80 MiB | Start with CPU; verify GPU separately |
| Audio-to-MIDI | ~225 KiB | CPU |
| Local conversation | Default 4B / 4-bit | Sufficient memory and GPU; tool calling and residency must pass |

Weight sizes are not working-memory requirements. Local chat uses native deployment with a compatible NVIDIA GPU on Windows and native Metal deployment on Apple Silicon. A complete local 4B host workflow on an 8 GB Mac is not certified; compatible cloud chat is available. Advanced settings retain custom model IDs, endpoints, precision and devices.

## 🌐 Music-model download routing

<img src="docs/images/huggingface.png" height="28" alt="Hugging Face"> **Hugging Face** · <img src="docs/images/hf-mirror.ico" height="24" alt="HF-Mirror"> **HF-Mirror**

Routes by network egress, with manual selection available. Mainland China checks the mirror first; an unavailable mirror is reported before retrying the same pinned revision upstream. Weights are verified. Local chat runtimes use their own download channels.

## Models and licenses

| Model | Purpose / download | License |
| --- | --- | --- |
| [MIDI-LLM](https://huggingface.co/slseanwu/MIDI-LLM_Llama-3.2-1B) | Text-to-MIDI, approximately 3.45 GB, pinned revision | Llama 3.2 Community License; Built with Llama |
| [MIDI-GPT Yellow Medium](https://huggingface.co/Metacreation/MIDI-GPT) | Continuation / infill, approximately 351 MB, pinned revision | Weights: CC BY-NC 4.0, noncommercial use |
| [HTDemucs](https://huggingface.co/adefossez/HTDemucs) | Four-stem separation | See model card and Demucs upstream license |
| [Basic Pitch](https://github.com/spotify/basic-pitch) | ONNX weights installed with the package | Apache 2.0 |

The downloader checks SHA-256 for MIDI-LLM, MIDI-GPT, HTDemucs and decoder assets; Basic Pitch ONNX weights are also verified. Exact repositories, revisions and hashes are in [`download_models.py`](text2music/agent/download_models.py). Source availability does not give every model the same license. In particular, MIDI-GPT weights have a noncommercial restriction. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Configuration and privacy

Windows settings: `%APPDATA%\Triceratops\runtime.json`; dedicated Python and weights: `%LOCALAPPDATA%\Triceratops\`; generated work and memory: `%APPDATA%\Triceratops\runs\`. Keys stay in the user-owned configuration and are excluded from packages and repository commits. Cloud-mode chat calls send conversation and necessary project/analysis context to your chosen provider, which may charge for usage. Automatic model-source selection contacts an IP geolocation service and retains only the country code and lookup time, without saving the public IP, city or precise location. A proxy/VPN can change the observed egress. Manual source selection skips this query. The backend listens only on `127.0.0.1:49327`.

## Testing feedback

Open an [issue](https://github.com/Aolin-MIR/triceratops-music-agent/issues) with OS, REAPER version, CPU/GPU, reproduction steps, expected behavior and actual behavior. Exclude API keys and private recordings. A short shareable MIDI/audio fixture is helpful.

## Credits

Music models and tools used by this project:

- [MIDI-LLM / Shih-Lun Wu et al.](https://github.com/slSeanWU/MIDI-LLM): text-conditioned multitrack MIDI generation, based on Llama 3.2 with an extended music vocabulary. Built with Llama.
- [MIDI-GPT / Metacreation Lab](https://github.com/Metacreation/MIDI-GPT): **Yellow Medium** weights for continuation and infill, retaining the CC BY-NC 4.0 restriction.
- [HTDemucs / Alexandre Défossez et al.](https://github.com/facebookresearch/demucs): four-stem separation into vocals, drums, bass and other.
- [Basic Pitch / Spotify](https://github.com/spotify/basic-pitch): the ICASSP 2022 ONNX model for MIDI transcription.
- [Anticipation / John Thickstun et al.](https://github.com/jthickstun/anticipation): music-event conversion / decoding used by MIDI-LLM; [JUCE](https://github.com/juce-framework/JUCE) provides the VST3 framework and [librosa](https://github.com/librosa/librosa) provides audio analysis algorithms.

Chat uses a user-configured cloud model or a compatibility-checked local Qwen3.5 model. Windows local inference runs through llama.cpp Vulkan on the GPU; chat weights are not bundled. Unintegrated candidate models are not listed as used components.


Thanks to [Anticipation](https://github.com/jthickstun/anticipation), [JUCE](https://github.com/juce-framework/JUCE) and [librosa](https://github.com/librosa/librosa). See [NOTICE](NOTICE) for third-party licenses.
