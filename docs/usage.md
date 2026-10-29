# Usage

Run every command as `python3 scripts/image_peak.py <command> …` from the repo, or with the full path to
`scripts/image_peak.py` from anywhere. Paths in `--out` and `REPO` can be relative.

## New images from a prompt

| Command | Does |
|---|---|
| `plan "<prompt>" --slug NAME --out DIR [--no-people] [--aspect 3:2]` | Writes `DIR/NAME/plan.json` and prints the base prompt, the dark-edit prompt, a stronger dark-edit prompt, and where each image goes |
| `generate --slug NAME --out DIR --generator ADAPTER [--stronger]` | Runs the adapter for each missing image (after `plan`) |
| `build --slug NAME --out DIR [--headroom auto\|N]` | Builds and verifies the three files from whatever images are in `DIR/NAME/frames/` |
| `run "<prompt>" --slug NAME --out DIR --generator ADAPTER [--headroom auto\|N] [--no-people] [--aspect 3:2]` | `plan` + `generate` + `build`; regenerates a weak dark edit once with the stronger prompt |

- `--generator` takes `cursor`, `agy`, or the path to your own adapter ([generators](generators.md)).
- `--headroom auto` picks the HDR peak from what the highlights are; a number sets it (in multiples of SDR
  white, for example `4`).
- `--no-people` adds "No people." to the prompts. Every prompt already asks for no text, logos or watermarks.
- `--aspect` is passed to the generator as "Landscape 3:2" and so on.

### Frames

`build` reads `DIR/NAME/frames/NAME.base.{jpg,png,webp}` and, if present, `NAME.dark.{jpg,png,webp}`.
With no dark image it runs in single-frame mode. Put any images there, including camera brackets, and
run `build`.

### Output: `DIR/NAME/`

| File | Contents |
|---|---|
| `NAME.uhdr.jpg` | Ultra HDR JPEG (sRGB base + multichannel gain map) |
| `NAME.p3.jpg` | SDR in Display P3 |
| `NAME.sdr.jpg` | SDR in sRGB, highlight detail kept |
| `NAME.generator-base.jpg` | The generator's picture, cropped like the others (for comparison) |
| `NAME.picture.html` | The `<picture>` element with `width`, `height`, `alt` |
| `NAME.report.json` | Every measurement and check |
| `preview.html` | Comparison slider, the live `<picture>` choice, the report |
| `plan.json`, `frames/` | Prompts and the generator's images |

The files are cropped to the area both generator images share (edits often reframe slightly). To keep an
image's exact size, use the site-upgrade commands below, which never crop.

### Report fields worth reading

| Field | Meaning |
|---|---|
| `HDR peak in file` | Brightest highlight in the decoded HDR file, as a multiple of SDR white (99.95th percentile) |
| `pixels above SDR white` | Share of the picture the HDR file lifts. Near 0%: the HDR file is not worth its bytes |
| `P3 SDR pixels outside sRGB` | Share of colour only a P3 screen shows. Near 0%: the P3 file adds nothing |
| `blown to white: generator base -> SDR tier` | Pixels clipped to white before and after; the sRGB file should never be worse |
| `headroom`, `headroom reason` | The peak chosen and why |
| `dark edit, measured gap` | How much darker the edit really was (generators rarely give the stops asked for) |
| `checks` | The 8 checks, each true or false |

## Existing sites and repos

| Command | Does |
|---|---|
| `audit REPO [--work DIR]` | Finds images and their references, scores each, lists pipeline risks. Writes `audit.md` and `audit.json`. Changes nothing |
| `upgrade REPO [--work DIR] [--images PATH …] [--generator ADAPTER \| --plan-only] [--headroom auto\|N]` | Builds the files beside each original, at its exact size |
| `rewrite REPO [--work DIR] [--apply]` | Writes `markup.patch` and `rewrite.md`; `--apply` also edits the files |

`--work` defaults to `REPO/.image-peak` (add it to `.gitignore`). `--images` takes paths relative to
`REPO`, as `audit.md` lists them. Full walkthrough: [site-upgrade](site-upgrade.md).

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Every check passed |
| 1 | A check failed (named in the report and on stderr), or a generator produced nothing twice |
| 3 | `build`: the dark edit recovered too little or shows a different scene; regenerate it (`run` and `upgrade` do this once automatically, then `upgrade` falls back to single-frame) |
