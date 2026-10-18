#!/bin/bash
# Install native files and register the in-plugin setup screen.
set -euo pipefail
if [[ "$(uname -m)" != "arm64" ]]; then
  echo "Triceratops 1.0.1 requires Apple Silicon for its model runtime." >&2
  exit 1
fi
root="$(cd -- "$(dirname -- "$0")" && pwd)"
python="${TRICERATOPS_PYTHON:-python3.11}"
"$python" -c 'import sys,platform; assert platform.machine() == "arm64", "Use native ARM64 Python, not an x86 interpreter under Rosetta"; assert (3,10) <= sys.version_info < (3,12), "Use Python 3.10 or 3.11"; assert tuple(map(int,platform.mac_ver()[0].split(".")[:2])) >= (14,0), "The pinned Torch runtime requires macOS 14 or newer"'
# Verify the distributed native bundles before changing installed files.
for bundle in "$root/Triceratops.vst3" "$root"/*.component; do
  [[ -d "$bundle" ]] || continue
  /usr/bin/codesign --verify --deep --strict "$bundle"
done
data="$HOME/Library/Application Support/Triceratops"
mkdir -p "$data" "$HOME/Library/Audio/Plug-Ins/VST3"
"$python" -m venv "$data/venv-1.0.1"
runtime="$data/venv-1.0.1/bin/python"
export PYTHONPATH="$root/backend"
"$runtime" "$root/configure_macos.py" "$data" "$runtime"
# Setup jobs install/check dependencies and models in the plug-in Settings UI.
# Reuse existing configured paths and credentials; never print or prompt for keys.
"$runtime" - "$root" "$data" <<'PYSETUP'
import sys
from pathlib import Path
from text2music.agent.first_run import initialize
root,data=map(Path,sys.argv[1:])
initialize(root, data, data, '/Applications/REAPER.app/Contents/MacOS/REAPER')
PYSETUP
plugin="$HOME/Library/Audio/Plug-Ins/VST3/Triceratops.vst3"
if [[ -e "$plugin" ]]; then
  cp -R "$plugin" "$data/Triceratops-vst3-backup-$(date +%Y%m%d-%H%M%S)"
fi
ditto "$root/Triceratops.vst3" "$plugin"
for component in "$root"/*.component; do
  [[ -d "$component" ]] || continue
  destination="$HOME/Library/Audio/Plug-Ins/Components/$(basename "$component")"
  mkdir -p "$HOME/Library/Audio/Plug-Ins/Components"
  if [[ -e "$destination" ]]; then
    cp -R "$destination" "$data/$(basename "$component")-backup-$(date +%Y%m%d-%H%M%S)"
  fi
  ditto "$component" "$destination"
done
echo 'Triceratops 1.0.1 installed. Rescan VST3 / Audio Units. Open Settings to detect hardware, download and verify models, then apply. Keep this extracted directory in place.'
