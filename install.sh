#!/usr/bin/env bash
# Biomni-Lite one-click installer for macOS and Linux.
# Usage: ./install.sh            (all packages)
#        ./install.sh --core     (core packages only: no scanpy, rdkit and other large analysis packages)
set -euo pipefail
cd "$(dirname "$0")"

step() { printf '\n== %s\n' "$1"; }
fail() { printf '\nERROR: %s\n' "$1" >&2; exit 1; }

step "Checking Python (3.12)"
PY=""
for c in python3.12 python3; do
    if command -v "$c" >/dev/null 2>&1; then
        v=$("$c" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || true)
        if [ "$v" = "3.12" ]; then PY="$c"; break; fi
    fi
done
[ -n "$PY" ] || fail "Python 3.12 was not found. Install it (for example: brew install python@3.12) and run this again."
echo "Using $($PY --version)"

step "Checking Node.js (20 or newer)"
command -v node >/dev/null 2>&1 || fail "Node.js was not found. Install version 20 or newer (for example: brew install node) and run this again."
major=$(node -p 'process.versions.node.split(".")[0]')
[ "$major" -ge 20 ] || fail "Node.js is too old ($(node -v)). Install version 20 or newer."
echo "Node.js $(node -v)"

step "Creating the Python environment (.venv)"
[ -x .venv/bin/python ] || "$PY" -m venv .venv
.venv/bin/python -m pip install --upgrade pip >/dev/null

step "Installing Python packages (this can take several minutes)"
REQ=requirements.txt
if [ "${1:-}" = "--core" ]; then
    sed '/^# Analysis packages/,$d' requirements.txt > .requirements-core.txt
    REQ=.requirements-core.txt
fi
.venv/bin/python -m pip install -r "$REQ" || fail "Installing the Python packages failed. Read the messages above, fix the cause and run this again."

step "Preparing the settings file and data folder"
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example. No keys are set: add your model keys in the app's Settings page."
fi
mkdir -p ui_data

step "Building the web page (first time only, about a minute)"
(cd web && npm install && npm run build) || fail "The web page build failed."

printf '\nInstalled. Start Biomni-Lite with ./start.sh, then open http://localhost:3001\n'
