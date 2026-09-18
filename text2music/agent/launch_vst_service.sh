#!/usr/bin/env bash
set -euo pipefail

runtime_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
native_site="$HOME/.cache/text2score/site"
legacy_site="/mnt/e/text2score/.venv/lib/python3.10/site-packages"
agent_env="$HOME/.config/text2score/qwen.env"
export TMP=/tmp TEMP=/tmp TMPDIR=/tmp
export TEXT2SCORE_RUNS_DIR="/mnt/e/text2score/text2music/artifacts/agent_runs"
export PYTHONPATH="$runtime_root:$native_site:$legacy_site${PYTHONPATH:+:$PYTHONPATH}"
if [[ -r "$agent_env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$agent_env"
  set +a
fi

if curl --silent --fail --connect-timeout 0.2 --max-time 0.5 \
    http://127.0.0.1:49327/health >/dev/null 2>&1; then
  exit 0
fi
cd "$runtime_root"
exec /usr/bin/python3 -m text2music.agent.vst_service
