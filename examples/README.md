# Examples

Every folder is a finished run you can open, rebuild or copy from. Results and figures:
[docs/results.md](../docs/results.md).

| Folder | Scene | Shows |
|---|---|---|
| [`glass-furnace`](glass-furnace) | Fire and molten glass in a dark workshop | The biggest gain: blown fire recovered, 7.85× HDR, P3 vases |
| [`night-market`](night-market) | Lanterns and a flaming wok on a wet street | A scene made end to end from one prompt (`run --generator cursor`) |
| [`neon-alley`](neon-alley) | Neon tubes in a rainy alley | P3 as the main gain (8.4% outside sRGB) |
| [`snow-peak`](snow-peak) | Sunlit snow over a shaded forest | Large bright areas, lower peak (4×), no real P3 gain |
| [`lighthouse-dusk`](lighthouse-dusk) | A lamp at dusk | Little to gain, and the report says so |
| [`site-upgrade`](site-upgrade) | A small site with six images | `audit`, `upgrade` and `rewrite` on an existing repo |

## What is in a scene folder

```text
glass-furnace/
├── frames/                         the generator's two images (base, dark edit)
├── plan.json                       the scene prompt
├── glass-furnace.uhdr.jpg          HDR file (Ultra HDR, gain map)
├── glass-furnace.p3.jpg            SDR file in Display P3
├── glass-furnace.sdr.jpg           SDR file in sRGB
├── glass-furnace.generator-base.jpg  the generator's picture, cropped like the files above
├── glass-furnace.picture.html      the <picture> element
├── glass-furnace.report.json       every measurement and check
└── preview.html                    comparison slider and report
```

## Open the previews

```bash
python3 -m http.server 8000 --directory examples
```

Then open <http://localhost:8000/glass-furnace/preview.html> (or any other scene). An HDR screen in a
Chromium browser or Safari shows the HDR file's lift; on an sRGB screen the files look alike and the
report carries the difference.

## Rebuild a scene

The frames are saved, so a rebuild needs no generator:

```bash
python3 scripts/image_peak.py build --slug glass-furnace --out examples
```

## Prompts used

| Scene | Prompt |
|---|---|
| Glass furnace | Inside a dim stone glassblowing workshop: the open mouth of a glass furnace glows with intense orange-yellow fire, a gather of molten glass glows on a steel pipe, cobalt blue and emerald green vases catch the light on a shelf |
| Night market | A night market street food stall with glowing paper lanterns, a hot wok throwing orange flames, steam rising, wet pavement reflecting the lights |
| Neon alley | A narrow rain-soaked alley at night with abstract neon tubes in magenta, cyan and red, bare bulbs strung overhead and long coloured reflections on wet cobblestones |
| Snow peak | A high alpine valley at midday: a sunlit snowy mountain face and glacier under a deep blue sky, exposed for the dark pine forest in the foreground shade |
| Lighthouse at dusk | A stone lighthouse on dark sea cliffs at dusk, its lamp lit and casting a beam, waves breaking white on the rocks below, a thin band of orange sunset under heavy storm clouds |

Each base prompt was extended by image-peak with "a real, unedited camera photograph on a tripod, exposed
for the midtones …" and the no-text, no-logo constraints; `plan` prints the exact text.

## The images

Generated with Cursor's built-in image generator for these examples; released with the repo under the
MIT licence.
