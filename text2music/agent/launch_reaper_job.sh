#!/usr/bin/env bash
# Runs one non-interactive generation requested by the REAPER ReaScript.
set -euo pipefail

project_root="$HOME/.local/share/text2score-runtime/app"
windows_runs="/mnt/e/text2score/text2music/artifacts/agent_runs"
legacy_site="/mnt/e/text2score/.venv/lib/python3.10/site-packages"
agent_env="$HOME/.config/text2score/qwen.env"
# WSL inherits Windows TEMP by default.  Keeping temporary extraction and the
# large Transformers package on Linux ext4 avoids p9_client_rpc stalls.
export TMP=/tmp TEMP=/tmp TMPDIR=/tmp
python_headers="$HOME/.cache/text2score/python-dev/usr/include/python3.10"
if [[ -d "$python_headers" ]]; then
  export CPATH="$python_headers:$HOME/.cache/text2score/python-dev/usr/include${CPATH:+:$CPATH}"
fi
native_site="$HOME/.cache/text2score/site"
# Core source, PyTorch and Transformers now live on Linux ext4.  Keep only
# small optional dependencies (music21, mido, OpenAI) on the legacy venv path.
export TEXT2SCORE_RUNS_DIR="$windows_runs"
export PYTHONPATH="$project_root:$native_site:$legacy_site${PYTHONPATH:+:$PYTHONPATH}"
if [[ -r "$agent_env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$agent_env"
  set +a
fi

cd "$project_root"
exec /usr/bin/python3 -m text2music.agent.reaper_bridge "$@"
