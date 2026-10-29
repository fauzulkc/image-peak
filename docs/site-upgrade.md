# Upgrading an existing site or repo

Three commands, each safe to stop after. Work files go to `REPO/.true-image/`.

```bash
python3 scripts/true_image.py audit   ./my-site
python3 scripts/true_image.py upgrade ./my-site --generator cursor
python3 scripts/true_image.py rewrite ./my-site
```

A complete worked example, with the recorded output of each step, is in
[`examples/site-upgrade`](../examples/site-upgrade).

## 1. audit: what gains, where it is used, what would break it

`audit` finds every JPEG, PNG and WebP (skipping `node_modules`, build output and files true-image made)
and every place the source refers to each one: HTML and JSX `<img>`, CSS `url()`, Markdown images,
imports, and strings in data files. It then scores each image.

| Recommendation | When |
|---|---|
| skip | Long side under 480 px (icons, thumbnails) |
| skip | Uses transparency (gain-map JPEGs have no alpha) |
| skip | Already has a gain map |
| skip | Already in a wide-gamut profile (keep the original as the P3 file) |
| skip | A flat graphic or screenshot (P3 expansion would shift brand colours; HDR adds nothing) |
| skip | Under 0.3% clipped highlights and under 3% saturated colour (nothing to gain) |
| upgrade | Clipped highlights to recover, or saturated colour for the P3 file |

It also lists **pipeline risks**: build steps that re-save JPEGs and would strip the gain map and the P3
profile. It looks for `next` without `images.unoptimized: true`, Astro, Nuxt and Gatsby image pipelines,
vite-imagetools, the Vite image optimizer, imagemin, sharp, squoosh, eleventy-img, optimizer scripts
(Pillow `.save(… quality …)`, `sharp(`, jpegoptim, mozjpeg, cwebp and similar), and a Cloudflare
`wrangler` config (Polish and Image Resizing are zone settings the repo cannot show).

From the example:

| Image | Clipped | Saturated | Used in | Recommendation |
|---|---|---|---|---|
| `dashboard.png` | 43.7% | 14.2% | `index.html` (img) | skip: graphic |
| `furnace.jpg` | 3.2% | 2.1% | `index.html` (img), `gallery.ts` (string) | upgrade |
| `icon.png` | 0.0% | 100.0% | not referenced | skip: small |
| `logo.png` | 0.0% | 16.9% | `index.html` (img) | skip: transparency |
| `neon.jpg` | 0.5% | 5.7% | `post.md` (markdown), `site.css` (css-url) | upgrade |
| `snow.jpg` | 2.9% | 0.0% | `Hero.tsx` (img) | upgrade |

"Clipped" is the share of pixels with any channel at 250 or above, measured on a downscaled copy.

Read `audit.md` before upgrading; skip anything the owner wants left alone with `--images`.

## 2. upgrade: new files beside each original

```bash
python3 scripts/true_image.py upgrade ./my-site                              # every recommended image
python3 scripts/true_image.py upgrade ./my-site --images public/hero.jpg     # chosen images
python3 scripts/true_image.py upgrade ./my-site --generator cursor           # with a generator dark edit
python3 scripts/true_image.py upgrade ./my-site --plan-only                  # dark edits by an agent's tool
```

- Files keep the original's **exact size**, so `width`, `height` and layouts stay right.
- Originals are never modified or deleted.
- With a generator, the generator edits each original darker and the files get recovered highlight
  detail; the new `name.sdr.jpg` becomes the fallback. Without one, single-frame mode lifts the
  highlights and the original stays the fallback.
- `--plan-only` writes `pending-edits.json`: for each image, the input file, the prompt, a stronger
  prompt and where to save the edit. Save the edits, then run `upgrade` again.
- Each image ships only the files that earn their bytes: the HDR file when at least 0.5% of pixels go
  above white, the P3 file when at least 0.5% of colour falls outside sRGB. Nothing earned: nothing is
  written.
- A failed or weak generator edit falls back to single-frame.

From the example: the furnace had a generator edit and shipped all three files (peak 7.78×, 2.9% above
white, 4.9% outside sRGB); the neon alley shipped HDR and P3 (single-frame, 7.0% outside sRGB); the snow
shipped HDR only (6.9% above white, 0.0% outside sRGB, so no P3 file).

## 3. rewrite: `<img>` to `<picture>`

`rewrite` changes literal `<img src>` references to upgraded images into `<picture>` elements, keeping
every attribute, with `srcSet` and self-closing tags in JSX. It writes `markup.patch` and `rewrite.md`
and edits files only with `--apply`. Images already inside a `<picture>` are left alone, so a second run
changes nothing.

From the example's `markup.patch`:

```diff
-    <img src="/images/furnace.jpg" alt="A glass furnace" width="1152" height="864" class="hero">
+    <picture>
+      <source media="(dynamic-range: high)" srcset="/images/furnace.uhdr.jpg">
+      <source media="(color-gamut: p3)" srcset="/images/furnace.p3.jpg">
+      <img src="/images/furnace.sdr.jpg" alt="A glass furnace" width="1152" height="864" class="hero">
+    </picture>
```

```diff
-      <img className="hero-image" src="/images/snow.jpg" alt="Alpine snow" width={1152} height={864} />
+      <picture>
+        <source media="(dynamic-range: high)" srcSet="/images/snow.uhdr.jpg" />
+        <img className="hero-image" src="/images/snow.jpg" alt="Alpine snow" width={1152} height={864} />
+      </picture>
```

`rewrite.md` lists what to change by hand, with the exact change:

- **CSS backgrounds**: add `@media (color-gamut: p3)` and `@media (dynamic-range: high)` rules that swap
  `background-image` for the same selector.
- **Markdown images**: replace with the `<picture>` block if the renderer allows raw HTML.
- **Imports and data strings**: render with `<picture>` in the component that outputs them.

## 4. Before deploying

Fix every pipeline risk from the audit, or the files ship stripped. After deploying, fetch one HDR file
from the live site and check it still holds two images (base and gain map), for example:

```bash
curl -s https://example.com/images/furnace.uhdr.jpg -o /tmp/check.jpg && python3 -c "from PIL import Image; print(getattr(Image.open('/tmp/check.jpg'), 'n_frames', 1))"
```

`2` means the gain map survived. `1` means something re-encoded the file.
