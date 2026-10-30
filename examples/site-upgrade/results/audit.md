# true-image audit: site

| Image | Size | Clipped | Saturated | Used in | Recommendation |
|---|---|---|---|---|---|
| `public/images/dashboard.png` | 1200x800 | 43.7% | 14.2% | index.html:9 (img-tag) | **skip**: graphic: flat colour gains nothing from HDR, and P3 expansion would shift brand colours |
| `public/images/furnace.jpg` | 1152x864 | 3.2% | 2.1% | index.html:8 (img-tag), src/data/gallery.ts:1 (string) | **upgrade**: clipped highlights to recover (a generator dark edit recovers detail; single-frame lifts them) |
| `public/images/icon.png` | 64x64 | 0.0% | 100.0% | not referenced | **skip**: small (64 px long side): icon or thumbnail |
| `public/images/logo.png` | 600x200 | 0.0% | 16.9% | index.html:5 (img-tag) | **skip**: uses transparency: gain-map JPEGs have no alpha |
| `public/images/neon.jpg` | 1152x864 | 0.5% | 5.7% | content/post.md:3 (markdown-image), src/styles/site.css:3 (css-url) | **upgrade**: clipped highlights to recover (a generator dark edit recovers detail; single-frame lifts them) |
| `public/images/snow.jpg` | 1152x864 | 2.9% | 0.0% | src/components/Hero.tsx:4 (img-tag) | **upgrade**: clipped highlights to recover (a generator dark edit recovers detail; single-frame lifts them) |

## Pipeline risks (would strip gain maps or colour profiles)

- `package.json`: next: next/image re-encodes images unless images.unoptimized is true. Fix: exclude *.uhdr.jpg and *.p3.jpg from it (or serve them from a path it skips).
- `scripts/optimize.py`: script re-saves images with Pillow. Fix: skip *.uhdr.jpg and *.p3.jpg in it: re-saving drops the gain map and the P3 profile.
- `wrangler config`: Cloudflare: Polish or Image Resizing re-encodes JPEGs if enabled for the zone (not visible in the repo). Fix: keep Polish off for the image paths, or check the served bytes still hold the gain map.
