TRICERATOPS 0.9 - REAPER ONLY

Windows users: download Triceratops-0.9.0-Windows-x64-Setup.exe from
https://github.com/Aolin-MIR/triceratops-music-agent/releases/tag/v0.9.0

The EXE installs the canonical system VST3 and a Python seed runtime. After
installation, Configure runtime and download models creates a dedicated native
Python environment in your user profile, downloads runtime packages and pinned
models, verifies hashes and checks the selected compute device. WSL is not used.

CPU is the default. CUDA is an explicit option and requires a compatible NVIDIA
driver. Your own Qwen/OpenAI-compatible API key is required for Agent chat.
Large weights are downloaded during setup, not embedded in the EXE.

BUILD (Windows)
1. Initialize the pinned JUCE submodule and build the MSVC Release VST3.
2. Obtain the official Python 3.11.9 x64 embeddable ZIP. Its SHA-256 is
   009d6bf7e3b2ddca3d784fa09f90fe54336d5b60f0e0f305c37f400bf83cfd3b.
3. Extract into a clean Python seed directory. Enable `import site` in
   python311._pth and bootstrap pip using the official get-pip.py. The seed must
   contain only Python, pip/setuptools/wheel and their dependencies, not models,
   credentials or development packages.
4. Run:
   python vst3/installer/package_release.py --platform windows --plugin <VST3 bundle> --python-seed <clean seed> --output vst3/package/payload
5. Download Microsoft's signed VC++ x64 redistributable to
   vst3/package/tools/vc_redist.x64.exe. Verify its Authenticode signature.
6. Compile vst3/installer/Triceratops.iss with Inno Setup 6.7.3 or newer.
   Output: vst3/package/release/Triceratops-0.9.0-Windows-x64-Setup.exe

Do not copy developer qwen.env, runtime.json, recordings or generated histories
into a payload. package_release.py uses an explicit module allowlist.

macOS builds are provided by .github/workflows/macos-vst3.yml. The setup script
requires Apple Silicon, macOS 14+ and native ARM64 Python 3.10/3.11, and installs
a dedicated venv using CPU mode. Mac packages are unsigned / not notarized;
full model and REAPER functionality on physical Mac hardware is not yet verified.
See docs/SYSTEM_REQUIREMENTS.md in the repository for software constraints,
resource budgets and the distinction between recommendations and tested limits.
