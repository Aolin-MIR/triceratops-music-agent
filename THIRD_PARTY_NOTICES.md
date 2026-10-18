# Third-party notices · Triceratops 1.0

The release includes the Triceratops REAPER VST3, desktop Agent source and a Python seed runtime. Third-party software and model artifacts retain their respective licenses.

- JUCE: the pinned submodule `vst3/vendor/JUCE` is distributed under its AGPLv3 option for this open-source VST3. Corresponding source and build scripts are in this repository and its pinned submodule. https://github.com/juce-framework/JUCE
- CPython 3.11.9 Windows embedded distribution: Python Software Foundation License; `LICENSE.txt` ships with the seed runtime. https://www.python.org/downloads/release/python-3119/
- pip, setuptools and runtime Python packages retain the licenses in their installed `.dist-info` directories. Torch is BSD-style; Transformers is Apache 2.0; Basic Pitch is Apache 2.0; Demucs is MIT; midigpt Python/native code is MIT. These package licenses do not relicense model weights.
- MIDI-LLM code and model: Llama 3.2 Community License. Built with Llama. Llama 3.2 is licensed under the Llama 3.2 Community License, Copyright © Meta Platforms, Inc. All Rights Reserved. The downloader retains upstream `LICENSE.md` and model cards. https://huggingface.co/slseanwu/MIDI-LLM_Llama-3.2-1B
- MIDI-GPT Yellow Medium model weights: Creative Commons Attribution-NonCommercial 4.0 International. Copyright (c) 2026 Metacreation Lab. Attribution: Philippe Pasquier, Jeff Ens, Nathan Fradet, Paul Triana, Davide Rizzotti, Jean-Baptiste Rolland and Maryam Safi, MIDI-GPT. https://huggingface.co/Metacreation/MIDI-GPT
- HTDemucs four-stem model and Demucs runtime: Alexandre Défossez and contributors, MIT. The runtime loads `adefossez/HTDemucs` at revision `cbc8a9b1a87023b7fd74e7b3412e6321c0eab003`. https://github.com/facebookresearch/demucs ; https://huggingface.co/adefossez/HTDemucs
- Basic Pitch ICASSP 2022 ONNX model and runtime: Spotify AB and contributors, Apache 2.0. The model is installed with `basic-pitch[onnx]==0.4.0`. https://github.com/spotify/basic-pitch
- Anticipation MIDI decoder: pinned upstream source with its own license metadata retained by pip. https://github.com/jthickstun/anticipation
- Ollama runtime 0.40.6: Ollama contributors, MIT; the macOS package includes the official runtime for native Metal inference. Windows does not bundle or install Ollama. https://github.com/ollama/ollama/tree/v0.40.6
- Local chat Qwen3.5-4B (Q4_K_M GGUF): Qwen team, Apache 2.0. Downloaded from the official model registry and run with llama.cpp Vulkan on Windows; the macOS package uses Ollama with Metal. The selected model passed the native tool-call and conversation compatibility evaluation. https://huggingface.co/Qwen/Qwen3.5-4B
- Microsoft Visual C++ Redistributable: redistributed as Microsoft's unmodified signed installer under its redistribution terms. https://learn.microsoft.com/cpp/windows/latest-supported-vc-redist

Large model files are downloaded separately from their pinned upstream repositories, using the selected Hugging Face endpoint. Consult each model card and license before your intended use. The release is a public testing version, not a grant of commercial model rights.

The active music-model inventory is MIDI-LLM, MIDI-GPT Yellow Medium, HTDemucs and Basic Pitch ONNX. User-selected remote chat providers are not bundled model dependencies. Local chat weights are downloaded separately from the official model registry and run with the platform-specific inference runtime. Model weights have separate licenses. Candidates discussed in research are not release components.
