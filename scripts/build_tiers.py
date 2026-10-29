"""Build the three delivery tiers from a generated base photo and one generated darker edit, verify
them by decoding, and write a <picture> snippet, a report and a preview page.

Usage: python build_tiers.py <base.jpg> <dark.jpg> <output dir> --slug NAME [--headroom auto|N] [--chroma-boost 1.15]

Tiers (all from one HDR master):
  <slug>.uhdr.jpg  Ultra HDR: detail-kept sRGB base + multichannel gain map (HDR + P3 on HDR screens)
  <slug>.p3.jpg    SDR in Display P3 (wide-gamut screens not showing HDR)
  <slug>.sdr.jpg   SDR in sRGB (everyone else)

Exit codes: 0 all checks passed, 1 a check failed, 3 the dark edit recovered no highlights (regenerate it).
"""
import argparse, html, io, json, sys
from pathlib import Path
import cv2
import imagecodecs
import numpy as np
from PIL import Image, ImageCms

sys.path.insert(0, str(Path(__file__).resolve().parent))
from display_p3_icc import display_p3_profile, srgb_profile

parser = argparse.ArgumentParser()
parser.add_argument("base")
parser.add_argument("dark")
parser.add_argument("output")
parser.add_argument("--slug", required=True)
parser.add_argument("--headroom", default="auto", help="'auto' or the brightest highlight in x SDR white")
parser.add_argument("--chroma-boost", type=float, default=1.15, help="OKLab chroma scale for saturated colour going into P3")
parser.add_argument("--prompt", default="", help="the scene prompt, recorded in the report")
parser.add_argument("--single-frame", action="store_true", help="no dark edit: highlights are lifted from the base alone")
parser.add_argument("--keep-size", action="store_true", help="keep the base's exact dimensions (upgrading an existing image)")
arguments = parser.parse_args()
output = Path(arguments.output)
output.mkdir(parents=True, exist_ok=True)
slug = arguments.slug

# ---------- colour maths ----------
SRGB_TO_XYZ = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750], [0.0193339, 0.1191920, 0.9503041]])
P3_TO_XYZ = np.array([[0.4865709, 0.2656677, 0.1982173], [0.2289746, 0.6917385, 0.0792869], [0.0000000, 0.0451134, 1.0439444]])
XYZ_TO_P3 = np.linalg.inv(P3_TO_XYZ)
SRGB_TO_P3 = XYZ_TO_P3 @ SRGB_TO_XYZ
P3_TO_SRGB = np.linalg.inv(SRGB_TO_P3)
XYZ_TO_LMS = np.array([[0.8189330101, 0.3618667424, -0.1288597137], [0.0329845436, 0.9293118715, 0.0361456387], [0.0482003018, 0.2643662691, 0.6338517070]])
LMS_TO_OKLAB = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099], [0.0259040371, 0.7827717662, -0.8086757660]])


def srgb_decode(encoded):
    return np.where(encoded <= 0.04045, encoded / 12.92, ((encoded + 0.055) / 1.055) ** 2.4)


def srgb_encode(linear):
    linear = np.clip(linear, 0, None)
    return np.where(linear <= 0.0031308, 12.92 * linear, 1.055 * linear ** (1 / 2.4) - 0.055)


def p3_linear_to_oklab(p3):
    return np.cbrt((p3 @ P3_TO_XYZ.T) @ XYZ_TO_LMS.T) @ LMS_TO_OKLAB.T


def oklab_to_p3_linear(lab):
    return ((lab @ np.linalg.inv(LMS_TO_OKLAB).T) ** 3 @ np.linalg.inv(XYZ_TO_LMS).T) @ XYZ_TO_P3.T


