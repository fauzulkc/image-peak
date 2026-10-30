# Changelog

## 1.1.0 (2026-10-30)

- Renamed from image-peak to true-image: the repo (`fauzulkc/true-image`; GitHub redirects the old
  URL), the plugin and marketplace, the skill, the `true-image` command and `scripts/true_image.py`,
  the `TRUE_IMAGE_*` environment variables, the `~/.venvs/true-image` environment and the `.true-image`
  work folder. Reinstall the plugin under its new name.
- Product page: [fauzul.com/true-image](https://fauzul.com/true-image).

## 1.0.1 (2026-10-30)

- Reproducible builds: the sRGB file embeds a fixed sRGB profile built in code (identical conversion to
  Little CMS's own), instead of Pillow's, which stamped the current time. Rebuilding an example no longer
  changes a committed file.

## 1.0.0 (2026-10-29)

- Installable as a Claude Code plugin (`/plugin install image-peak --marketplace fauzulkc/image-peak`),
  as a skill folder, or as a command-line tool.
- No install step from any harness: `scripts/image_peak.py` runs under any Python 3, builds its own
  environment on first use (venv, then uv, then virtualenv) and re-runs inside it. Tested from empty
  environments on Ubuntu and native Windows. `doctor` reports what it found.
- `AGENTS.md` for agent harnesses other than Claude Code; `install.sh` one-line installer with an
  `image-peak` command on `PATH` and optional skill-directory links.
- Custom adapters can be `.py`, `.js`, `.ps1`, `.sh` or any executable.
- `requirements.txt` with tested version ranges.
- Five example scenes and a site-upgrade example with recorded results; measured comparison figures.
- Documentation: getting started, usage, generators, site upgrade, how it works, delivery, results.
- Fix: `audit` no longer skips optimizer scripts in repos whose path contains "image-peak".

## 0.2.0

- Upgrade existing sites and repos: `audit`, `upgrade` (tiers at the original size), `rewrite`
  (`<img>` to `<picture>` patch).
- Adapters put `~/.local/bin` on `PATH`, so generator CLIs resolve from non-login shells.

## 0.1.0

- One prompt to Ultra HDR, Display P3 and sRGB files with any generator: bundled Cursor and agy adapters,
  the adapter contract, and `plan`/`build` for agent-driven tools. Every file decoded and checked.
