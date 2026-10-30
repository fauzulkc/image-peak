# Post-processing a generated image

Generate with any tool, then run true-image as the next step. It takes the saved file and returns the
three web files (`NAME.uhdr.jpg`, `NAME.p3.jpg`, `NAME.sdr.jpg`), a `<picture>` snippet and a report.

This works for an image from the agy CLI, the Cursor `agent` CLI, an MCP image tool, a harness's built-in
image generation, a web app download, or a camera.

Below, `true-image` is the command `install.sh` puts on your `PATH`. From a clone it is
`python3 scripts/true_image.py` (`py scripts\true_image.py` on Windows).

## The step after generation

Three commands. `NAME` is a short slug for the image; `DIR` is where its folder goes.

```bash
true-image plan "a glass furnace with molten glass, cobalt and emerald vases" --slug furnace --out ./images
cp ~/Downloads/furnace.png ./images/furnace/frames/furnace.base.png
true-image build --slug furnace --out ./images
```

1. `plan` creates `./images/furnace/frames/`, records the scene in `plan.json`, and prints the prompts
   for the darker edit and where that edit goes (`dark_prompt`, `dark_prompt_stronger`, `dark_path`).
   Describe what the image shows; the report records it.
2. The copy makes your image the base frame. The name is `NAME.base` with the file's own extension
   (`.jpg`, `.jpeg`, `.png` or `.webp`).
3. `build` lifts the highlights into HDR, widens saturated colour into P3, encodes, decodes every file
   and checks it. Exit 0 means every check passed.

With the base alone, the build runs in **single-frame mode**: highlights lift from the one image and the
sRGB file is your original. Add a darker edit before `build` (next section) and the build also recovers
the detail your generator clipped to white: flame structure, snow texture, the colour of a neon tube.

## Add the darker edit for recovered detail

The darker edit is the same picture, edited about 4 stops darker, so the bright parts show colour and
texture. Make it from the saved base with the tool that suits you, then run `build`.

### agy or Cursor, from the command line

```bash
true-image generate --slug furnace --out ./images --generator agy      # or: --generator cursor
true-image build    --slug furnace --out ./images
```

`generate` finds the base you saved and runs only the edit, writing `frames/furnace.dark.jpg`. Cursor
needs a one-time `agent login`.

### agy or Cursor, inside an agent chat

When an agent drives agy or Cursor through its own skill (`antigravity-image-gen`, `cursor-image-gen`):
give it the saved base as the input image and `dark_prompt` from `plan.json` as the prompt, and save the
result to `dark_path`. Then run `build`.

### An MCP image tool or a harness's built-in image tool

1. Call the tool in **edit mode** with the input image set to `base_path` and the prompt set to
   `dark_prompt`.
2. Save the result to `dark_path`. A tool that returns a URL or base64 data: write those bytes to
   `dark_path` (`.jpg`, `.png` or `.webp`).
3. Run `build`.

### A web app with image editing

Upload the base, paste `dark_prompt`, and download the result as `frames/NAME.dark.png` (or `.jpg`,
`.webp`). Then run `build`.

### Exit 3: a stronger edit

Exit 3 means the edit recovered too little. Make it again with `dark_prompt_stronger`, then build:

```bash
true-image generate --slug furnace --out ./images --generator agy --stronger
true-image build    --slug furnace --out ./images
```

With an MCP or web tool, repeat its edit step with `dark_prompt_stronger` and overwrite `dark_path`.

## An image already placed in a page

`build` crops to the area the base and the edit share, since edits often reframe slightly. For an image
whose size is already set in a layout, `upgrade` keeps its exact size and writes the files beside it:

```bash
true-image audit   ./my-site
true-image upgrade ./my-site --images public/images/hero.jpg --generator agy
true-image rewrite ./my-site
```

`--images` takes paths as `audit.md` lists them, relative to the folder you passed. Leave out
`--generator` for single-frame. `rewrite` writes `<img>` to `<picture>` as a patch; `--apply` applies it.
Full walkthrough: [Upgrading a site](site-upgrade.md).

## Make it the standing step after every generation

Put the instruction where your agent reads its rules (`CLAUDE.md`, `AGENTS.md`, `.cursor/rules`,
`GEMINI.md`), so every generated image arrives as the three files:

```markdown
## Generated images

After generating an image for this project, post-process it with true-image before using it:

1. `true-image plan "<what the image shows>" --slug <name> --out <images dir>`
2. Save the image as `<images dir>/<name>/frames/<name>.base.<ext>`.
3. Edit that saved image about 4 stops darker with the same tool, using `dark_prompt` from `plan.json`,
   and save it to `dark_path`. `--generator agy` or `--generator cursor` with `true-image generate` does
   this from the command line.
4. `true-image build --slug <name> --out <images dir>`. On exit 3, redo step 3 with
   `dark_prompt_stronger`.
5. Use `<name>.picture.html` in the page and serve the three files byte for byte.
```

For terminal workflows, a shell function wraps the same steps:

```bash
# true_image_after IMAGE NAME OUT_DIR "SCENE" [GENERATOR]
true_image_after() {
  local image="$1" name="$2" out_dir="$3" scene="$4" generator="${5:-}"
  true-image plan "$scene" --slug "$name" --out "$out_dir" > /dev/null
  cp "$image" "$out_dir/$name/frames/$name.base.${image##*.}"
  if [ -n "$generator" ]; then
    true-image generate --slug "$name" --out "$out_dir" --generator "$generator"
  fi
  true-image build --slug "$name" --out "$out_dir"
}
```

```bash
true_image_after ~/Downloads/furnace.png furnace ./images "a glass furnace with molten glass" agy
```

## What you get

`DIR/NAME/` holds the three files, `NAME.picture.html`, `NAME.report.json` and `preview.html` (a slider
comparing your original with each file). Serve the folder over HTTP to open the preview:

```bash
python3 -m http.server 8000 --directory ./images
```

Read the report before shipping: `pixels above SDR white` near 0% means ship without the HDR file, and
`P3 SDR pixels outside sRGB` near 0% means ship without the P3 file. Delivery details:
[Delivery](delivery.md).
