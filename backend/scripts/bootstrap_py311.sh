#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
ENV_PATH="${ROOT_DIR}/.py311"

if ! command -v conda >/dev/null 2>&1; then
  echo "conda is required but not found" >&2
  exit 1
fi

if [ ! -d "${ENV_PATH}" ]; then
  conda create -p "${ENV_PATH}" python=3.11 -y
fi

"${ENV_PATH}/bin/python" -m pip install --upgrade pip
"${ENV_PATH}/bin/pip" install -r "${ROOT_DIR}/backend/requirements.txt"

echo "Environment ready: ${ENV_PATH}"
echo "Run backend with: ${ENV_PATH}/bin/uvicorn backend.main:app --reload"
