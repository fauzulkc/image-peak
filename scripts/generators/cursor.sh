#!/usr/bin/env bash
# Adapter: Cursor Agent CLI (Nano Banana). Contract: cursor.sh create|edit <prompt_file> <output_path> [input_image]
# Rules from the cursor-image-gen skill: run from ~/cursor-images, always --trust, never --force/--yolo,
# and tell it not to move or convert the file (headless mode cannot approve shell commands).
set -uo pipefail
mode="$1" prompt_file="$2" output_path="$3" input_image="${4:-}"
mkdir -p ~/cursor-images && cd ~/cursor-images || { echo "cannot use ~/cursor-images" >&2; exit 1; }
name="hdr-$(basename "${output_path%.*}")-$(date +%s)"
if [ "$mode" = edit ]; then
  lead="Use your image generation tool (Nano Banana) in edit mode with the existing image at $input_image as the input image."
else
  lead="Use your image generation tool (Nano Banana) to create this image."
fi
reply=$(agent -p --trust "$lead $(cat "$prompt_file") Name the image $name. Do not run shell commands, do not convert, copy or move the file. When the tool returns, end your reply with one line exactly: IMAGE_PATH: <absolute path to the saved image>" 2>&1)
path=$(printf '%s\n' "$reply" | sed -n 's/.*IMAGE_PATH: *\([^ ]*\).*/\1/p' | tail -1)
[ -f "$path" ] || path=$(ls -t ~/.cursor/projects/*/assets/"$name".* 2>/dev/null | head -1)
[ -f "$path" ] || { printf '%s\n' "$reply" | tail -5 >&2; exit 1; }
cp "$path" "$output_path"
