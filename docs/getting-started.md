# Getting started

## Requirements

- Python 3.10 or later with the `venv` module, or `uv`. Nothing else to install: the first run sets up
  its own environment. Works on macOS, Linux, WSL and native Windows.
- bash only for the two bundled generator adapters (macOS, Linux, WSL, Git Bash).
- Optional: an image generator. The bundled adapters drive Cursor's `agent` CLI and Google Antigravity's
  `agy` CLI. Any other generator works through an adapter or through an agent (see [generators](generators.md)).
  Without one you can still rebuild the examples, convert your own images, and upgrade a site.

## Install

Pick one route.

### Claude Code plugin

```text
/plugin install image-peak --marketplace fauzulkc/image-peak
```

On Claude Code before 2.1.275:

```text
/plugin marketplace add fauzulkc/image-peak
/plugin install image-peak@image-peak
```

From a shell:

```bash
claude plugin marketplace add fauzulkc/image-peak && claude plugin install image-peak@image-peak
```

The skill then appears as `image-peak` (namespaced under the plugin). Update later with
`/plugin marketplace update image-peak`.

### Skill folder

```bash
git clone https://github.com/fauzulkc/image-peak.git ~/.claude/skills/image-peak
```

Update with `git -C ~/.claude/skills/image-peak pull`.

### Command line only

```bash
git clone https://github.com/fauzulkc/image-peak.git && cd image-peak
```

Install through one Claude Code route only; with both, the skill is listed twice.

### Any other agent harness, or a terminal

```bash
curl -fsSL https://raw.githubusercontent.com/fauzulkc/image-peak/main/install.sh | bash
```

It clones the repo to `~/.local/share/image-peak`, puts an `image-peak` command in `~/.local/bin`, and
sets up the environment. To also link the skill folder into a harness's skills directory:

```bash
curl -fsSL https://raw.githubusercontent.com/fauzulkc/image-peak/main/install.sh | bash -s -- --link-skill ~/.claude/skills
```

Agents that read `AGENTS.md` (Codex, Cursor, Gemini CLI and others) find their instructions in
[AGENTS.md](../AGENTS.md). On Windows without WSL, use the "Command line only" route and `py` in place of
`python3`; everything except the two bash adapters runs natively.

## First run

There is no install step. The first call of any command creates the Python environment, installs the
pinned libraries into it, and re-runs the command inside it. To do that up front and see what it found:

```bash
python3 scripts/image_peak.py doctor
```

```text
image-peak: first run: setting up ~/.venvs/image-peak (about a minute, once)
image-peak: ready
python       3.12.3 at ~/.venvs/image-peak/bin/python
libraries    numpy 2.5.4, opencv 5.0.0, pillow 13.0.0, imagecodecs 2026.10.10 (libultrahdr 2.0.2)
bash         /usr/bin/bash
generator    cursor  found at ~/.local/bin/agent
generator    agy     found at ~/.local/bin/agy
status       ready
```

Tested from an empty environment on Ubuntu (Python 3.12) and on native Windows (Python 3.13). Later
calls hand over straight away. The environment lives in `~/.venvs/image-peak`; set `IMAGE_PEAK_VENV` to
put it elsewhere. Setup tries Python's `venv` module first, then `uv` (which can also fetch a newer
Python), then `virtualenv`.

## A first result without a generator

```bash
python3 scripts/image_peak.py build --slug glass-furnace --out examples
python3 -m http.server 8000 --directory examples
```

Open <http://localhost:8000/glass-furnace/preview.html>: a slider compares the generator's picture with
each delivered file, below it the `<picture>` element shows which file your screen picked, and the
report lists every number and check. Previews need `http://`; opened as `file://`, the browser blocks the
files they load.

## A first result with a generator

```bash
python3 scripts/image_peak.py run "a copper kettle steaming on a gas flame in a dark kitchen" --slug kettle --out ./images --generator cursor
```

Two generator calls (about a minute each), then about 20 seconds of processing. The files land in
`./images/kettle/`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `could not create ~/.venvs/image-peak` | Install the venv module: `sudo apt install python3-venv` (Debian, Ubuntu) |
| `the environment was set up but the image libraries still do not import` | Delete `~/.venvs/image-peak` and run again |
| `could not create a Python 3.10+ environment` | Install Python 3.10+ with venv, or `uv` (`curl -LsSf https://astral.sh/uv/install.sh \| sh`) |
| `the generator did not produce …` | Check the generator is logged in (`agent status` for Cursor). agy exits on a quota error (429): switch generator |
| Exit 3 from `build` | The dark edit recovered too little. `run` retries once with a stronger prompt; by hand, regenerate the edit with `dark_prompt_stronger` from `plan.json` |
| Exit 1 from `build` | A check failed; the report's `checks` names it. Usually the edit changed the scene: regenerate the edit |
| The preview shows no difference | Your screen is SDR and sRGB. The HDR and P3 files only differ on screens that can show them |
| HDR looks flat on the live site | Something re-encoded the file. Run `audit` on the site repo and see [delivery](delivery.md) |
