#!/bin/bash
# Experimental macOS native setup. Run from the extracted release directory.
set -euo pipefail
if [[ "$(uname -m)" != "arm64" ]]; then
  echo "Triceratops 0.9 model runtime requires Apple Silicon. Intel Mac is not supported by the pinned Torch wheel." >&2
  exit 1
fi

root="$(cd -- "$(dirname -- "$0")" && pwd)"
python="${TRICERATOPS_PYTHON:-python3.11}"
"$python" -c 'import sys,platform; assert platform.machine() == "arm64", "Use native ARM64 Python, not an x86 interpreter under Rosetta"; assert (3,10) <= sys.version_info < (3,12), "Use Python 3.10 or 3.11"; assert tuple(map(int,platform.mac_ver()[0].split(".")[:2])) >= (14,0), "The pinned Torch runtime requires macOS 14 or newer"'
data="$HOME/Library/Application Support/Triceratops"
mkdir -p "$data" "$HOME/Library/Audio/Plug-Ins/VST3"
"$python" -m venv "$data/venv-0.9"
runtime="$data/venv-0.9/bin/python"
"$runtime" -m pip install -r "$root/requirements-runtime.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple
"$runtime" -m pip install --no-deps 'https://codeload.github.com/jthickstun/anticipation/tar.gz/af37397922665a0fb8d474d7988b0f3755a38d45'
if [[ -z "${TRICERATOPS_SETUP_KEY:-}" ]]; then
  read -r -s -p 'Qwen / compatible API key (empty keeps existing): ' TRICERATOPS_SETUP_KEY
  printf '\n'
fi
export TRICERATOPS_SETUP_KEY
export PYTHONPATH="$root/backend"
"$runtime" "$root/configure_macos.py" "$data" "$runtime"
model_home="$("$runtime" -c 'import json,sys; print(json.load(open(sys.argv[1]))["model_home"])' "$data/runtime.json")"
"$runtime" -m text2music.agent.download_models --home "$model_home"
"$runtime" -m text2music.agent.doctor --config "$data/runtime.json"
plugin="$HOME/Library/Audio/Plug-Ins/VST3/Triceratops.vst3"
if [[ -e "$plugin" ]]; then
  cp -R "$plugin" "$data/Triceratops-vst3-backup-$(date +%Y%m%d-%H%M%S)"
fi
ditto "$root/Triceratops.vst3" "$plugin"
"$runtime" - "$root" "$data" <<'PY'
import json,sys
from pathlib import Path
root,data=map(Path,sys.argv[1:])
settings=json.loads((data/'runtime.json').read_text())
(data/'backend.json').write_text(json.dumps(dict(python=settings['python'],
 entry=str(root/'backend/text2music/agent/runtime.py'),config=str(data/'runtime.json')),indent=2))
PY
unset TRICERATOPS_SETUP_KEY
echo 'Setup complete. Rescan Triceratops in REAPER. Keep this extracted directory in place.'
