#!/usr/bin/env bash
# save-image.sh
#
# Run this script on an INTERNET-CONNECTED machine to build the Biomni-Lite
# Docker image and export it as a compressed tarball that can be transferred
# to an air-gapped or restricted-internet VM.
#
# Usage:
#   bash scripts/save-image.sh [output-file]
#
# Default output file: biomni-lite.tar.gz
#
# After running this script, copy the tarball to your VM, e.g.:
#   scp biomni-lite.tar.gz user@<vm-ip>:~/
# Then on the VM run:
#   bash scripts/load-and-run.sh biomni-lite.tar.gz

set -euo pipefail

IMAGE_NAME="biomni-lite:latest"
OUTPUT_FILE="${1:-biomni-lite.tar.gz}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "==> Building Docker image: ${IMAGE_NAME}"
docker build -t "${IMAGE_NAME}" "${REPO_ROOT}"

echo "==> Exporting image to ${OUTPUT_FILE} ..."
docker save "${IMAGE_NAME}" | gzip > "${OUTPUT_FILE}"

SIZE=$(du -sh "${OUTPUT_FILE}" | cut -f1)
echo ""
echo "Done. Image saved to: ${OUTPUT_FILE} (${SIZE})"
echo ""
echo "Transfer this file to your VM, then run:"
echo "  bash scripts/load-and-run.sh ${OUTPUT_FILE}"
