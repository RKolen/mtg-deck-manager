#!/usr/bin/env bash
# Run sim lint and type checks (pylint 10/10 + pyright strict).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="${ROOT}/.venv"
SIM="${ROOT}/sim"

if [[ ! -x "${VENV}/bin/python" ]]; then
  echo "Create the venv first: python3 -m venv ${VENV}" >&2
  exit 1
fi

"${VENV}/bin/pip" install -q -r "${SIM}/requirements-dev.txt"
echo "==> pyright (strict)"
"${VENV}/bin/pyright" "${SIM}"
echo "==> pylint"
"${VENV}/bin/pylint" "${SIM}"
