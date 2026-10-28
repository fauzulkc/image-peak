#!/usr/bin/env bash
# One-time setup inside WSL: a venv with the four packages the pipeline needs.
# imagecodecs ships libultrahdr (Google's gain-map encoder) as a prebuilt wheel, so nothing is compiled.
set -euo pipefail
venv="$HOME/.venvs/image-peak"
[ -x "$venv/bin/python" ] || python3 -m venv "$venv"
"$venv/bin/pip" install --quiet --upgrade numpy opencv-python-headless pillow imagecodecs
"$venv/bin/python" - <<'PY'
import cv2, imagecodecs, numpy, PIL
assert imagecodecs.ULTRAHDR.available, "imagecodecs was built without libultrahdr"
print(f"ready: numpy {numpy.__version__}, opencv {cv2.__version__}, pillow {PIL.__version__}, "
      f"imagecodecs {imagecodecs.__version__}, {imagecodecs.ultrahdr_version()}")
PY
echo "generator CLIs for the bundled adapters (any other generator: write an adapter or use plan/build):"
if command -v agent >/dev/null; then echo "  cursor: $(agent status 2>&1 | tail -1)"; else echo "  cursor: agent CLI not installed"; fi
if command -v agy >/dev/null; then echo "  agy: installed ($(agy --version 2>&1 | head -1))"; else echo "  agy: not installed"; fi
