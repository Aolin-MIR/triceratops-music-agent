#!/bin/bash
# Install native files and register the in-plugin setup screen.
set -euo pipefail
if [[ "$(uname -m)" != "arm64" ]]; then
  echo "Triceratops 1.0.1b requires Apple Silicon for its model runtime." >&2
  exit 1
fi
root="$(cd -- "$(dirname -- "$0")" && pwd)"
if /usr/bin/pgrep -x REAPER >/dev/null || /usr/bin/pgrep -x 'Logic Pro' >/dev/null; then
  echo 'Save and quit REAPER / Logic Pro before installing. No applications were closed.' >&2
  exit 1
fi
[[ "$(/usr/bin/sw_vers -productVersion | cut -d . -f 1)" -ge 14 ]] || { echo 'Requires macOS 14 or newer.' >&2; exit 1; }
data="${TRICERATOPS_DATA_DIR:-$HOME/Library/Application Support/Triceratops}"
umask 077
mkdir -p "$data"
python="$(/bin/bash "$root/bootstrap-python.sh" "$data")"
"$python" -c 'import sys,platform; assert platform.machine() == "arm64", "Use native ARM64 Python, not an x86 interpreter under Rosetta"; assert (3,10) <= sys.version_info < (3,12), "Use Python 3.10 or 3.11"; assert tuple(map(int,platform.mac_ver()[0].split(".")[:2])) >= (14,0), "The pinned Torch runtime requires macOS 14 or newer"'
# Verify the distributed native bundles before changing installed files.
for bundle in "$root/Triceratops.vst3" "$root"/*.component; do
  [[ -d "$bundle" ]] || continue
  /usr/bin/codesign --verify --deep --strict "$bundle"
done
mkdir -p "$data" "$HOME/Library/Audio/Plug-Ins/VST3"
"$python" -m venv "$data/venv-1.0.1b"
runtime="$data/venv-1.0.1b/bin/python"
export PYTHONPATH="$root/backend"
"$runtime" "$root/backend/text2music/agent/macos_bootstrap.py" --data "$data" --source "${TRICERATOPS_DOWNLOAD_SOURCE:-auto}"
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
"$runtime" - "$root" "$data" <<'PYRECEIPT'
import hashlib, json, os, sys, time
from pathlib import Path
root, data = map(Path, sys.argv[1:])
receipt = {'version': '1.0.1b', 'installer': 'online', 'completed_at': int(time.time()),
           'backend': str(root / 'backend'), 'python': sys.executable,
           'download_source': os.environ.get('TRICERATOPS_DOWNLOAD_SOURCE', 'auto')}
path = data / 'installation-online.json'
temporary = path.with_suffix('.tmp')
temporary.write_text(json.dumps(receipt, indent=2))
temporary.chmod(0o600)
os.replace(temporary, path)
PYRECEIPT
echo 'Triceratops 1.0.1b installed. Rescan VST3 / Audio Units. Open Settings to detect hardware, download and verify models, then apply. Keep this extracted directory in place.'
