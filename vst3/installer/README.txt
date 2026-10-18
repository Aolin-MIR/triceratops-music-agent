TRICERATOPS 1.0 - REAPER ONLY

Windows users: download Triceratops-1.0.1b-Windows-x64-Setup.exe from
https://github.com/Aolin-MIR/triceratops-music-agent/releases/latest

The EXE installs the canonical VST3, a Python seed and the Vulkan llama.cpp
runtime. Ollama is not installed or bundled on Windows. Open Settings inside
the plug-in to detect devices, install packages, download models and verify
chat. Local chat downloads its GGUF directly from the official model registry,
checks its size and SHA-256, then runs it with llama.cpp on the selected GPU.
Configuration and downloads run in background jobs; cancellation retains the
prior settings. WSL is not used.

Auto setup tests local chat first. If it fails, cloud chat requires your own
compatible API key and a successful native tool-call / tool-replay probe.
Direct buttons work without any chat API. Selected devices stay fixed during
use; local chat remains resident. Music-model downloads use the selected regional
endpoint and verify pinned revisions. On Windows, local chat downloads only its
GGUF model directly from the official registry. Large model weights are fetched
inside the plug-in and are not bundled in the EXE.

BUILD (Windows)
1. Initialize the pinned JUCE submodule and build the MSVC Release VST3.
2. Obtain the official Python 3.11.9 x64 embeddable ZIP. Its SHA-256 is
   009d6bf7e3b2ddca3d784fa09f90fe54336d5b60f0e0f305c37f400bf83cfd3b.
3. Extract into a clean Python seed directory. Enable `import site` in
   python311._pth and bootstrap pip using the official get-pip.py. The seed must
   contain only Python, pip/setuptools/wheel and their dependencies, not models,
   credentials or development packages.
4. Run:
   python vst3/installer/package_release.py --platform windows --plugin <VST3 bundle> --python-seed <clean seed> --llama-cpp-runtime <verified Vulkan llama.cpp directory> --output vst3/package/payload
5. Download Microsoft's signed VC++ x64 redistributable to
   vst3/package/tools/vc_redist.x64.exe. Verify its Authenticode signature.
6. Compile vst3/installer/Triceratops.iss with Inno Setup 6.7.3 or newer.
   Output: vst3/package/release/Triceratops-1.0.1b-Windows-x64-Setup.exe

Do not copy developer qwen.env, runtime.json, recordings or generated histories
into a payload. package_release.py uses an explicit module allowlist.

macOS builds are provided by .github/workflows/macos-vst3.yml. The online
installer supports Apple Silicon on macOS 14+, prepares native Python and
installs optional local-chat components when selected in the plug-in. Music
models and dependencies are configured in Settings. See MACOS_README.txt and
docs/SYSTEM_REQUIREMENTS.md for installation and hardware requirements.
