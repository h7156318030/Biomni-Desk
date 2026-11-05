#!/usr/bin/env bash
# Start Biomni-Lite on macOS and Linux: the backend on port 8765 and the web page on port 3001.
# Stop it with ./stop.sh
set -euo pipefail
cd "$(dirname "$0")"

[ -x .venv/bin/python ] || { echo "Biomni-Lite is not installed yet. Run ./install.sh first."; exit 1; }
export PYTHONIOENCODING=utf-8
export NO_PROXY=localhost,127.0.0.1,::1
export no_proxy=localhost,127.0.0.1,::1
mkdir -p ui_data

echo "Starting the backend (the agent needs about a minute to load)..."
nohup .venv/bin/python -m biomni_ui.server > ui_data/backend.log 2>&1 &
echo $! > ui_data/backend.pid

echo "Starting the web page..."
(cd web && nohup npm run start -- -p 3001 > ../ui_data/web.log 2>&1 &
 echo $! > ../ui_data/web.pid)

sleep 6
echo ""
echo "Open http://localhost:3001 and wait until the bottom-left corner says Ready."
echo "Logs: ui_data/backend.log and ui_data/web.log"
if command -v open >/dev/null 2>&1; then open http://localhost:3001 || true; fi
