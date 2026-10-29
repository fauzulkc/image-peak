---
name: image-peak
description: Turn one text prompt into a full set of delivery images for every screen - an Ultra HDR (gain-map) JPEG with P3 colour for HDR screens, a Display P3 SDR JPEG for wide-gamut screens, and an sRGB SDR JPEG for everyone else - all verified by decoding, plus a ready <picture> snippet and a preview page with a comparison slider. Works with any image generator through any harness - a CLI (Cursor agent, agy, bundled adapters), any executable that follows a four-argument adapter contract, or an agent's own image tool (an MCP image tool, a harness's built-in image generation) via plan/build. Use whenever the user wants HDR images, gain-map or Ultra HDR photos, "full dynamic range", "best colour on every screen", wide-gamut / P3 imagery, images that "adapt to the screen", or a generated hero/card/band image that should not lose highlights (fire, sun, neon, snow, sky), in any project or workflow. Also use to convert existing frames (one image, or a base + darker pair, from any source including a camera) into the three tiers, and to upgrade the images of an existing site or repo - "upgrade our site's images to HDR", "make the photos on this site wide gamut", "audit our images" - with an audit (which images gain, where they are referenced, which build steps would strip the result), tiers at each image's exact original size, and a reviewable <img> to <picture> patch.
---

# image-peak: HDR and P3 images from one prompt, any generator

One prompt in, three verified files out. Image generators only make **8-bit sRGB SDR** (checked:
Cursor/Nano Banana JPEGs have no colour profile, at most 1280 px, nothing above white). The
generator supplies the picture; this skill's code supplies the dynamic range and the gamut:

| Tier | File | Shown to |
|---|---|---|
| HDR + P3 | `<slug>.uhdr.jpg`: detail-kept sRGB base + multichannel gain map | HDR screens (Chromium, Safari 26); the OS scales the lift to the live headroom |
| P3 SDR | `<slug>.p3.jpg`: Display P3 profile | Wide-gamut screens not showing HDR |
| sRGB SDR | `<slug>.sdr.jpg` | Everyone else |

The SDR tiers keep highlight detail (fire stays orange flames, snow keeps texture) instead of the
generator's blown white; the HDR tier lifts those highlights above white.

## What the generator must do (any generator)

Two images of one scene:

1. **base**: the prompt, photographed normally (bright parts may clip).
2. **dark**: an **edit of the saved base** (same framing), about 4 stops darker so the bright parts
   show colour and texture. It must be an edit; two separate generations are two different scenes.

