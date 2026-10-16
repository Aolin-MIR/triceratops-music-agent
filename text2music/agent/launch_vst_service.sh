#!/usr/bin/env bash
set -euo pipefail
runtime_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
config="${1:?Pass the installed runtime.json configuration file}"
python="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["python"])' "$config")"
export PYTHONPATH="$runtime_root${PYTHONPATH:+:$PYTHONPATH}"
cd "$runtime_root"
exec "$python" -m text2music.agent.runtime --config "$config"
