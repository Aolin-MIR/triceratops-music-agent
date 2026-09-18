#!/usr/bin/env bash
# Starts the local Text2Score agent for the REAPER ReaScript integration.
set -euo pipefail

project_root="/mnt/e/text2score"
agent_env="$HOME/.config/text2score/qwen.env"

# Optional user-owned credentials. Keep this outside the repository.
if [[ -r "$agent_env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$agent_env"
  set +a
fi

cd "$project_root"
exec .venv/bin/python -m text2music.agent.app
