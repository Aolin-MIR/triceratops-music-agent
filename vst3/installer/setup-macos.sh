#!/bin/bash
# Install native files and register the in-plugin setup screen.
set -euo pipefail
if [[ "$(uname -m)" != "arm64" ]]; then
  echo "Triceratops 1.0 requires Apple Silicon for its model runtime." >&2
  exit 1
fi
root="$(cd -- "$(dirname -- "$0")" && pwd)"
python="${TRICERATOPS_PYTHON:-python3.11}"
"$python" -c 'import sys,platform; assert (3,10) <= sys.version_info < (3,12), "Use native Python 3.10 or 3.11"; assert tuple(map(int,platform.mac_ver()[0].split(".")[:2])) >= (14,0), "macOS 14+ is required"'
data="$HOME/Library/Application Support/Triceratops"
mkdir -p "$data" "$HOME/Library/Audio/Plug-Ins/VST3"
cp -R "$root/Triceratops.vst3" "$HOME/Library/Audio/Plug-Ins/VST3/"
"$python" -m venv "$data/venv-1.0"
runtime="$data/venv-1.0/bin/python"
TRICERATOPS_INSTALL="$root" TRICERATOPS_DATA="$data" "$runtime" - <<'PY'
import json, os, sys
from pathlib import Path
root = Path(os.environ['TRICERATOPS_INSTALL'])
data = Path(os.environ['TRICERATOPS_DATA'])
sys.path.insert(0, str(root/'backend'))
from text2music.agent.first_run import initialize
from text2music.agent.configuration import atomic_json
path = data/'runtime.json'
old = json.loads(path.read_text()) if path.exists() else {}
old['python'] = sys.executable
atomic_json(path, old)
initialize(root, data, data, '/Applications/REAPER.app/Contents/MacOS/REAPER')
PY
printf '%s\n' 'Triceratops 1.0 installed. Open it in REAPER and use Settings to detect devices, download models and verify chat.'
