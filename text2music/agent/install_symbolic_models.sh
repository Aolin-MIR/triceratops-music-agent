#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="${ROOT}/.venv/bin/python"
MIRROR="${HF_ENDPOINT:-https://beta.hf-mirror.com}"
MODEL_HOME="${TEXT2SCORE_MODEL_HOME:-${HOME}/.cache/text2score/models}"

mkdir -p "${ROOT}/models" "${ROOT}/third_party" \
  "${MODEL_HOME}/midi-llm" "${MODEL_HOME}/midi-gpt"
if [[ ! -e "${ROOT}/models/midi-llm" ]]; then
  ln -s "${MODEL_HOME}/midi-llm" "${ROOT}/models/midi-llm"
fi
if [[ ! -e "${ROOT}/models/midi-gpt" ]]; then
  ln -s "${MODEL_HOME}/midi-gpt" "${ROOT}/models/midi-gpt"
fi

# Python packages are available from domestic mirrors.
"${PYTHON}" -m pip install 'midigpt[inference]==0.3.4' \
  -i https://pypi.tuna.tsinghua.edu.cn/simple \
  --extra-index-url https://mirrors.aliyun.com/pypi/simple

# MIDI-LLM's decoder has no PyPI release. Pin the exact upstream commit used
# by the official repository.
"${PYTHON}" -m pip install --no-deps \
  'https://codeload.github.com/jthickstun/anticipation/tar.gz/af37397922665a0fb8d474d7988b0f3755a38d45'

# Metadata and ordinary files come from the domestic HF mirror. Large Xet
# blobs may be redirected to the upstream CDN, while retaining resume support.
HF_ENDPOINT="${MIRROR}" HF_HUB_DOWNLOAD_TIMEOUT=120 "${PYTHON}" -c \
  "from huggingface_hub import snapshot_download; snapshot_download('slseanwu/MIDI-LLM_Llama-3.2-1B', revision='8b82ab9ec144348900e9ea4623b123e0b12f60b3', local_dir='${ROOT}/models/midi-llm')"

HF_ENDPOINT="${MIRROR}" HF_HUB_DOWNLOAD_TIMEOUT=120 "${PYTHON}" -c \
  "from huggingface_hub import hf_hub_download; [hf_hub_download('Metacreation/MIDI-GPT', name, revision='3aa5748ba68e32a43c70ddc66b5e595069484532', local_dir='${ROOT}/models/midi-gpt') for name in ('yellow_encoder.json', 'yellow_medium-final.safetensors')]"

printf '%s  %s\n' \
  '7da7f50fefa027208121661c799d3bde2a7c04ad01d40a3d4a597be3fdcaf2ae' "${ROOT}/models/midi-llm/model.safetensors" \
  'acd856168e87c640868ac20cf7523e5912e5171506101fbaebd8eea49a7c4f7c' "${ROOT}/models/midi-gpt/yellow_medium-final.safetensors" \
  | sha256sum --check --strict

echo "Symbolic models installed. Run model_status() to verify readiness."
