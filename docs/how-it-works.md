# How it works

The generator supplies the picture. The code supplies the range and the colour, and checks its own work.
Everything below is in [`scripts/build_tiers.py`](../scripts/build_tiers.py).

## 1. Two images of one scene

The base is the prompt photographed normally; the dark image is an edit of that base about 4 stops
darker. The edit holds what the base lost: the flame's structure, the snow's texture, the colour of a
neon tube that clipped to white.

Generators darken by less than they are asked for. In the examples, "4 stops darker" measured
between 0.4 and 1.9 stops, and unevenly: highlights darken more than midtones. So the dark image supplies
the **shape and colour** of highlights, and the chosen headroom sets their level.

## 2. Alignment

Edits reframe slightly. SIFT features (on contrast-equalised greyscale, so features match across
exposures) and a RANSAC homography map the dark image onto the base. The check requires at least 50
inliers and a median residual under 2 px; the examples aligned with 488 to 1,671 inliers at 0.47 to
1.11 px. New images are cropped to the area both images cover. Site upgrades keep the original size and
use the base outside the edit's area.

## 3. Headroom

The HDR peak, as a multiple of SDR white, is chosen from what the highlights are (`--headroom N` overrides):

| Highlights | Peak | Example |
|---|---|---|
| Coloured light sources (dark-image highlight chroma over 0.08) | 8× | furnace, night market, neon, lighthouse |
| Large bright areas (over 3% of the picture) | 4× | snow |
| Small neutral highlights | 6× | speculars, bulbs |
| Almost nothing clipped (0.1% or less) | 2× | |

## 4. HDR master

The base everywhere. Where the base clips, highlights are lifted toward the peak by how bright the dark
image is there, relative to each pixel's own SDR level, so a dark neighbour at the soft edge of a
highlight (sky next to snow) keeps its own level. Colour inside clipped areas comes from the dark image,
because the base clipped it to white there.

## 5. The sRGB file: detail kept

A local tone map of the master: a bilateral filter splits log luminance into a smooth base layer and a
detail layer; the base layer gets a soft shoulder above 0.7 of white and the detail rides on top, so
highlights keep their texture. Where a colour cannot be both that bright and that saturated in sRGB,
the pixel keeps its hue and saturation and gives up brightness: fire stays orange flames. In
single-frame mode the generator's own picture is the sRGB file.

## 6. P3

Colour that is already saturated (OKLab chroma 0.06 to 0.14 ramps the effect in) is scaled by 1.15 and
kept inside Display P3. Neutrals, stone and skin keep their values. The Display P3 ICC profile is built in code
by [`display_p3_icc.py`](../scripts/display_p3_icc.py) (P3 primaries, D65 white, the sRGB curve); it
matches Little CMS within 1 step out of 255.

## 7. Encoding

libultrahdr 2.0.2 (through `imagecodecs`) encodes the sRGB file plus a multichannel gain map that
reaches the P3 master on HDR screens. libultrahdr fixes the base to sRGB, which is why the P3 SDR file is
separate.

## 8. Checks

Every file is decoded again and checked:

1. Alignment: 50+ inliers, median residual under 2 px (or single frame).
2. The Ultra HDR file holds two images: base and gain map.
3. The decoded HDR peak is within 10% of the master's.
4. Decode error above white under 12% (median).
5. The sRGB base inside the file matches the intended one (mean difference under 3 of 255).
6. The P3 file carries a Display P3 profile.
7. The P3 file leaves sRGB colours alone (mean difference under 4 of 255 after conversion back).
8. The sRGB file blows out no more pixels than the generator did.

A failed check exits 1 and names itself. The report records every number behind it.

## What it is

With generator images, the highlights and the P3 colour are **authored**: the generator invents what the
darker exposure shows, and the chosen headroom sets the peak. With camera brackets in `frames/`, the same
code merges captured light.
