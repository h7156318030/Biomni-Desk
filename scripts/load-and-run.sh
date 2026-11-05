#!/usr/bin/env bash
# load-and-run.sh
#
# Run this script on the TARGET VM (restricted / air-gapped network) to import
# a previously saved Biomni-Lite Docker image and start the Gradio web UI.
#
# Prerequisites on the VM:
#   - Docker Engine (https://docs.docker.com/engine/install/)
#   - Docker Compose plugin (included with Docker Desktop / Docker Engine ≥ 23)
#
# Usage:
#   bash scripts/load-and-run.sh [image-tarball]
#
# Default tarball: biomni-lite.tar.gz (in the current directory)

set -euo pipefail

IMAGE_TARBALL="${1:-biomni-lite.tar.gz}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# ── 1. Load image ──────────────────────────────────────────────────────────
if ! docker image inspect biomni-lite:latest &>/dev/null; then
    if [[ ! -f "${IMAGE_TARBALL}" ]]; then
        echo "ERROR: Image tarball not found: ${IMAGE_TARBALL}"
        echo "Run scripts/save-image.sh on an internet-connected machine first."
        exit 1
    fi
    echo "==> Loading Docker image from ${IMAGE_TARBALL} ..."
    docker load < "${IMAGE_TARBALL}"
else
    echo "==> Docker image biomni-lite:latest already present, skipping load."
fi

# ── 2. Ensure .env exists ──────────────────────────────────────────────────
ENV_FILE="${REPO_ROOT}/.env"
if [[ ! -f "${ENV_FILE}" ]]; then
    echo ""
    echo "==> No .env file found. Creating one from .env.example ..."
    cp "${REPO_ROOT}/.env.example" "${ENV_FILE}"
    echo ""
    echo "IMPORTANT: Edit ${ENV_FILE} and set your API key(s) before continuing:"
    echo "  ANTHROPIC_API_KEY=sk-ant-..."
    echo ""
    read -rp "Press ENTER after you have saved your API key(s) in .env, or Ctrl-C to abort: "
fi

# ── 3. Create workspace directory for run outputs ──────────────────────────
mkdir -p "${REPO_ROOT}/workspace"

# ── 4. Start the Gradio UI ─────────────────────────────────────────────────
# Source .env to pick up GRADIO_PORT (and other overrides) for the display message.
# Docker Compose already reads .env automatically; this is only needed for the echo.
# shellcheck disable=SC1090
source "${ENV_FILE}" 2>/dev/null || true

PORT="${GRADIO_PORT:-7860}"
AGENT="${BIOMNI_AGENT:-}"

echo ""
echo "==> Starting Biomni-Lite Gradio UI on port ${PORT} ..."

# Recommend direct agent launch for VPN / remote VM deployments to avoid
# the selector page transition (which requires a browser reload).
if [[ -z "${AGENT}" ]]; then
    echo ""
    echo "TIP: For smoother operation on remote VMs / VPN, set BIOMNI_AGENT in .env:"
    echo "  BIOMNI_AGENT=a1   (general biomedical agent)"
    echo "  BIOMNI_AGENT=ad1  (Alzheimer's Disease agent)"
    echo ""
fi

cd "${REPO_ROOT}"
docker compose up biomni-lite-gradio -d

echo ""
echo "Biomni-Lite is running!"
echo "Open http://$(hostname -I 2>/dev/null | awk '{print $1}'):${PORT} in your browser."
echo ""
echo "To view logs : docker compose logs -f biomni-lite-gradio"
echo "To stop      : docker compose down"
