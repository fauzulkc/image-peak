---
name: true-image
description: Turn one text prompt into a full set of delivery images for every screen - an Ultra HDR (gain-map) JPEG with P3 colour for HDR screens, a Display P3 SDR JPEG for wide-gamut screens, and an sRGB SDR JPEG for everyone else - all verified by decoding, plus a ready <picture> snippet and a preview page with a comparison slider. Works with any image generator through any harness - a CLI (Cursor agent, agy, bundled adapters), any executable that follows a four-argument adapter contract, or an agent's own image tool (an MCP image tool, a harness's built-in image generation) via plan/build. Use whenever the user wants HDR images, gain-map or Ultra HDR photos, "full dynamic range", "best colour on every screen", wide-gamut / P3 imagery, images that "adapt to the screen", or a generated hero/card/band image that should keep its highlights (fire, sun, neon, snow, sky), or to post-process an image just made with agy, Cursor, an MCP image tool or any generator, in any project or workflow. Also use to convert existing frames (one image, or a base + darker pair, from any source including a camera) into the three tiers, and to upgrade the images of an existing site or repo - "upgrade our site's images to HDR", "make the photos on this site wide gamut", "audit our images" - with an audit (which images gain, where they are referenced, which build steps would strip the result), tiers at each image's exact original size, and a reviewable <img> to <picture> patch.
---

# true-image: HDR and P3 images from one prompt, any generator

One prompt in, three verified files out. Image generators only make **8-bit sRGB SDR** (checked:
Cursor/Nano Banana JPEGs have no colour profile, at most 1280 px, nothing above white). The
generator supplies the picture; this skill's code supplies the dynamic range and the gamut:

| Tier | File | Shown to |
|---|---|---|
| HDR + P3 | `<slug>.uhdr.jpg`: detail-kept sRGB base + multichannel gain map | HDR screens (Chromium, Safari 26); the OS scales the lift to the live headroom |
| P3 SDR | `<slug>.p3.jpg`: Display P3 profile | Wide-gamut screens showing SDR |
| sRGB SDR | `<slug>.sdr.jpg` | Everyone else |

The SDR tiers keep highlight detail (fire stays orange flames, snow keeps texture) where the
generator blew them to white; the HDR tier lifts those highlights above white.

## What the generator must do (any generator)

Two images of one scene:

1. **base**: the prompt, photographed normally (bright parts may clip).
2. **dark**: an **edit of the saved base** (same framing), about 4 stops darker so the bright parts
   show colour and texture. Editing the saved base keeps one scene in both frames.

