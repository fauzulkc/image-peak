#!/usr/bin/env bash
# image-peak installer for any agent harness or terminal (macOS, Linux, WSL):
#   curl -fsSL https://raw.githubusercontent.com/fauzulkc/image-peak/main/install.sh | bash
# Clones (or updates) the repo, puts an `image-peak` command in ~/.local/bin, and sets up the Python
# environment. Options (after `bash -s --` when piped):
#   --dir DIR          where the repo goes            (default ~/.local/share/image-peak)
#   --link-skill DIR   also link the skill folder into a harness's skills directory, e.g.
#                      --link-skill ~/.claude/skills   (repeatable; the link is DIR/image-peak)
#   --no-setup         skip the environment set-up (it then happens on first use)
set -euo pipefail
repository="https://github.com/fauzulkc/image-peak.git"
directory="$HOME/.local/share/image-peak"
skill_directories=() setup=1
while [ $# -gt 0 ]; do
  case "$1" in
    --dir) directory="$2"; shift 2 ;;
    --link-skill) skill_directories+=("$2"); shift 2 ;;
    --no-setup) setup=0; shift ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
command -v git >/dev/null || { echo "image-peak: git is required" >&2; exit 1; }
command -v python3 >/dev/null || command -v uv >/dev/null || { echo "image-peak: Python 3.10+ (or uv) is required" >&2; exit 1; }

if [ -d "$directory/.git" ]; then
  git -C "$directory" pull --ff-only --quiet && echo "image-peak: updated $directory"
else
  mkdir -p "$(dirname "$directory")" && git clone --quiet --depth 1 "$repository" "$directory" && echo "image-peak: cloned to $directory"
fi
mkdir -p "$HOME/.local/bin"
ln -sf "$directory/scripts/image-peak" "$HOME/.local/bin/image-peak"
echo "image-peak: command at ~/.local/bin/image-peak"
for skills in "${skill_directories[@]+"${skill_directories[@]}"}"; do
  skills="${skills/#\~/$HOME}"
  mkdir -p "$skills" && ln -sfn "$directory" "$skills/image-peak" && echo "image-peak: skill linked at $skills/image-peak"
done
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) echo "image-peak: add ~/.local/bin to PATH (export PATH=\"\$HOME/.local/bin:\$PATH\")" ;; esac
[ "$setup" = 1 ] && bash "$directory/scripts/image-peak" doctor
echo "image-peak: done. Try: image-peak --help"