def expand_into_p3(p3_linear, boost):
    """Scale OKLab chroma of already-saturated pixels (never neutrals, stone or skin) and stay inside P3."""
    lab = p3_linear_to_oklab(np.clip(p3_linear, 0, None))
    chroma = np.hypot(lab[..., 1], lab[..., 2])
    ramp = np.clip((chroma - 0.06) / 0.08, 0, 1)  # none below chroma 0.06, full from 0.14
    scale = 1 + (boost - 1) * ramp * ramp * (3 - 2 * ramp)
    peak = np.maximum(p3_linear.max(-1, keepdims=True), 1.0)
    result, decided = p3_linear.copy(), np.zeros(p3_linear.shape[:2], bool)
    for shrink in np.linspace(1.0, 0.0, 11):  # the largest scale that stays inside P3
        trial_scale = 1 + (scale - 1) * shrink
        trial = oklab_to_p3_linear(np.stack([lab[..., 0], lab[..., 1] * trial_scale, lab[..., 2] * trial_scale], -1))
        take = ((trial >= -1e-4) & (trial <= peak + 1e-4)).all(-1) & ~decided
        result[take], decided = trial[take], decided | take
    return np.clip(result, 0, None)


def outside_srgb_share(p3_linear):
    srgb = p3_linear @ P3_TO_SRGB.T
    peak = np.maximum(p3_linear.max(-1), 1.0)[..., None]
    return float(((srgb < -0.002) | (srgb > peak + 0.002)).any(-1).mean())


# ---------- load and align the dark edit to the base ----------
base = cv2.imread(arguments.base)[..., ::-1]
dark = cv2.imread(arguments.dark)[..., ::-1]
generator_base_full = base.copy()
height, width = base.shape[:2]


def feature_gray(image):
    gray = cv2.cvtColor(np.ascontiguousarray(image), cv2.COLOR_RGB2GRAY)
    return cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(cv2.equalizeHist(gray))


if arguments.single_frame:
    dark = base.copy()
    coverage = np.ones((height, width), bool)
    inliers, residual = None, None
else:
    sift = cv2.SIFT_create(6000)
    base_points, base_descriptors = sift.detectAndCompute(feature_gray(base), None)
    dark_points, dark_descriptors = sift.detectAndCompute(feature_gray(dark), None)
    good = [first for first, second in cv2.BFMatcher().knnMatch(dark_descriptors, base_descriptors, k=2) if first.distance < 0.75 * second.distance]
    if len(good) < 12:
        print(f"FAIL alignment: only {len(good)} feature matches; the dark edit does not show the same scene", file=sys.stderr)
        sys.exit(3)
    source = np.float32([dark_points[match.queryIdx].pt for match in good])
    target = np.float32([base_points[match.trainIdx].pt for match in good])
    homography, inliers = cv2.findHomography(source, target, cv2.RANSAC, 3.0)
    dark = cv2.warpPerspective(dark, homography, (width, height), flags=cv2.INTER_LANCZOS4)
    coverage = cv2.erode(cv2.warpPerspective(np.ones(dark.shape[:2], np.uint8) * 255, homography, (width, height)), np.ones((9, 9), np.uint8)) > 0
    residual = np.linalg.norm(cv2.perspectiveTransform(source[None], homography)[0] - target, axis=1)[inliers.ravel() == 1]

if arguments.keep_size:
    # Upgrading an existing image: its dimensions are part of the page's layout, so never crop.
    # Where the edit does not reach, the base stands in (no recovered highlight detail there).
    dark = np.where(coverage[..., None], dark, base)
else:
    # Crop to the rectangle the dark edit covers (trim the worst edge until clean), even dimensions.
    top, bottom, left, right = 0, height, 0, width
    while not coverage[top:bottom, left:right].all():
        window = coverage[top:bottom, left:right]
        gaps = {"top": (~window[0]).sum(), "bottom": (~window[-1]).sum(), "left": (~window[:, 0]).sum(), "right": (~window[:, -1]).sum()}
        worst = max(gaps, key=gaps.get)
        top, bottom, left, right = top + (worst == "top"), bottom - (worst == "bottom"), left + (worst == "left"), right - (worst == "right")
    bottom, right = bottom - (bottom - top) % 2, right - (right - left) % 2
    base, dark = base[top:bottom, left:right], dark[top:bottom, left:right]
    height, width = base.shape[:2]

