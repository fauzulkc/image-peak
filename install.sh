#!/usr/bin/env bash
# true-image installer for any agent harness or terminal (macOS, Linux, WSL):
#   curl -fsSL https://raw.githubusercontent.com/fauzulkc/true-image/main/install.sh | bash
# Clones (or updates) the repo, puts an `true-image` command in ~/.local/bin, and sets up the Python
# environment. Options (after `bash -s --` when piped):
#   --dir DIR          where the repo goes            (default ~/.local/share/true-image)
#   --link-skill DIR   also link the skill folder into a harness's skills directory, e.g.
#                      --link-skill ~/.claude/skills   (repeatable; the link is DIR/true-image)
#   --no-setup         skip the environment set-up (it then happens on first use)
set -euo pipefail
repository="https://github.com/fauzulkc/true-image.git"
directory="$HOME/.local/share/true-image"
skill_directories=() setup=1
while [ $# -gt 0 ]; do
  case "$1" in
    --dir) directory="$2"; shift 2 ;;
    --link-skill) skill_directories+=("$2"); shift 2 ;;
    --no-setup) setup=0; shift ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
command -v git >/dev/null || { echo "true-image: git is required" >&2; exit 1; }
command -v python3 >/dev/null || command -v uv >/dev/null || { echo "true-image: Python 3.10+ (or uv) is required" >&2; exit 1; }

if [ -d "$directory/.git" ]; then
  git -C "$directory" pull --ff-only --quiet && echo "true-image: updated $directory"
else
  mkdir -p "$(dirname "$directory")" && git clone --quiet --depth 1 "$repository" "$directory" && echo "true-image: cloned to $directory"
fi
mkdir -p "$HOME/.local/bin"
ln -sf "$directory/scripts/true-image" "$HOME/.local/bin/true-image"
echo "true-image: command at ~/.local/bin/true-image"
for skills in "${skill_directories[@]+"${skill_directories[@]}"}"; do
  skills="${skills/#\~/$HOME}"
  mkdir -p "$skills" && ln -sfn "$directory" "$skills/true-image" && echo "true-image: skill linked at $skills/true-image"
done
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) echo "true-image: add ~/.local/bin to PATH (export PATH=\"\$HOME/.local/bin:\$PATH\")" ;; esac
[ "$setup" = 1 ] && bash "$directory/scripts/true-image" doctor
echo "true-image: done. Try: true-image --help"