A text-only generator that cannot edit: give it only the base. The build runs in **single-frame mode**
(highlights lifted from the base alone; the SDR tiers are the generator's picture). Less good, still valid.

## Setup (once per machine)

`bash scripts/setup.sh` creates `~/.venvs/image-peak` (numpy, opencv, pillow, imagecodecs with
libultrahdr 2.0.2; no compiling) and reports which generator CLIs are logged in.
Below, `IMAGE_PEAK` means `~/.venvs/image-peak/bin/python -I <skill dir>/scripts/image_peak.py`.
On Windows, set up and run it inside WSL (`wsl bash -lc "..."`, skill dir as a `/mnt/c/...` path);
`--out` then takes a WSL path.

## Route A: a CLI generator (one command)

```bash
IMAGE_PEAK run "<scene prompt>" --slug <name> --out <dir> --generator cursor   # or agy, or /path/to/adapter
```

About 2 to 3 minutes (two generations plus ~20 s of processing); give the Bash call a 600000 ms
timeout. It writes the plan, generates the base, edits it darker, builds and verifies, and
regenerates the dark edit once (stronger) if it recovered too little. Re-runs skip frames that exist.

Bundled adapters (`scripts/generators/`): `cursor` (Cursor Agent CLI, Nano Banana) and `agy`
(Antigravity CLI, generate_image). Their tool rules come from `cursor-image-gen` and
`antigravity-image-gen`: never `--force`; agy runs with normal permissions, so a run where agy reaches
for a shell tool ends without an image (exit 1) and a quota 429 exits 2 (switch generator).

**Any other generator: write an adapter.** Any executable, called as

```text
<adapter> create <prompt_file> <output_path>
<adapter> edit   <prompt_file> <output_path> <input_image>
```

It reads the prompt from `prompt_file`, writes one image (JPEG, PNG or WebP) to `output_path`, and
exits 0. Anything else means failure (the runner retries once). The prompts are generator-neutral;
the adapter adds its own tool wording (see `cursor.sh`, about 20 lines). Pass it as `--generator /path/to/adapter`.

## Route B: an agent's own image tool (MCP, built-in harness tools)

When only the agent can call the generator (an MCP image tool, a harness image tool):

1. `IMAGE_PEAK plan "<scene prompt>" --slug <name> --out <dir>` writes `<dir>/<name>/plan.json` and prints
   `base_prompt`, `base_path`, `dark_prompt`, `dark_prompt_stronger`, `dark_path`.
2. Call the image tool with `base_prompt`; save the image to `base_path` (any of .jpg/.png/.webp).
3. Call the tool **in edit mode on that saved base** with `dark_prompt`; save to `dark_path`.
   No edit mode: skip this step (single-frame mode).
4. `IMAGE_PEAK build --slug <name> --out <dir>`. Exit 3 = the dark edit recovered too little: redo step 3
   with `dark_prompt_stronger`, then build again.

The same route converts frames from anywhere: drop `<name>.base.*` (and optionally `<name>.dark.*`)
into `<dir>/<name>/frames/` and run `build`. Real camera brackets work and give real HDR.

## Route C: upgrade an existing site or repo

Three steps, each safe to stop after. Work files go to `<repo>/.image-peak/` (add it to `.gitignore`).

```bash
IMAGE_PEAK audit   <repo>                        # report only; changes nothing
IMAGE_PEAK upgrade <repo> [--generator cursor]   # tiers next to each original; originals untouched
IMAGE_PEAK rewrite <repo> [--apply]              # <img> to <picture>: a patch, applied only with --apply
```

1. **audit** finds every JPEG, PNG and WebP (skipping `node_modules`, build output and existing tiers),
   finds where the source references each one (HTML/JSX `<img>`, CSS `url()`, Markdown, imports, data
   strings), and scores it. It recommends **skip** for icons under 480 px, images with transparency,
   images that already have a gain map, sources already in a wide-gamut profile (keep the original as
   the P3 file), flat graphics and screenshots (P3 expansion would shift brand colours), and images with
   almost nothing to gain. It also flags **pipeline risks**: anything that re-saves JPEGs and would strip
   the gain map and profile (next/image without `unoptimized`, Astro/Nuxt/Gatsby image pipelines,
   vite-imagetools, imagemin, sharp, optimizer scripts, Cloudflare Polish). Read `audit.md` with the
   owner before upgrading.
2. **upgrade** builds tiers at the image's **exact original size** (`--keep-size`; never cropped, so
   layouts and `width`/`height` stay correct). With `--generator`, the generator **edits the existing
   image** darker (recovered highlight detail, all three tiers, the detail-kept `.sdr.jpg` becomes the
   fallback). Without one it builds single-frame and the original stays the fallback. `--plan-only`
   writes `pending-edits.json` (input image, prompt, stronger prompt, where to save) for an agent's own
   image tool; run upgrade again once the edits are saved. `--images` picks specific files. Each image
   ships only the tiers that earn their bytes: HDR when 0.5%+ of pixels go above white, P3 when 0.5%+
   leave sRGB. A failed or weak generator edit falls back to single-frame, never to a broken file.
3. **rewrite** turns literal `<img src>` references into `<picture>` (`srcSet` and self-closing tags in
   JSX, every original attribute kept) and writes `markup.patch` plus `rewrite.md`: CSS backgrounds
   (with the exact `@media` rules), Markdown, imports and data strings to handle by hand, the pipeline
   risks, and the `dynamic-range-limit` CSS. It skips images already inside a `<picture>`, so re-runs
   change nothing. Review the patch, then `--apply`; commit only when the owner asks.

Fix the pipeline risks before deploying, or the tiers ship stripped. After deploying, fetch one
`.uhdr.jpg` from the live site and check it still holds two images (base + gain map).

## Results

Exit 0 = every check passed; 1 = a check failed (named in the report); 3 = regenerate the dark edit.
`<dir>/<name>/` holds the three tiers, `<name>.report.json`, `<name>.picture.html` (paste-ready),
`preview.html` (slider: generator output vs each tier, the live `<picture>` choice, the report and
checks) and `frames/`. **Serve the folder over HTTP to view `preview.html`**, not `file://`
(a static server, or a `.claude/launch.json` entry running `python3 -m http.server <port>` there).

