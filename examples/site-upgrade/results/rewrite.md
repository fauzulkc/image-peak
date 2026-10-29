# image-peak rewrite: site

Patch only (not applied): 2 files with <img> to <picture> changes. Patch: `site/.image-peak/markup.patch`.

## Handle by hand

- `src/data/gallery.ts:1` (string, `/images/furnace.jpg`): this is data: render it with <picture> in the component that outputs it, deriving the tier names from the base name
- `content/post.md:3` (markdown-image, `/images/neon.jpg`): replace with the <picture> block from the image's preview folder (raw HTML) if the renderer allows it
- `src/styles/site.css:3` (css-url, `/images/neon.jpg`): add `@media (color-gamut: p3) { <same selector> { background-image: url(…/neon.p3.jpg) } }` and the same under `(dynamic-range: high)` with `neon.uhdr.jpg`

## Pipeline risks

- `package.json`: next: next/image re-encodes images unless images.unoptimized is true. Fix: exclude *.uhdr.jpg and *.p3.jpg from it (or serve them from a path it skips).
- `scripts/optimize.py`: script re-saves images with Pillow. Fix: skip *.uhdr.jpg and *.p3.jpg in it: re-saving drops the gain map and the P3 profile.
- `wrangler config`: Cloudflare: Polish or Image Resizing re-encodes JPEGs if enabled for the zone (not visible in the repo). Fix: keep Polish off for the image paths, or check the served bytes still hold the gain map.

## CSS to add once

```css
img { dynamic-range-limit: standard; }          /* calm HDR in grids and body copy */
.lightbox img, .hero img { dynamic-range-limit: no-limit; }  /* full HDR where an image is the point */
```
