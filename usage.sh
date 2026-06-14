#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${SCRIPT_DIR}/.venv/bin/python"

if [[ ! -x "${PYTHON}" ]]; then
  echo "Python virtual environment not found at ${PYTHON}" >&2
  exit 1
fi

exec "${PYTHON}" "${SCRIPT_DIR}/usage_report.py" "$@"