Checks: alignment (50+ inliers, median under 2 px), the Ultra HDR file holds base + gain map, decoded
HDR peak within 10% of the master, decode error above white under 12%, the file's SDR base matches the
intended one, the P3 file carries Display P3 and leaves sRGB colours alone, and the SDR tier blows out
no more than the generator did.

## How the build works (`scripts/build_tiers.py`)

- Aligns the dark edit to the base (SIFT + RANSAC homography), crops to the shared area (edits reframe).
- **Headroom auto** (`--headroom N` overrides): coloured light sources 8x, small neutral highlights 6x,
  large bright areas 4x, almost nothing clipped 2x; the reason is in the report.
- HDR master: the base everywhere; highlights lifted relative to each pixel's own level, with shape and
  colour from the dark edit where the base clipped.
- SDR base: local tone map (bilateral base/detail split, soft shoulder above 0.7); out-of-range colour
  keeps hue and saturation and gives up level.
- P3: OKLab chroma x1.15 only on already-saturated colour, never neutrals. The profile comes from
  `display_p3_icc.py` (verified against Little CMS: max difference 1 on the 0-255 scale).
- Encodes with libultrahdr via `imagecodecs`, then decodes every file and checks it.

## Deliver

```html
<picture>
  <source media="(dynamic-range: high)" srcset="x.uhdr.jpg">
  <source media="(color-gamut: p3)" srcset="x.p3.jpg">
  <img src="x.sdr.jpg" width="…" height="…" alt="…">
</picture>
```

- Calm HDR in grids, full when opened: `dynamic-range-limit: standard` / `no-limit`.
- Wrong guesses are safe: every tier contains a correct SDR picture.
- **Never re-save these files through a JPEG optimizer**; it drops the gain map and the P3 profile
  (any JPEG optimizer or CDN re-encode can do this; exclude these files from it).
- Prerendered HTML only; no JavaScript source swapping.

## Making generated images better for the web

A generator's file is a starting point, not a web asset: 8-bit sRGB, no colour profile, nothing
above white, highlights clipped. Use the skill to close that gap on purpose:

1. **Prompt for range.** Name a light source or a specular (a filament, low sun on glass, wet
   highlights) and colours near the sRGB edge (ripe fruit, neon, deep teal). Low-key or pastel scenes
   have little to lift; the report will say so.
2. **Edit, never regenerate, for the dark frame.** A second generation is a second scene. If the
   alignment check fails twice, build single-frame rather than tuning the code.
3. **Read the report before shipping a tier.** `pixels above SDR white` and `HDR peak` say whether
   the HDR file earns its extra bytes (it is about 1.8x the SDR file); `P3 SDR pixels outside sRGB`
   says whether the P3 file differs at all. Near zero on both: ship only `<slug>.sdr.jpg`.
4. **Deliver with `<picture>`** (see Deliver), with `width`/`height` set, `dynamic-range-limit:
   standard` in grids and `no-limit` when opened, prerendered, never re-saved by an optimizer.
5. **Show readers without HDR or P3 what they miss.** Put the generator's file beside the
   `<picture>` and mark, from the decoded files, where pixels go above white or outside sRGB. A
   measured map is honest; a brightened SDR copy that imitates HDR is not.
6. **Say what is authored.** Generated highlights and P3 colour are designed, not captured; a caption
   line says so, and HDR display is proven by the decoded numbers until someone checks on an HDR screen.

## Rules and limits

- The host project's image rules still apply (for example: no text or logos unless asked, and
  **get the owner's pick before an image is wired into a page**).
- Highlights and P3 colour from a generator are **authored**, not captured: the "4 stops darker" edit
  is really 0.4 to 2 stops and uneven, so the HDR level is set by headroom. Low-key scenes (dusk, night
  with one lamp) clip little and get little HDR; the report says so. Real camera frames give real HDR.
- Size is the generator's (about 1000 to 1280 px after the crop). For a hero, upscale the frames
  before building, never the finished files.
- libultrahdr fixes the base to sRGB, which is why P3 SDR is a separate file.
- If an edit changes the scene (moved sun, reshaped cloud), expect a colour fringe; regenerate the
  edit rather than tuning the code.
- HDR display is proven by numbers until someone looks on an HDR screen; say which was checked.
