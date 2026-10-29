# true-image: instructions for any agent

This file is for coding agents in any harness (Claude Code, Codex, Cursor, Gemini CLI, Windsurf, Aider,
or your own). It says everything an agent needs to run true-image without a human installing anything.
Claude Code users get the same content as a skill from [SKILL.md](SKILL.md).

## What it does

Turns a text prompt, an existing image, or a whole site's images into three verified web files:
`NAME.uhdr.jpg` (Ultra HDR gain map, HDR + P3 on HDR screens), `NAME.p3.jpg` (Display P3 SDR) and
`NAME.sdr.jpg` (sRGB SDR, highlight detail kept), plus a `<picture>` snippet and a report.

## How to run it

One command, from any shell, any OS:

```bash
python3 <repo>/scripts/true_image.py <command> [arguments]
```

On Windows without `python3`, use `py` or `python`. If it was installed with `install.sh`, `true-image`
is on `PATH` and equals the command above.

**There is no install step.** The first call creates its own environment in `~/.venvs/true-image`
(about a minute, once), installs its pinned libraries there, and re-runs your command inside it. Later
calls hand over straight away. Requirements: Python 3.10+ with `venv`, or `uv`. If neither works, the
error says exactly what to install. `python3 <repo>/scripts/true_image.py doctor` sets up and reports.

## Choose the route

| The user wants | Run |
|---|---|
| New images from a prompt, and a generator CLI is available (Cursor `agent`, `agy`, or an adapter) | `true_image.py run "<prompt>" --slug NAME --out DIR --generator cursor` |
| New images, and **you** call the image generator (an MCP tool, your harness's built-in image tool) | `plan`, generate two images yourself, `build` (below) |
| Their own photo or frames turned into the three files | put them in `DIR/NAME/frames/` as `NAME.base.*` (and `NAME.dark.*`), then `build` |
| An existing site's images upgraded | `audit REPO`, then `upgrade REPO`, then `rewrite REPO` |

### You call the generator yourself

1. `python3 scripts/true_image.py plan "<prompt>" --slug NAME --out DIR` prints JSON with `base_prompt`,
   `base_path`, `dark_prompt`, `dark_prompt_stronger`, `dark_path`.
2. Generate an image with `base_prompt`; save it to `base_path` (.jpg, .png or .webp).
3. **Edit that saved image** (not a new generation) with `dark_prompt`; save it to `dark_path`. If your
   tool cannot edit images, skip this step: the build runs in single-frame mode.
4. `python3 scripts/true_image.py build --slug NAME --out DIR`. Exit 3 means the edit recovered too
   little or changed the scene: redo step 3 with `dark_prompt_stronger`, then build again.

### Existing site or repo

1. `audit REPO`: read `REPO/.true-image/audit.md` and show the user what it recommends and the pipeline
   risks (build steps that would strip the files). It changes nothing.
2. `upgrade REPO [--generator NAME | --plan-only] [--images PATH ...]`: writes new files beside each
   original at its exact size; never modifies originals. With `--plan-only`, make the edits listed in
   `REPO/.true-image/pending-edits.json` with your image tool, then run `upgrade` again.
3. `rewrite REPO`: writes `REPO/.true-image/markup.patch` and `rewrite.md`. Show the patch; run
   `rewrite REPO --apply` only after the user agrees. Then do the hand edits in `rewrite.md` and fix
   the pipeline risks.

## Results and exit codes

- 0: every check passed. 1: a check failed (named in the report and on stderr) or a generator produced
  nothing twice. 3: regenerate the dark edit.
- Read `DIR/NAME/NAME.report.json` before shipping. If `pixels above SDR white` is near 0%, drop the HDR
  file; if `P3 SDR pixels outside sRGB` is near 0%, drop the P3 file. (`upgrade` does this for you.)
- `DIR/NAME/preview.html` compares the files; serve the folder over http to view it.

## Rules

- Never re-save the output files with an image optimizer or a CDN that re-encodes JPEGs: it strips the
  gain map and the P3 profile. `audit` lists such steps in a repo.
- Generated highlights and P3 colour are authored, not captured; say so where it matters.
- The bundled `cursor` and `agy` adapters need bash (macOS, Linux, WSL, Git Bash). Your own adapter can be
  `.py`, `.js`, `.ps1`, `.sh` or any executable: see [docs/generators.md](docs/generators.md).
- Follow the project's own rules about images (for example, get the owner's pick before wiring an image
  into a page).

Full documentation: [README](README.md) and [docs/](docs/).
