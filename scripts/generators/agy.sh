#!/usr/bin/env bash
# Adapter: Google Antigravity CLI (agy, built-in generate_image). Contract: agy.sh create|edit <prompt_file> <output_path> [input_image]
# Runs with agy's normal permissions. The prompt forbids shell use; if the model still reaches for a shell
# tool, headless mode denies it and the run ends without an image (exit 1, see antigravity-image-gen).
# A 429 RESOURCE_EXHAUSTED means the image quota is gone for hours: exit 2, use another generator.
set -uo pipefail
mode="$1" prompt_file="$2" output_path="$3" input_image="${4:-}"
name="hdr-$(basename "${output_path%.*}")-$(date +%s)"
if [ "$mode" = edit ]; then
  lead="Use the existing image at $input_image as the input image and edit it with your built-in generate_image tool."
else
  lead="Use your built-in generate_image tool to create the following image."
fi
reply=$(agy -p "Use only your built-in generate_image tool. Do not run any shell command, do not move, copy or convert files. $lead $(cat "$prompt_file") Save the image with name \"$name\". After the tool returns, you MUST end your reply with a single line in this exact format: IMAGE_PATH: <absolute filesystem path to the saved image>" 2>&1)
if printf '%s' "$reply" | grep -q -E '429|RESOURCE_EXHAUSTED'; then echo "agy image quota exhausted (429); use another generator" >&2; exit 2; fi
path=$(printf '%s\n' "$reply" | sed -n 's/.*IMAGE_PATH: *\([^ ]*\).*/\1/p' | tail -1)
[ -f "$path" ] || path=$(printf '%s\n' "$reply" | grep -o -E '/[^ "]+\.(png|jpe?g|webp)' | tail -1)
[ -f "$path" ] || { printf '%s\n' "$reply" | tail -5 >&2; exit 1; }
cp "$path" "$output_path"