base_encoded, dark_encoded = base / 255.0, dark / 255.0
base_linear, dark_linear = srgb_decode(base_encoded), srgb_decode(dark_encoded)

# Measured exposure gap (informational: a generator's edit is not a physical exposure).
base_mean, dark_mean = base_linear.mean(-1), dark_linear.mean(-1)
usable = (base_mean > 0.08) & (base_encoded.max(-1) < 0.85) & (dark_mean > 0.004) & (dark_encoded.max(-1) < 0.85)
measured_gap = float(-np.log2(np.median(base_mean[usable] / dark_mean[usable]))) if usable.sum() > 100 else None

# ---------- highlights: where the base clips, and what the dark edit holds there ----------
highlight_ramp = np.clip((base_encoded.max(-1) - 0.80) / 0.17, 0, 1)
highlight_ramp = cv2.GaussianBlur(highlight_ramp * highlight_ramp * (3 - 2 * highlight_ramp), (0, 0), 3)
highlight_mask = highlight_ramp > 0.5
highlight_area = float(highlight_mask.mean())
recovered_share = float((dark_encoded.max(-1)[highlight_mask] < 0.97).mean()) if highlight_mask.any() else 1.0
if not arguments.single_frame and highlight_area > 0.001 and recovered_share < 0.5:
    print(f"FAIL dark edit: only {100 * recovered_share:.0f}% of the base's highlights are unclipped in it", file=sys.stderr)
    sys.exit(3)

# ---------- headroom: chosen from what the highlights are ----------
dark_highlight_chroma = 0.0
if highlight_mask.any():
    lab = p3_linear_to_oklab(dark_linear[highlight_mask] @ SRGB_TO_P3.T)
    dark_highlight_chroma = float(np.hypot(lab[:, 1], lab[:, 2]).mean())
if arguments.headroom != "auto":
    headroom, headroom_reason = float(arguments.headroom), "set by hand"
elif highlight_area <= 0.001:
    headroom, headroom_reason = 2.0, "almost nothing clips: HDR adds little"
elif dark_highlight_chroma > 0.08:
    headroom, headroom_reason = 8.0, "coloured light sources (fire, neon, lamps)"
elif highlight_area > 0.03:
    headroom, headroom_reason = 4.0, "large bright areas (snow, sky, cloud)"
else:
    headroom, headroom_reason = 6.0, "small neutral highlights (speculars, bulbs, sun)"

# ---------- HDR master ----------
# The dark edit supplies the highlights' shape and colour; their level is authored up to the headroom.
# Boost is relative to each pixel's own SDR brightness, so ramp edges never lift dark neighbours.
dark_luminance = dark_linear @ SRGB_TO_XYZ[1]
reference_level = np.percentile(dark_luminance[highlight_mask], 99.5) if highlight_mask.any() else 1.0
highlight_strength = np.clip(dark_luminance / max(reference_level, 1e-4), 0, 1) ** 1.5
base_luminance = base_linear @ SRGB_TO_XYZ[1]
target_luminance = base_luminance * (1 + (headroom - 1) * highlight_strength * highlight_ramp)
colour_ramp = np.clip((base_encoded.max(-1) - 0.92) / 0.06, 0, 1)[..., None]  # dark-edit colour only where the base has none
chromaticity = (1 - colour_ramp) * base_linear / np.maximum(base_luminance, 1e-5)[..., None] \
    + colour_ramp * dark_linear / np.maximum(dark_luminance, 1e-5)[..., None]
hdr_srgb_linear = chromaticity * target_luminance[..., None]
hdr_p3 = expand_into_p3(hdr_srgb_linear @ SRGB_TO_P3.T, arguments.chroma_boost)


