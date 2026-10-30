# Generators

true-image needs two images of one scene from a generator:

1. **base**: the prompt, photographed normally. Bright parts may clip.
2. **dark**: an **edit of the saved base**, about 4 stops darker, so the bright parts show colour and
   texture. Editing the saved base keeps one scene in both frames, which the alignment check confirms.

A text-only generator gives only the base; the build then runs in single-frame mode.

Already generated an image? [Post-processing](post-process.md) takes it from there.

There are three ways to connect a generator.

## 1. Bundled adapters

```bash
python3 scripts/true_image.py run "<prompt>" --slug NAME --out DIR --generator cursor
python3 scripts/true_image.py run "<prompt>" --slug NAME --out DIR --generator agy
```

| Adapter | Drives | Notes |
|---|---|---|
| `cursor` | Cursor's `agent` CLI (its built-in image tool) | Log in once with `agent login`. Runs from `~/cursor-images` with `--trust` |
| `agy` | Google Antigravity's `agy` CLI (built-in `generate_image`) | Runs with agy's normal permissions and saves through `generate_image`. A quota error (HTTP 429) exits 2: switch generator |

Both add `~/.local/bin` to `PATH` themselves, so they work from tools that start non-login shells.

## 2. Your own adapter

An adapter is any executable called in one of two ways:

```text
<adapter> create <prompt_file> <output_path>
<adapter> edit   <prompt_file> <output_path> <input_image>
```

It reads the prompt from `prompt_file`, writes one JPEG, PNG or WebP image to `output_path`, and exits 0.
Any other exit code, or an empty output, counts as a failure (the runner retries once). The prompts are
generator-neutral ("Edit the input image. …"); add your tool's own wording in the adapter.

A template (`my-generator` stands for your tool's command):

```bash
#!/usr/bin/env bash
set -euo pipefail
mode="$1" prompt_file="$2" output_path="$3" input_image="${4:-}"
prompt="$(cat "$prompt_file")"
if [ "$mode" = edit ]; then
  my-generator edit --image "$input_image" --prompt "$prompt" --out "$output_path"
else
  my-generator create --prompt "$prompt" --out "$output_path"
fi
test -s "$output_path"
```

```bash
python3 scripts/true_image.py run "<prompt>" --slug NAME --out DIR --generator ./my-adapter.sh
```

The bundled [`cursor.sh`](../scripts/generators/cursor.sh) and [`agy.sh`](../scripts/generators/agy.sh)
are about 20 lines each and show how to drive an agent-style CLI that prints the saved path.

## 3. A generator only an agent can call

Some generators are tools inside an agent (an MCP image tool, a harness's built-in image generation).
The agent runs the steps:

```bash
python3 scripts/true_image.py plan "<prompt>" --slug NAME --out DIR
```

`plan` prints JSON with `base_prompt`, `base_path`, `dark_prompt`, `dark_prompt_stronger` and
`dark_path`. The agent then:

1. calls its image tool with `base_prompt` and saves the result to `base_path` (`.jpg`, `.png` or `.webp`);
2. calls the tool in edit mode on that saved file with `dark_prompt` and saves to `dark_path`
   (a text-only tool skips this step);
3. runs `python3 scripts/true_image.py build --slug NAME --out DIR`. On exit 3 it redoes step 2 with
   `dark_prompt_stronger`.

Inside Claude Code the skill does this on its own when you ask for images and name the tool to use.

## Prompting for range

- Name a light source or a specular: a filament, a flame, low sun on glass, wet highlights.
- Name colours near the edge of sRGB: ripe fruit, neon, deep teal, saturated flowers.
- Low-key or pastel scenes have little to lift; the report says so, and you can ship the sRGB file alone.
