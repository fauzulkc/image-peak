# Site upgrade example

`site/` is a small site in its **before** state; `results/` is the recorded output of running true-image
on it. The site has six images, every kind of reference the rewrite handles, and three pipeline risks.

```text
site-upgrade/
├── site/
│   ├── index.html                 <img> for furnace, dashboard, logo
│   ├── src/components/Hero.tsx    JSX <img> for snow
│   ├── src/styles/site.css        CSS background: neon
│   ├── content/post.md            Markdown image: neon
│   ├── src/data/gallery.ts        data string: furnace
│   ├── public/images/             furnace.jpg, snow.jpg, neon.jpg, logo.png (transparent), icon.png (64 px), dashboard.png (flat UI)
│   ├── package.json, next.config.js   Next.js without images.unoptimized  (pipeline risk)
│   ├── scripts/optimize.py        re-saves JPEGs with Pillow                (pipeline risk)
│   └── wrangler.toml              Cloudflare                                (pipeline risk)
└── results/                       audit.md, audit.json, manifest.json, markup.patch, rewrite.md
```

## Run it yourself

From the repo root, on a copy so the example stays in its before state:

```bash
cp -r examples/site-upgrade/site /tmp/site
python3 scripts/true_image.py audit /tmp/site
python3 scripts/true_image.py upgrade /tmp/site
python3 scripts/true_image.py rewrite /tmp/site
cat /tmp/site/.true-image/markup.patch
```

Without a generator, every image builds single-frame, so the furnace keeps its original as the fallback.
The recorded results gave the furnace the generator's dark edit of that picture (from
`examples/glass-furnace/frames/`), so it shipped all three files. To do the same, add
`--generator cursor` to `upgrade`, or copy the edit in before running `upgrade`:

```bash
mkdir -p /tmp/site/.true-image/public-images-furnace/frames
cp examples/glass-furnace/frames/glass-furnace.dark.jpg /tmp/site/.true-image/public-images-furnace/frames/furnace.dark.jpg
```

## What happened

- `audit`: 3 of 6 images recommended (furnace, neon, snow); dashboard skipped as a flat graphic, logo for
  transparency, icon for size; all three pipeline risks found. See [`results/audit.md`](results/audit.md).
- `upgrade`: furnace shipped HDR, P3 and sRGB (peak 7.78×); neon shipped HDR and P3; snow shipped HDR
  only (it has no P3 gain). See [`results/manifest.json`](results/manifest.json).
- `rewrite`: two files patched (HTML and JSX); the CSS background, the Markdown image and the data
  string listed for hand edits with the exact change. See [`results/markup.patch`](results/markup.patch)
  and [`results/rewrite.md`](results/rewrite.md).