# ---------- SDR base: detail-kept local tone map of the master ----------
def detail_kept_sdr(hdr_linear, knee=0.7, top_level=0.97):
    """Log-luminance base/detail split; the smooth base gets a soft shoulder above the knee and the detail
    rides on top, so highlights keep texture. Out-of-range colour keeps its hue and saturation and gives
    up level: bright fire stays orange instead of turning pale."""
    luminance = np.maximum(hdr_linear @ SRGB_TO_XYZ[1], 1e-5)
    log_luminance = np.log2(luminance).astype(np.float32)
    base_layer = cv2.bilateralFilter(log_luminance, 0, 0.5, 6)
    log_knee, span = np.log2(knee), np.log2(top_level) - np.log2(knee)
    compressed = np.where(base_layer > log_knee, log_knee + span * (1 - np.exp(-np.maximum(base_layer - log_knee, 0) / span)), base_layer)
    new_luminance = np.minimum(2.0 ** (compressed + log_luminance - base_layer), 0.995)
    colour = hdr_linear / luminance[..., None] * new_luminance[..., None]
    colour = colour / np.maximum(colour.max(-1, keepdims=True), 1.0)
    return (np.clip(srgb_encode(np.clip(colour, 0, 1)), 0, 1) * 255).round().astype(np.uint8)


# Single frame: there is no recovered highlight detail to tone-map back in, so the generator's own
# picture is the best SDR base; the gain map alone adds the lift.
sdr_pixels = base.copy() if arguments.single_frame else detail_kept_sdr(hdr_srgb_linear)

# ---------- encode the three tiers ----------
alpha = np.ones((height, width, 1))
ultrahdr = imagecodecs.ultrahdr_encode(
    np.concatenate([hdr_p3, alpha], -1).astype(np.float16), level=92,
    sdr=np.concatenate([sdr_pixels, alpha * 255], -1).astype(np.uint8),
    gamut=imagecodecs.ULTRAHDR.CG.DISPLAY_P3, usage=imagecodecs.ULTRAHDR.USAGE.QUALITY,
    gainmap_level=90, multichannel=True,
)
paths = {"uhdr": output / f"{slug}.uhdr.jpg", "p3": output / f"{slug}.p3.jpg", "sdr": output / f"{slug}.sdr.jpg"}
paths["uhdr"].write_bytes(ultrahdr)
Image.fromarray(sdr_pixels).save(paths["sdr"], quality=90, icc_profile=srgb_profile())
p3_sdr_linear = np.clip(expand_into_p3(srgb_decode(sdr_pixels / 255.0) @ SRGB_TO_P3.T, arguments.chroma_boost), 0, 1)
Image.fromarray((srgb_encode(p3_sdr_linear) * 255).round().astype(np.uint8)).save(paths["p3"], quality=90, icc_profile=display_p3_profile())

# Generator base cropped the same way, for the preview slider.
Image.fromarray(base).save(output / f"{slug}.generator-base.jpg", quality=90)

# ---------- verify by reading every file back ----------
decoded_hdr = imagecodecs.ultrahdr_decode(ultrahdr, dtype=np.float16)[..., :3].astype(np.float32)
decoded_sdr = imagecodecs.ultrahdr_decode(ultrahdr, dtype=np.uint8)[..., :3]
container = Image.open(io.BytesIO(ultrahdr))
intended_luminance, decoded_luminance = hdr_p3 @ P3_TO_XYZ[1], decoded_hdr @ P3_TO_XYZ[1]
above_white = intended_luminance > 1
intended_peak = float(np.percentile(intended_luminance, 99.95))
decoded_peak = float(np.percentile(decoded_luminance, 99.95))
decode_error = float(np.median(np.abs(decoded_luminance - intended_luminance)[above_white] / intended_luminance[above_white])) if above_white.any() else 0.0
p3_file = Image.open(paths["p3"])
p3_profile = ImageCms.ImageCmsProfile(io.BytesIO(p3_file.info["icc_profile"]))
p3_as_srgb = np.asarray(ImageCms.profileToProfile(p3_file, p3_profile, ImageCms.createProfile("sRGB"), renderingIntent=1), dtype=float)
p3_outside = ((p3_sdr_linear @ P3_TO_SRGB.T < -0.002) | (p3_sdr_linear @ P3_TO_SRGB.T > 1.002)).any(-1)
p3_inside_difference = float(np.abs(p3_as_srgb - sdr_pixels).mean(-1)[~p3_outside].mean())
blown_generator = float((base.min(-1) >= 250).mean())
blown_sdr = float((np.asarray(Image.open(paths["sdr"])).min(-1) >= 250).mean())

