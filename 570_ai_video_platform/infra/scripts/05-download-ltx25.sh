#!/bin/bash
# Compatibility entry point; all model downloads now live in 03-download-models.sh.
set -euo pipefail
echo "Using 03-download-models.sh for all platform models, including LTX-2.5."
exec bash "$(dirname "$0")/03-download-models.sh"
