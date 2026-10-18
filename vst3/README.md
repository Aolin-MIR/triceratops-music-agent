# Triceratops 1.0.2 · REAPER VST3

User documentation: [中文](../readme.md) / [English](../README.en.md).

Windows supports REAPER x64 through a native VST3 and a dedicated native Python runtime. macOS supports REAPER VST3 and Logic Pro MIDI FX / Audio FX Audio Units. User installations do not require WSL. See [system requirements](../docs/SYSTEM_REQUIREMENTS.md) for architecture, memory, storage and device constraints.

## Build

```powershell
cmake -S vst3 -B vst3/build-msvc -G "Visual Studio 17 2022" -A x64
cmake --build vst3/build-msvc --config Release --target Triceratops_VST3
```

JUCE is a pinned Git submodule; clone with `--recurse-submodules`.
The single Windows plug-in destination is `C:\Program Files\Common Files\VST3\Triceratops.vst3`. Save and close REAPER before updating it. Developer deployment uses `copy_plugin.ps1`; public distribution uses the EXE described in [installer/README.txt](installer/README.txt).

## Native backend configuration

`%APPDATA%\Triceratops\backend.json` contains `python`, `entry` and `config` absolute paths. The plug-in starts those arguments without invoking a shell. The user-owned runtime configuration supplies paths, selected compute device, API settings and model directory. No developer drive or WSL path is compiled into the VST3.

The macOS equivalent is `~/Library/Application Support/Triceratops/backend.json`. It launches native Python, not WSL.

Local HTTP: `127.0.0.1:49327`. The backend writes the one-shot REAPER importer into the configured runs directory, with that directory injected as a Lua string. Import uses REAPER's `-nonewinst` script support and adds actual MIDI/audio sources on new tracks. Automatic import and explicit import share the same bridge.

## Verification

`python -m pytest -q` runs Agent, MIDI, service and release-path regression tests. `python -m text2music.agent.doctor --config <runtime.json>` checks dependencies, selected device, model checksums and Basic Pitch ONNX initialization.

Audio verification helpers in `tools/` were used against actual audio, MIDI and REAPER projects. Historical Steinberg validator results do not certify the v0.9 build. Public release notes record the checks that were actually rerun.
