# Delivery

## The markup

```html
<picture>
  <source media="(dynamic-range: high)" srcset="name.uhdr.jpg">
  <source media="(color-gamut: p3)" srcset="name.p3.jpg">
  <img src="name.sdr.jpg" width="1048" height="712" alt="…" loading="lazy" decoding="async">
</picture>
```

Each run writes this as `name.picture.html` with the real `width`, `height` and `alt`. In JSX, the
attribute is `srcSet` and `<source>` closes itself (`rewrite` does this for you).

The browser picks before it downloads anything, so each visitor fetches one file:

| Screen | Gets |
|---|---|
| HDR (reports `dynamic-range: high`) | `name.uhdr.jpg`. Browsers that apply gain maps lift the highlights; the OS scales the lift to the screen's headroom at that moment. Browsers that do not apply them show its sRGB base |
| Wide gamut, not in HDR | `name.p3.jpg` |
| Everything else | `name.sdr.jpg` |

Every file holds a correct SDR picture, so a wrong guess still shows a good image. Browser support for
gain maps and `dynamic-range-limit` is moving; the current state, with sources, is in
[The colour you mostly won't see](https://fauzul.com/blog/colour-you-mostly-wont-see).

Skip a file when it earns nothing: if the report shows almost no `pixels above SDR white`, leave out the
HDR `<source>`; if almost no `P3 SDR pixels outside sRGB`, leave out the P3 one. (`upgrade` and
`rewrite` do this by the 0.5% rule.)

## Keeping HDR calm

```css
img { dynamic-range-limit: standard; }          /* HDR held to SDR white in grids and body copy */
.hero img, .lightbox img { dynamic-range-limit: no-limit; }   /* full HDR where the image is the point */
```

## Keeping the files intact

The gain map and the P3 profile live in the JPEG's metadata and a second embedded image. Anything that
decodes and re-encodes the file drops them, and the HDR and P3 files silently become ordinary SDR.

- Exclude `*.uhdr.jpg` and `*.p3.jpg` from image optimizers and build-time image pipelines
  (next/image without `unoptimized`, Astro, Nuxt and Gatsby image components, vite-imagetools, imagemin,
  sharp, squoosh, custom scripts). `audit` lists the ones in a repo.
- Turn off CDN recompression (Cloudflare Polish, image resizing) for these paths.
- Serve them as static files with their original bytes.

Check the live file still has its gain map:

```bash
curl -s https://example.com/images/name.uhdr.jpg -o /tmp/check.jpg && python3 -c "from PIL import Image; print(getattr(Image.open('/tmp/check.jpg'), 'n_frames', 1))"
```

`2`: intact. `1`: something re-encoded it.

## CSS backgrounds

`<picture>` cannot reach a CSS background. Swap the image with media queries instead:

```css
.band { background-image: url("name.sdr.jpg"); }
@media (color-gamut: p3) { .band { background-image: url("name.p3.jpg"); } }
@media (dynamic-range: high) { .band { background-image: url("name.uhdr.jpg"); } }
```
