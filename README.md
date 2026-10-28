# image-peak

A Claude Code skill that turns one text prompt into three verified web images, one for each kind
of screen, using any image generator:

| Tier | File | Shown to |
|---|---|---|
| HDR + P3 | `<slug>.uhdr.jpg`: Ultra HDR, sRGB base + multichannel gain map | HDR screens; the OS scales the lift to the live headroom |
| P3 SDR | `<slug>.p3.jpg`: Display P3 profile | Wide-gamut screens not showing HDR |
| sRGB SDR | `<slug>.sdr.jpg` | Everyone else |

Each run also writes a paste-ready `<picture>` snippet, a JSON report with every check, and a
preview page with a comparison slider (generator output against each tier).

## Why generators need it

Image generators produce 8-bit sRGB SDR: no colour profile, nothing above white, and bright parts
(fire, sun, snow, neon) clipped to flat white. The generator supplies the picture; this skill's code
supplies the dynamic range and the gamut. It asks the generator for two frames of one scene (a normal
base and an edit of that base about 4 stops darker), aligns them, builds an HDR master, and encodes the
three tiers with libultrahdr. Every file is decoded again and checked before the run reports success.
The SDR tiers keep highlight detail instead of the generator's blown white; the HDR tier lifts those
highlights above white.

A generator that cannot edit still works: give it only the base and the build runs in single-frame
mode (highlights lifted from the base alone).

## Install

```bash
git clone git@github.com:fauzulkc/image-peak.git ~/.claude/skills/image-peak
bash ~/.claude/skills/image-peak/scripts/setup.sh
```

`setup.sh` creates `~/.venvs/image-peak` (numpy, opencv, pillow, imagecodecs with libultrahdr; prebuilt
wheels, nothing to compile) and reports which bundled generator CLIs are available. On Windows, run
setup and the commands below inside WSL.

Below, `IMAGE_PEAK` means:

```bash
~/.venvs/image-peak/bin/python -I ~/.claude/skills/image-peak/scripts/image_peak.py
```

## Quick start

**Route A: a CLI generator, one command.**

```bash
IMAGE_PEAK run "a filament bulb glowing at dusk" --slug bulb --out ./images --generator cursor
```

`--generator` takes a bundled adapter (`cursor`, `agy`) or a path to your own. An adapter is any
executable called as `<adapter> create <prompt_file> <output_path>` or
`<adapter> edit <prompt_file> <output_path> <input_image>` that writes one image and exits 0.

**Route B: an agent's own image tool** (an MCP image tool, a harness's built-in generator).

1. `IMAGE_PEAK plan "<scene prompt>" --slug <name> --out <dir>` prints the base and dark prompts and
   where to save each frame.
2. Generate the base and save it to `base_path`.
3. Edit that saved base with `dark_prompt` and save it to `dark_path` (skip if the tool cannot edit).
4. `IMAGE_PEAK build --slug <name> --out <dir>`. Exit 3 means the dark edit recovered too little: redo
   step 3 with `dark_prompt_stronger` and build again.

Existing frames from any source, including camera brackets, go in `<dir>/<name>/frames/` as
`<name>.base.*` (and optionally `<name>.dark.*`) followed by `build`.

Exit codes: 0 every check passed, 1 a check failed (named in the report), 3 regenerate the dark edit.
Serve the output folder over HTTP to view `preview.html`.

## Making generated images better for the web

The full steps are in [SKILL.md](SKILL.md#making-generated-images-better-for-the-web). In short:

1. Prompt for range: name a light source or a specular and colours near the sRGB edge.
2. Make the dark frame an edit of the base, never a second generation.
3. Read the report before shipping a tier. If almost nothing sits above white or outside sRGB, ship
   only the sRGB file.
4. Deliver with `<picture>`, with `width` and `height` set, prerendered, and never re-saved by an optimizer.
5. Show readers without HDR or P3 what they miss with a measured map, not a brightened copy.
6. Say what is authored: generated highlights and P3 colour are designed, not captured.

## Deliver

```html
<picture>
  <source media="(dynamic-range: high)" srcset="x.uhdr.jpg">
  <source media="(color-gamut: p3)" srcset="x.p3.jpg">
  <img src="x.sdr.jpg" width="…" height="…" alt="…">
</picture>
```

Use `dynamic-range-limit: standard` for images in grids and `no-limit` when one is opened. Every tier
contains a correct SDR picture, so a wrong guess by the browser is safe. Keep these files away from
JPEG optimizers and CDN re-encoding: a re-save drops the gain map and the P3 profile.

## Limits

- Highlights and P3 colour from a generator are authored, not captured. A generator's "4 stops darker"
  edit is really much less and uneven, so the HDR level is set by a chosen headroom. Real camera frames
  give real HDR.
- Low-key scenes (dusk, night with one lamp) clip little and get little HDR; the report says so.
- Output size is the generator's. For a large hero, upscale the frames before building, never the
  finished files.
- libultrahdr fixes the base to sRGB, which is why P3 SDR is a separate file.
- If the dark edit changes the scene, expect a colour fringe; regenerate the edit.
- The checks prove the files decode as intended. Whether they look right on an HDR screen is confirmed
  only by looking at one.

## License

MIT. See [LICENSE](LICENSE).