checks = {
    "alignment: 50+ inliers, median residual under 2 px (or single frame)": arguments.single_frame or (int(inliers.sum()) >= 50 and float(np.median(residual)) < 2.0),
    "Ultra HDR holds 2 images (base + gain map)": getattr(container, "n_frames", 1) == 2,
    "decoded HDR peak within 10% of the master": abs(decoded_peak - intended_peak) <= 0.1 * intended_peak,
    "decode error above white under 12% (median)": decode_error < 0.12,
    "SDR base in the file matches the intended base (mean under 3)": float(np.abs(decoded_sdr.astype(int) - sdr_pixels.astype(int)).mean()) < 3.0,
    "P3 file carries a Display P3 profile": ImageCms.getProfileDescription(p3_profile).strip() == "Display P3",
    "P3 file leaves sRGB colours alone (mean under 4)": p3_inside_difference < 4.0,
    "SDR base blows out no more than the generator base": blown_sdr <= blown_generator + 0.0005,
}
report = {
    "slug": slug,
    "prompt": arguments.prompt,
    "size": f"{width}x{height}",
    "frames": "single frame: highlights lifted from the base alone, no recovered detail" if arguments.single_frame else "base + dark edit",
    "alignment": "not needed" if arguments.single_frame else f"{int(inliers.sum())} inliers, median residual {np.median(residual):.2f}px",
    "dark edit, measured gap": f"{measured_gap:+.2f} EV" if measured_gap is not None else "not measurable",
    "highlights clipped in the generator base": f"{100 * highlight_area:.1f}%",
    "headroom": headroom,
    "headroom reason": headroom_reason,
    "HDR peak in file (x SDR white, 99.95th pct)": round(decoded_peak, 2),
    "pixels above SDR white": f"{100 * (decoded_luminance > 1.05).mean():.1f}%",
    "HDR pixels outside sRGB (P3)": f"{100 * outside_srgb_share(decoded_hdr):.1f}%",
    "P3 SDR pixels outside sRGB": f"{100 * p3_outside.mean():.1f}%",
    "blown to white: generator base -> SDR tier": f"{100 * blown_generator:.2f}% -> {100 * blown_sdr:.2f}%",
    "decode error above white (median)": round(decode_error, 3),
    "file sizes": {tier: f"{path.stat().st_size / 1024:.0f} KB" for tier, path in paths.items()},
    "checks": checks,
    "all checks passed": all(checks.values()),
}
(output / f"{slug}.report.json").write_text(json.dumps(report, indent=2))

# ---------- delivery snippet and preview page ----------
alt_text = html.escape(arguments.prompt or slug, quote=True)
picture = f"""<picture>
  <source media="(dynamic-range: high)" srcset="{slug}.uhdr.jpg">
  <source media="(color-gamut: p3)" srcset="{slug}.p3.jpg">
  <img src="{slug}.sdr.jpg" width="{width}" height="{height}" alt="{alt_text}" loading="lazy" decoding="async">
</picture>
<!-- Keep HDR calm in grids and let it run when opened:
     .grid img {{ dynamic-range-limit: standard; }}  .lightbox img {{ dynamic-range-limit: no-limit; }}
     Never pass these files through an optimizer that re-saves JPEGs: it drops the gain map and the profile. -->
"""
(output / f"{slug}.picture.html").write_text(picture)
template = (Path(__file__).resolve().parent / "preview_template.html").read_text()
(output / "preview.html").write_text(template.replace("__SLUG__", slug).replace("__PICTURE__", picture.split("<!--")[0].replace(' loading="lazy"', ''))
                                     .replace("__REPORT__", json.dumps(report)).replace("__TITLE__", alt_text))

print(json.dumps(report, indent=2))
if not report["all checks passed"]:
    print("FAIL: " + "; ".join(name for name, passed in checks.items() if not passed), file=sys.stderr)
    sys.exit(1)
