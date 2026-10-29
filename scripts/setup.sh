#!/usr/bin/env bash
# Optional: set up (or repair) image-peak's environment now instead of on first use, and report what it
# found. Any image-peak command does the same set-up automatically when it is needed.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$here/image-peak" doctor
