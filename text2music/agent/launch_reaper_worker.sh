#!/usr/bin/env bash
# Starts the one-per-panel Text2Score GPU worker. It exits when the panel writes
# the shutdown marker; completed music remains in the Windows-visible runs dir.
set -euo pipefail

runtime_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
inference_dir="$runtime_root/text2music/inference"
queue="/mnt/e/text2score/text2music/artifacts/agent_runs/worker_queue"
native_site="$HOME/.cache/text2score/site"
legacy_site="/mnt/e/text2score/.venv/lib/python3.10/site-packages"
headers="$HOME/.cache/text2score/python-dev/usr/include/python3.10"
mkdir -p "$queue"

# A panel close leaves this exact marker on purpose. A new panel session must
# discard that old marker before bringing up its own worker.
rm -f "$queue/shutdown"

# Brackets avoid matching this pgrep command itself.
if pgrep -f '[w]arm_worker.py' >/dev/null 2>&1; then exit 0; fi

# Publish a fresh state before Torch boot
printf 'STATE: loading\nDETAIL: Loading local GPU PyTorch model service\n' > "$queue/worker-state.txt"
export TMP=/tmp TEMP=/tmp TMPDIR=/tmp
export TEXT2SCORE_RUNS_DIR="/mnt/e/text2score/text2music/artifacts/agent_runs"
export TEXT2SCORE_WORKER_QUEUE="$queue"
export CPATH="$headers:$HOME/.cache/text2score/python-dev/usr/include${CPATH:+:$CPATH}"
export PYTHONPATH="$inference_dir:$runtime_root/text2music/inference:$runtime_root:$native_site:$legacy_site${PYTHONPATH:+:$PYTHONPATH}"

cd "$inference_dir"
exec /usr/bin/python3 warm_worker.py
