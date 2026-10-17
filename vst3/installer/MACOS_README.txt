Triceratops 0.9.1 for REAPER on Apple Silicon

Requires macOS 14 or newer and native ARM64 Python 3.10 or 3.11.
The model backend does not support Intel Macs or Python running under Rosetta.

1. Keep this extracted directory in a permanent location.
2. Run bash setup-macos.sh in Terminal.
   By default it uses python3.11. To select an interpreter:
   TRICERATOPS_PYTHON=/absolute/path/to/python3.11 bash setup-macos.sh
3. Enter your own OpenAI-compatible API key at the hidden prompt.
   An empty response preserves the existing key.
4. Rescan VST3 plug-ins in REAPER and insert Triceratops.

Settings: ~/Library/Application Support/Triceratops/runtime.json
The installer preserves existing paths, device, API endpoint and chat model.
Configuration backups stay in the same folder with owner-only permissions.
The plug-in is installed only after dependencies and model checks pass.
CPU is the default. Models are downloaded at pinned revisions and verified.
Do not delete the extracted backend directory while it is installed.

See the release verification record for actual test coverage and limitations.
