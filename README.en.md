# Triceratops Music Agent

[中文](readme.md) | [English](README.en.md)

**Keep the next few bars inside your REAPER project.**

Triceratops is a music Agent VST3 for REAPER. Describe an idea naturally or use the action buttons to generate, continue, edit and analyze MIDI, then import editable results into real REAPER tracks.

**REAPER only. Windows uses a native Python backend; WSL is not required.** Chat and intent rewriting can use a compatible cloud tool-calling API or a local model on the GPU through llama.cpp. Local chat does not fall back to CPU. Explicit analysis, timing, velocity, continuation, separation and transcription buttons call local tools directly without a chat API. Music processing runs locally.

[![Triceratops 0.9 feature overview](docs/images/triceratops-0.9-overview.webp)](https://github.com/Aolin-MIR/triceratops-music-agent/releases/download/v0.9.0/Triceratops-0.9.0-Feature-Overview.png)

## This update · 1.0 integration

Current checks: local Qwen3.5 4B completed 21 real chat/tool-flow scenarios through the native Windows llama.cpp/Vulkan backend (21/21 passed), plus 13 local-GPU scenarios covering small talk, capability discovery, ambiguity, out-of-scope requests, memory and mixed intent (13/13 passed). A real text-guided MIDI generation check preserved a detailed Chinese request as a natural English MIDI-LLM prompt and returned a parseable MIDI containing notes. Startup logs confirmed all 33/33 chat-model layers were offloaded to the RTX 3080 Laptop GPU. Another 115 Python unit tests passed. These checks cover the stated inputs and devices; they do not guarantee musical quality for every prompt or validate every model/device combination.

This source update is part of the **1.0 integration**; download links below still point to the existing **v0.9 installers**, which do not include unrepackaged 1.0 changes. Physical Mac validation remains pending, and the 1.0 installer has not been released.

- **Local chat adapter**: llama.cpp Vulkan GPU inference on Windows, with native tool calling and tool-result replay; a cloud API can be selected separately. Selected models must pass a compatibility probe; arbitrary providers and models are not guaranteed to work.
- **Direct action buttons**: analysis, four-bar continuation, velocity, timing, stem separation, transcription, undo and feedback execute without asking an LLM. These actions remain available with chat disabled.
- **Fixed devices**: select CPU / GPU explicitly for the resident local LLM. GPU mode rejects automatic CPU offload. MIDI-LLM, MIDI-GPT and HTDemucs have separate device settings, with no automatic migration between tasks.
- **Model download routing**: a mainland-China public egress IP prefers `hf-mirror.com` only when pinned metadata is available without an overseas redirect. Unavailable mirrors are reported and select the official source; other regions use official Hugging Face, with manual `official` / `china` selection. Failed geolocation is reported and selects the official source, without guessing from UI language. Revisions are pinned and music weight SHA-256 hashes are checked. The local chat model is downloaded through the Ollama registry and then run by llama.cpp; no byte-identical domestic mirror has been verified. Routing affects models only, without changing API endpoints or dependency sources.
- **Hardware planner**: device recommendations account for available RAM, VRAM and model budgets, with lighter music work on CPU. The hardware planner and in-plugin Settings panel are integrated. Actual checks covered detection, verification/apply and cancellation retaining the previous configuration. The panel uses the existing colors and type styles. Both cloud and local GPU chat passed real tool-flow checks. Model quality, speed and API replacement on other hardware still require separate evaluation.

Native Windows CPU measurements (Ryzen 9 5900HX, 27.9 GiB currently visible memory):

| Task | Conditions | Time |
| --- | --- | --- |
| MIDI-GPT continuation | 12 input notes, 4 new bars | About 11.2 s first run; 3.7 s repeated |
| HTDemucs separation | 12 s audio, 4 stems | About 19.9 s |
| Basic Pitch transcription | Short trumpet fixture | About 13.2 s |
| Audio analysis | 12 s audio, including initial imports | About 19.2 s |
| MIDI-LLM generation | Default limit of 768 new tokens, including loading | About 247 s |

These are offline measurements for specific inputs and hardware. Full CPU generation is slow; the planner favors GPU for MIDI-LLM when sufficient resources remain. Mac physical-machine results will be added after the Mac changes are merged.

## Download and install

- [Windows x64 EXE installer](https://github.com/Aolin-MIR/triceratops-music-agent/releases/download/v0.9.0/Triceratops-0.9.0-Windows-x64-Setup.exe)
- [Release notes, checksums and available assets](https://github.com/Aolin-MIR/triceratops-music-agent/releases/tag/v0.9.0)
- [macOS Apple Silicon ZIP](https://github.com/Aolin-MIR/triceratops-music-agent/releases/download/v0.9.0/Triceratops-0.9.0-macOS-AppleSilicon.zip): requires **Apple Silicon, macOS 14+, and native ARM64 Python 3.10 / 3.11**. Extract and keep the directory, then run `bash setup-macos.sh`. The universal VST3 build passed; testing in REAPER on a physical Mac is pending. Intel Mac model execution is not supported.

1. Save your project and close REAPER. Run the EXE. The single VST3 installation is `C:\Program Files\Common Files\VST3\Triceratops.vst3`.
2. Open **Configure runtime and download models** at the end of installation or from the Start menu. Select REAPER, a model directory and compute device, and enter your cloud API settings. This describes the released v0.9 utility; local chat and direct-button modes are configured in 1.0. A dedicated native Python seed is included, without modifying system Python.
3. First setup downloads runtime packages and models. The existing v0.9 installer defaults to the Tsinghua PyPI mirror and `hf-mirror.com`; the downloader on `main` now routes model sources by public egress country. Failed downloads report an error; rerun setup to resume. Missing models never silently select a different generator.
4. In REAPER, open **Preferences → Plug-ins → VST → Re-scan**, then insert **Triceratops**.
5. Rerun configuration to change settings or download missing files. Uninstalling the application retains user models, credentials and generated work for backup or manual removal.

The current v0.9 EXE includes the plug-in, configuration utility and Python seed. **Large weights are downloaded by setup, not embedded in the EXE.** CPU is the default. An unavailable selected device produces an error rather than a silent device switch.

In 1.0, use **Settings** in the plug-in header to detect hardware, choose chat mode and model sources, download/setup, verify/apply or cancel. The Windows installer bundles Ollama as a model-download utility and llama.cpp Vulkan for inference; chat weights are downloaded from Settings. The 1.0 installer has not been publicly released yet.

Use **中文 / English** in the plug-in header to switch buttons, status text, hints and operation reports. The language preference is remembered; chat defaults to the selected interface language.

## System requirements

**Software constraints, suggested resource budgets and tested configurations are different.** A full-feature minimum has not been established by testing machines with different memory capacities; these recommendations are not certified minimums.

| Item | Windows | macOS |
| --- | --- | --- |
| OS / architecture | Windows 10 / 11 x64; Windows 11 tested, Windows 10 not separately verified | Apple Silicon (M1 or newer), macOS 14+; Intel Mac model execution is unsupported |
| Host | REAPER x64; 7.80 tested, 7.80 or newer recommended | Native Apple Silicon REAPER, 7.80 or newer recommended; full physical-machine testing pending |
| Python | Dedicated Python 3.11.9 included; no WSL required | User-installed native ARM64 Python 3.10 / 3.11; setup looks for `python3.11` by default |
| Memory budget | Start with 16 GB for CPU use; 32 GB gives more room for instruments / longer audio; not a measured minimum | Start with 16 GB unified memory, preferably 32 GB; 8 GB is not a recommended full-feature configuration; no Mac measurements yet |
| Graphics | No discrete GPU needed for CPU mode; the current CUDA path uses BF16, so a BF16-capable Ampere or newer NVIDIA GPU and a conservative 16 GB VRAM budget are recommended | Setup selects CPU; no discrete GPU required; MPS / MLX acceleration is not validated |
| Free storage budget | Reserve 20 GB for CPU or 30 GB for CUDA installation, plus download caches, audio and projects | Reserve 20 GB, plus download caches, audio and projects |
| Network / API | Internet for initial dependencies / weights; free-form chat needs a compatible cloud API or a local Windows GPU model; direct buttons need no API | Same; the Mac ZIP includes neither Python nor model weights, and its local chat backend awaits testing |

Storage and memory figures are conservative planning recommendations, not measured peaks for every feature. Music weights total approximately 4 GB; the default local-chat candidate adds about 3.32 GB. Neither figure represents the full installation or runtime footprint. CPU generation is an offline task with no real-time guarantee. CUDA also requires an NVIDIA driver that can run the installer's `cu130` PyTorch build; the CUDA version shown by `nvidia-smi` alone does not prove compatibility. AMD / Intel GPU acceleration, Windows ARM64 and Intel Mac are outside current support.

See **[System requirements and support scope (中文 / English)](docs/SYSTEM_REQUIREMENTS.md)** for evidence, tested configurations and differences between features.

## Chat modes and fixed devices

- **remote**: configure a cloud endpoint, model and API key. Setup actually probes native tool calling and tool-result replay; compatibility is not guaranteed for every provider.
- **Windows local GPU chat**: choose local chat and `qwen3.5:4b-q4_K_M` in plug-in Settings. The bundled Ollama utility downloads the model; llama.cpp Vulkan runs inference on the GPU and must pass a GPU-residency check. CPU inference is not used as a fallback. No cloud key is required.
- **disabled**: free-form chat is disabled while explicit buttons remain available. New-score descriptions and open-ended edits require an enabled language model.

The local LLM uses an explicit **CPU / GPU** choice and remains resident, without per-task unloading or automatic device changes. GPU mode checks actual residency and rejects automatic CPU offload. MIDI-LLM, MIDI-GPT and HTDemucs have separate fixed-device settings; new setup defaults prioritize CPU for MIDI-GPT and separation. Basic Pitch ONNX and audio analysis use CPU. Insufficient resources produce an error; change settings explicitly if necessary.

## Features

| Action | Implementation |
| --- | --- |
| Chat / New score | Broad Chinese or English requests, small talk and intent rewriting; preserves concrete and abstract musical descriptions for text-conditioned MIDI-LLM generation. Unsupported requests receive a clear scope response |
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

The 1.0 downloader checks SHA-256 for MIDI-LLM, MIDI-GPT and HTDemucs weights. Exact repositories, revisions and hashes are in [`download_models.py`](text2music/agent/download_models.py). Source availability does not give every model the same license. In particular, MIDI-GPT weights have a noncommercial restriction. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Configuration and privacy

Windows settings: `%APPDATA%\Triceratops\runtime.json`; dedicated Python and weights: `%LOCALAPPDATA%\Triceratops\`; generated work and memory: `%APPDATA%\Triceratops\runs\`. Keys stay in the user-owned configuration and are excluded from packages and repository commits. Cloud-mode chat calls send conversation and necessary project/analysis context to your chosen provider, which may charge for usage. Automatic model-source selection contacts an IP geolocation service and retains only the country code and lookup time, without saving the public IP, city or precise location. A proxy/VPN can change the observed egress. Manual source selection skips this query. The backend listens only on `127.0.0.1:49327`.

## Testing feedback

Open an [issue](https://github.com/Aolin-MIR/triceratops-music-agent/issues) with OS, REAPER version, CPU/GPU, reproduction steps, expected behavior and actual behavior. Exclude API keys and private recordings. A short shareable MIDI/audio fixture is helpful.

## Credits

Music models and tools actually used by v0.9:

- [MIDI-LLM / Shih-Lun Wu et al.](https://github.com/slSeanWU/MIDI-LLM): text-conditioned multitrack MIDI generation, based on Llama 3.2 with an extended music vocabulary. Built with Llama.
- [MIDI-GPT / Metacreation Lab](https://github.com/Metacreation/MIDI-GPT): **Yellow Medium** weights for continuation and infill, retaining the CC BY-NC 4.0 restriction.
- [HTDemucs / Alexandre Défossez et al.](https://github.com/facebookresearch/demucs): four-stem separation into vocals, drums, bass and other.
- [Basic Pitch / Spotify](https://github.com/spotify/basic-pitch): the ICASSP 2022 ONNX model for MIDI transcription.
- [Anticipation / John Thickstun et al.](https://github.com/jthickstun/anticipation): music-event conversion / decoding used by MIDI-LLM; [JUCE](https://github.com/juce-framework/JUCE) provides the VST3 framework and [librosa](https://github.com/librosa/librosa) provides audio analysis algorithms.

Chat uses a user-configured cloud model or a compatibility-checked local Qwen3.5 model. Windows local inference runs through llama.cpp Vulkan on the GPU; chat weights are not bundled. Unintegrated candidate models are not listed as used components.

Source provenance: this repository originated from [Keshav Bhandari/Text2Score](https://github.com/keshavbhandari/text2score), so source attribution is retained. **The v0.9 release does not install, download or invoke Text2Score trained weights.** Triceratops Agent, REAPER integration and desktop distribution work are maintained here. Full attribution and licenses are in [NOTICE](NOTICE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