A text-only generator gives only the base. The build runs in **single-frame mode** (highlights lifted
from the base alone; the SDR tiers are the generator's picture).

## Running it

Below, `TRUE_IMAGE` means `python3 <base directory of this skill>/scripts/true_image.py` (the folder
that holds this SKILL.md; for a plugin install, the plugin folder). On Windows use `py` or `python`
if `python3` is missing; it runs natively, and inside WSL too. **Setup is automatic:** the first
call creates its own environment in `~/.venvs/true-image` (once, about a minute; numpy, OpenCV, Pillow,
imagecodecs with libultrahdr, all prebuilt wheels), then re-runs the command inside it. It needs Python 3.10+
with `venv`, or `uv`; the error names what to install if neither works. `TRUE_IMAGE doctor` sets up and
reports which generator CLIs it found. Documentation with copy-paste examples: `docs/`, `AGENTS.md`
(the same instructions for other agent harnesses) and https://github.com/fauzulkc/true-image.

## Route A: a CLI generator (one command)

```bash
TRUE_IMAGE run "<scene prompt>" --slug <name> --out <dir> --generator cursor   # or agy, or /path/to/adapter
```

About 2 to 3 minutes (two generations plus ~20 s of processing); give the Bash call a 600000 ms
timeout. It writes the plan, generates the base, edits it darker, builds and verifies, and
regenerates the dark edit once (stronger) if it recovered too little. Re-runs skip frames that exist.

Bundled adapters (`scripts/generators/`): `cursor` (Cursor Agent CLI, Nano Banana) and `agy`
(Antigravity CLI, generate_image). Their tool rules come from `cursor-image-gen` and
`antigravity-image-gen`: Cursor runs with `--trust`; agy runs with its normal permissions and saves through
its own `generate_image`. A run that ends with no image exits 1; a quota 429 exits 2 (switch generator).

**Any other generator: write an adapter.** Any executable, called as

```text
<adapter> create <prompt_file> <output_path>
<adapter> edit   <prompt_file> <output_path> <input_image>
```

It reads the prompt from `prompt_file`, writes one image (JPEG, PNG or WebP) to `output_path`, and
exits 0. Any other exit, or an empty file, counts as a failure, and the runner retries once. The prompts are generator-neutral;
the adapter adds its own tool wording (see `cursor.sh`, about 20 lines). Pass it as `--generator /path/to/adapter`.

## Route B: an agent's own image tool (MCP, built-in harness tools)

When only the agent can call the generator (an MCP image tool, a harness image tool):

1. `TRUE_IMAGE plan "<scene prompt>" --slug <name> --out <dir>` writes `<dir>/<name>/plan.json` and prints
   `base_prompt`, `base_path`, `dark_prompt`, `dark_prompt_stronger`, `dark_path`.
2. Call the image tool with `base_prompt`; save the image to `base_path` (any of .jpg/.png/.webp).
3. Call the tool **in edit mode on that saved base** with `dark_prompt`; save to `dark_path`.
   A text-only tool skips this step (single-frame mode).
4. `TRUE_IMAGE build --slug <name> --out <dir>`. Exit 3 = the dark edit recovered too little: redo step 3
   with `dark_prompt_stronger`, then build again.

The same route converts frames from anywhere: drop `<name>.base.*` (and optionally `<name>.dark.*`)
into `<dir>/<name>/frames/` and run `build`. Real camera brackets work and give real HDR.

## Route B2: post-process an image that already exists

After any generation (agy, Cursor, an MCP image tool, a download), true-image is the next step:

1. `TRUE_IMAGE plan "<what the image shows>" --slug <name> --out <dir>` (prompts and the `frames/` folder).
2. Copy the image to `<dir>/<name>/frames/<name>.base.<ext>`.
3. For recovered detail, make the dark edit of that saved file: `TRUE_IMAGE generate --slug <name> --out
   <dir> --generator agy` (or `cursor`) runs the edit alone, since the base exists; an MCP or harness tool
   edits `base_path` with `dark_prompt` and saves to `dark_path`. Skip it for single-frame.
4. `TRUE_IMAGE build --slug <name> --out <dir>`.

For an image already placed in a page, `audit` then `upgrade --images <path>` keeps its exact size.
Full guide with every generator: `docs/post-process.md`.

## Route C: upgrade an existing site or repo

Three steps, each safe to stop after. Work files go to `<repo>/.true-image/` (add it to `.gitignore`).

```bash
TRUE_IMAGE audit   <repo>                        # report only
TRUE_IMAGE upgrade <repo> [--generator cursor]   # tiers next to each original; originals stay as they are
TRUE_IMAGE rewrite <repo> [--apply]              # <img> to <picture>: a patch; --apply applies it
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
2. **upgrade** builds tiers at the image's **exact original size** (`--keep-size`, uncropped, so
   layouts and `width`/`height` stay correct). With `--generator`, the generator **edits the existing
   image** darker (recovered highlight detail, all three tiers, the detail-kept `.sdr.jpg` becomes the
   fallback). Without one it builds single-frame and the original stays the fallback. `--plan-only`
   writes `pending-edits.json` (input image, prompt, stronger prompt, where to save) for an agent's own
   image tool; run upgrade again once the edits are saved. `--images` picks specific files. Each image
   ships only the tiers that earn their bytes: HDR when 0.5%+ of pixels go above white, P3 when 0.5%+
   leave sRGB. A failed or weak generator edit falls back to single-frame, and every written file passes its checks.
3. **rewrite** turns literal `<img src>` references into `<picture>` (`srcSet` and self-closing tags in
   JSX, every original attribute kept) and writes `markup.patch` plus `rewrite.md`: CSS backgrounds
   (with the exact `@media` rules), Markdown, imports and data strings to handle by hand, the pipeline
   risks, and the `dynamic-range-limit` CSS. It skips images already inside a `<picture>`, so a re-run
   leaves them as they are. Review the patch, then `--apply`; commit only when the owner asks.

Fix the pipeline risks before deploying, so the tiers ship with their gain maps and profiles. After deploying, fetch one
`.uhdr.jpg` from the live site and check it still holds two images (base + gain map).

## Results

Exit 0 = every check passed; 1 = a check failed (named in the report); 3 = regenerate the dark edit.
`<dir>/<name>/` holds the three tiers, `<name>.report.json`, `<name>.picture.html` (paste-ready),
`preview.html` (slider: generator output vs each tier, the live `<picture>` choice, the report and
checks) and `frames/`. **Serve the folder over HTTP to view `preview.html`**
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
- P3: OKLab chroma x1.15 only on already-saturated colour; neutrals keep their values. The profile comes from
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
- Every tier contains a correct SDR picture, so each screen gets a good image.
- **Serve these files byte for byte.** A JPEG optimizer or a CDN re-encode drops the gain map and the
  P3 profile; exclude these files from it.
- Prerender the `<picture>` in HTML; the browser picks the file.

## Making generated images better for the web

A generator's file is a starting point: 8-bit sRGB, untagged, capped at SDR white, highlights
clipped. Use the skill to close that gap on purpose:

1. **Prompt for range.** Name a light source or a specular (a filament, low sun on glass, wet
   highlights) and colours near the sRGB edge (ripe fruit, neon, deep teal). Low-key or pastel scenes
   have little to lift; the report will say so.
2. **Edit the saved base for the dark frame**, so both frames hold one scene. If the alignment check
   fails twice, build single-frame.
3. **Read the report before shipping a tier.** `pixels above SDR white` and `HDR peak` say whether
   the HDR file earns its extra bytes (it is about 1.8x the SDR file); `P3 SDR pixels outside sRGB`
   says whether the P3 file differs at all. Near zero on both: ship only `<slug>.sdr.jpg`.
4. **Deliver with `<picture>`** (see Deliver), with `width`/`height` set, `dynamic-range-limit:
   standard` in grids and `no-limit` when opened, prerendered, served byte for byte.
5. **Show readers without HDR or P3 what they miss.** Put the generator's file beside the
   `<picture>` and mark, from the decoded files, where pixels go above white or outside sRGB. Build
   that map from the decoded files.
6. **Say what is authored.** Generated highlights and P3 colour are designed by the generator; a
   caption line says so, and HDR display is proven by the decoded numbers until someone checks on an HDR screen.

## Rules and limits

- The host project's image rules still apply (for example: no text or logos unless asked, and
  **get the owner's pick before an image is wired into a page**).
- Highlights and P3 colour from a generator are **authored**: the "4 stops darker" edit measures
  0.4 to 2 stops and uneven, so the HDR level is set by headroom. Low-key scenes (dusk, night
  with one lamp) clip little and get little HDR; the report says so. Real camera frames give real HDR.
- Size is the generator's (about 1000 to 1280 px after the crop). For a hero, upscale the frames
  before building.
- libultrahdr fixes the base to sRGB, which is why P3 SDR is a separate file.
- If an edit changes the scene (moved sun, reshaped cloud), expect a colour fringe; regenerate the
  edit.
- HDR display is proven by numbers until someone looks on an HDR screen; say which was checked.
