#!/bin/bash
# Experimental macOS native setup. Run from the extracted release directory.
set -euo pipefail
if [[ "$(uname -m)" != "arm64" ]]; then
  echo "Triceratops 0.9 model runtime requires Apple Silicon. Intel Mac is not supported by the pinned Torch wheel." >&2
  exit 1
fi

root="$(cd -- "$(dirname -- "$0")" && pwd)"
python="${TRICERATOPS_PYTHON:-python3.11}"
"$python" -c 'import sys,platform; assert (3,10) <= sys.version_info < (3,12), "Use Python 3.10 or 3.11"; assert tuple(map(int,platform.mac_ver()[0].split(".")[:2])) >= (14,0), "The pinned Torch runtime requires macOS 14 or newer"'
data="$HOME/Library/Application Support/Triceratops"
mkdir -p "$data" "$HOME/Library/Audio/Plug-Ins/VST3"
cp -R "$root/Triceratops.vst3" "$HOME/Library/Audio/Plug-Ins/VST3/"
"$python" -m venv "$data/venv-0.9"
runtime="$data/venv-0.9/bin/python"
"$runtime" -m pip install -r "$root/requirements-runtime.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple
"$runtime" -m pip install --no-deps 'https://codeload.github.com/jthickstun/anticipation/tar.gz/af37397922665a0fb8d474d7988b0f3755a38d45'
read -r -s -p 'Qwen / compatible API key: ' TRICERATOPS_SETUP_KEY
printf '\n'
export TRICERATOPS_SETUP_KEY
export PYTHONPATH="$root/backend"
"$runtime" -m text2music.agent.download_models --home "$data/models"
"$runtime" - "$root" "$data" <<'PY'
import json,os,sys
from pathlib import Path
root,data=map(Path,sys.argv[1:])
python=data/'venv-0.9/bin/python'
config=data/'runtime.json'
settings=dict(python=str(python),runs_dir=str(data/'runs'),model_home=str(data/'models'),
              reaper='/Applications/REAPER.app/Contents/MacOS/REAPER',device='cpu',
              api_key=os.environ['TRICERATOPS_SETUP_KEY'])
config.write_text(json.dumps(settings,indent=2))
config.chmod(0o600)
PY
"$runtime" -m text2music.agent.doctor --config "$data/runtime.json"
"$runtime" - "$root" "$data" <<'PY'
import json,sys
from pathlib import Path
root,data=map(Path,sys.argv[1:])
(data/'backend.json').write_text(json.dumps(dict(python=str(data/'venv-0.9/bin/python'),
 entry=str(root/'backend/text2music/agent/runtime.py'),config=str(data/'runtime.json')),indent=2))
PY
unset TRICERATOPS_SETUP_KEY
echo 'Setup complete. Rescan Triceratops in REAPER. Keep this extracted directory in place.'
