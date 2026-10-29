"""Upgrade the images of an existing site or repo to the three delivery tiers.

  audit   REPO [--work DIR]
          Finds raster images and every place the source references them, scores each image (clipped
          highlights, saturated colour, photo or graphic), flags build steps that would strip gain maps or
          colour profiles, and writes WORK/audit.json and WORK/audit.md. Changes nothing.

  upgrade REPO [--work DIR] [--images PATH ...] [--generator ADAPTER | --plan-only] [--headroom auto|N]
          Builds tiers for the recommended images (or the listed ones) at their exact original size and
          writes them next to each original: NAME.uhdr.jpg, NAME.p3.jpg, NAME.sdr.jpg, only the tiers
          that earn their bytes. With --generator, the generator edits each original darker (recovered
          highlight detail); without one, single-frame mode. --plan-only writes the dark-edit prompts for an
          agent's own image tool and stops; run upgrade again once the edits are saved. Originals are never
          modified or deleted.

  rewrite REPO [--work DIR] [--apply]
          Turns literal <img> references to upgraded images into <picture> elements (srcSet in JSX) and
          writes WORK/markup.patch plus WORK/rewrite.md (CSS backgrounds, markdown, imports and data-module
          references to handle by hand, and the pipeline risks). --apply writes the files too.

WORK defaults to REPO/.image-peak (add it to .gitignore).
"""
import argparse, difflib, io, json, os, re, shutil, subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageCms

SCRIPTS = Path(__file__).resolve().parent
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
SOURCE_EXTENSIONS = {".html", ".htm", ".jsx", ".tsx", ".js", ".ts", ".mjs", ".vue", ".svelte", ".astro", ".md", ".mdx",
                     ".css", ".scss", ".sass", ".less", ".njk", ".liquid", ".hbs", ".ejs", ".php", ".erb", ".json"}
SKIP_DIRECTORIES = {"node_modules", ".git", "dist", "build", ".next", ".nuxt", ".output", ".svelte-kit", ".astro", "out",
                    "coverage", ".cache", ".turbo", ".vercel", ".wrangler", ".image-peak", "graphify-out", "vendor", "__pycache__"}
TIER_SUFFIXES = (".uhdr.jpg", ".p3.jpg", ".sdr.jpg", ".generator-base.jpg")
WIDE_GAMUT_WORDS = ("p3", "adobe rgb", "prophoto", "2020", "wide gamut")
MINIMUM_LONG_SIDE = 480


def walk(repo, extensions):
    for root, directories, files in os.walk(repo):
        directories[:] = [d for d in directories if d not in SKIP_DIRECTORIES and not d.startswith(".image-peak")]
        for name in files:
            if Path(name).suffix.lower() in extensions:
                yield Path(root) / name


# ---------- image analysis ----------
def to_srgb(image):
    """RGB pixels in sRGB, converting through the embedded profile when there is one."""
    profile_bytes = image.info.get("icc_profile")
    rgb = image.convert("RGB")
    if profile_bytes:
        try:
            source = ImageCms.ImageCmsProfile(io.BytesIO(profile_bytes))
            rgb = ImageCms.profileToProfile(rgb, source, ImageCms.createProfile("sRGB"), renderingIntent=1)
        except Exception:
            pass
    return rgb


def profile_description(image):
    profile_bytes = image.info.get("icc_profile")
    if not profile_bytes:
        return "none (read as sRGB)"
    try:
        return ImageCms.getProfileDescription(ImageCms.ImageCmsProfile(io.BytesIO(profile_bytes))).strip()
    except Exception:
        return "unreadable"


def has_gain_map(path, image):
    head = path.open("rb").read(512 * 1024)
    return b"hdrgm:" in head or b"urn:iso:std:iso:ts:21496" in head or getattr(image, "n_frames", 1) > 1 and image.format == "MPO"


def uses_transparency(image):
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        alpha = np.asarray(image.convert("RGBA"))[..., 3]
        return bool((alpha < 250).any())
    return False


def analyse(path, repo):
    image = Image.open(path)
    width, height = image.size
    record = {"path": str(path.relative_to(repo)), "size": f"{width}x{height}", "bytes": path.stat().st_size,
              "profile": profile_description(image)}
    skip = None
    if max(width, height) < MINIMUM_LONG_SIDE:
        skip = f"small ({max(width, height)} px long side): icon or thumbnail"
    elif uses_transparency(image):
        skip = "uses transparency: gain-map JPEGs have no alpha"
    elif has_gain_map(path, image):
        skip = "already has a gain map (HDR)"
    elif any(word in record["profile"].lower() for word in WIDE_GAMUT_WORDS):
        skip = "already wide-gamut: keep the original as the P3 file; rebuilding from sRGB would lose colour"
    rgb = to_srgb(image)
    rgb.thumbnail((800, 800))
    pixels = np.asarray(rgb, dtype=np.float32) / 255.0
    linear = np.where(pixels <= 0.04045, pixels / 12.92, ((pixels + 0.055) / 1.055) ** 2.4)
    lms = np.cbrt(linear @ np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566], [0.0883024619, 0.2817188376, 0.6299787005]]).T)
    lab = lms @ np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099], [0.0259040371, 0.7827717662, -0.8086757660]]).T
    chroma = np.hypot(lab[..., 1], lab[..., 2])
    clipped = float((pixels.max(-1) >= 250 / 255).mean())
    saturated = float((chroma > 0.14).mean())
    small = np.asarray(rgb.resize((256, max(1, round(256 * rgb.height / rgb.width)))), dtype=np.int16)
    flat = float((np.abs(np.diff(small, axis=1)).max(-1) == 0).mean())
    unique_colours = len(np.unique(small.reshape(-1, 3), axis=0))
    graphic = flat > 0.45 or unique_colours < 2500
    record.update({"clipped highlights": f"{100 * clipped:.1f}%", "saturated colour": f"{100 * saturated:.1f}%",
                   "kind": "graphic (flat colour, UI or illustration)" if graphic else "photographic"})
    if skip is None and graphic:
        skip = "graphic: flat colour gains nothing from HDR, and P3 expansion would shift brand colours"
    if skip is None and clipped < 0.003 and saturated < 0.03:
        skip = "nothing to gain: almost no clipped highlights or saturated colour"
    if skip:
        record["recommendation"], record["reason"] = "skip", skip
    elif clipped >= 0.003:
        record["recommendation"] = "upgrade"
        record["reason"] = "clipped highlights to recover (a generator dark edit recovers detail; single-frame lifts them)"
    else:
        record["recommendation"] = "upgrade"
        record["reason"] = "saturated colour for the P3 file; little HDR"
    return record


# ---------- references in source ----------
def classify(text, start, end, file_suffix):
    tag_start = text.rfind("<", 0, start)
    tag_close = text.rfind(">", 0, start)
    if tag_start > tag_close:
        tag_end = text.find(">", end)
        tag = text[tag_start:tag_end + 1]
        if re.match(r"<img\b", tag, re.I):
            attribute = re.search(r"\b(src|srcSet|srcset)\s*=\s*[\"']?[^\"'\s>]*$", text[tag_start:end], re.I)
            preceding = text[max(0, tag_start - 400):tag_start]
            inside_picture = preceding.lower().rfind("<picture") > preceding.lower().rfind("</picture>")
            if inside_picture:
                return "img-in-picture", (tag_start, tag_end + 1)
            if attribute and attribute.group(1).lower() == "src" and re.search(r"\bsrc\s*=\s*[\"'][^\"']*$", text[tag_start:end]):
                return "img-tag", (tag_start, tag_end + 1)
            return "img-other-attribute", (tag_start, tag_end + 1)
        return "other-tag", None
    line_start = text.rfind("\n", 0, start) + 1
    line = text[line_start:text.find("\n", end) if text.find("\n", end) != -1 else len(text)]
    if re.search(r"url\(\s*[\"']?[^)\"']*$", text[line_start:end]):
        return "css-url", None
    if file_suffix in (".md", ".mdx") and re.search(r"!\[[^\]]*\]\([^)]*$", text[line_start:end]):
        return "markdown-image", None
    if re.match(r"\s*import\b", line) or "require(" in line:
        return "import", None
    return "string", None


def find_references(repo, images):
    by_name = {}
    for image in images:
        by_name.setdefault(Path(image["path"]).name, []).append(image)
    if not by_name:
        return
    pattern = re.compile("|".join(re.escape(name) for name in sorted(by_name, key=len, reverse=True)))
    for source in walk(repo, SOURCE_EXTENSIONS):
        if source.stat().st_size > 2_000_000 or source.name in ("package-lock.json", "pnpm-lock.yaml"):
            continue
        try:
            text = source.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if text.startswith("# image-peak") or '"pipeline risks"' in text or ('"shipped"' in text and '"fallback"' in text):
            continue  # image-peak's own reports, wherever they were copied
        for match in pattern.finditer(text):
            name = match.group(0)
            if text[match.end():match.end() + 1].isalnum():
                continue
            literal_start = max(text.rfind(quote, 0, match.start()) for quote in ("\"", "'", "(", "`", " ", "="))
            reference = text[literal_start + 1:match.end()]
            candidates = by_name[name]
            if len(candidates) > 1:  # same file name in several folders: match the referenced path's tail
                tail = reference.lstrip("./").lstrip("/")
                candidates = [c for c in candidates if c["path"].replace(os.sep, "/").endswith(tail)] or candidates[:1]
            kind, span = classify(text, match.start(), match.end(), source.suffix.lower())
            if kind == "other-tag" and source.suffix.lower() == ".json":
                kind = "string"
            candidates[0].setdefault("references", []).append({
                "file": str(source.relative_to(repo)), "line": text.count("\n", 0, match.start()) + 1,
                "kind": kind, "reference": reference})


# ---------- pipeline risks ----------
RISKY_PACKAGES = {
    "next": "next/image re-encodes images unless images.unoptimized is true",
    "@astrojs/image": "Astro image integration re-encodes images",
    "@nuxt/image": "Nuxt Image re-encodes images",
    "gatsby-plugin-image": "Gatsby image processing re-encodes images",
    "gatsby-plugin-sharp": "Gatsby sharp processing re-encodes images",
    "vite-imagetools": "vite-imagetools re-encodes imported images",
    "vite-plugin-image-optimizer": "the Vite image optimizer re-encodes images",
    "imagemin": "imagemin re-encodes images", "sharp": "sharp can re-encode images (check where it runs)",
    "@squoosh/lib": "squoosh re-encodes images", "eleventy-img": "eleventy-img re-encodes images",
    "@11ty/eleventy-img": "eleventy-img re-encodes images",
}
SCRIPT_PATTERNS = [
    (re.compile(r"\.save\([^)]*(JPEG|jpeg|quality)"), "re-saves images with Pillow"),
    (re.compile(r"\bsharp\("), "re-encodes images with sharp"),
    (re.compile(r"\b(jpegoptim|mozjpeg|cjpeg|cwebp|guetzli|imagemin|squoosh|optipng|pngquant)\b"), "runs an image optimizer"),
]


def pipeline_risks(repo):
    risks = []
    for package_file in walk(repo, {".json"}):
        if package_file.name != "package.json":
            continue
        try:
            package = json.loads(package_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        dependencies = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
        for name, why in RISKY_PACKAGES.items():
            if name not in dependencies:
                continue
            if name == "next":
                configs = [p for p in package_file.parent.glob("next.config.*")]
                if any(re.search(r"unoptimized\s*:\s*true", c.read_text(encoding="utf-8", errors="ignore")) for c in configs):
                    continue
            if name == "sharp" and "next" in dependencies:
                continue
            risks.append({"where": str(package_file.relative_to(repo)), "risk": f"{name}: {why}",
                          "fix": "exclude *.uhdr.jpg and *.p3.jpg from it (or serve them from a path it skips)"})
        for script_name, command in package.get("scripts", {}).items():
            for pattern, why in SCRIPT_PATTERNS[2:]:
                if pattern.search(command):
                    risks.append({"where": f"{package_file.relative_to(repo)} scripts.{script_name}", "risk": why,
                                  "fix": "skip *.uhdr.jpg and *.p3.jpg"})
    for script in walk(repo, {".py", ".js", ".mjs", ".cjs", ".sh", ".ts"}):
        if script.stat().st_size > 500_000 or "image-peak" in str(script.relative_to(repo)) or script.name in ("site_upgrade.py", "build_tiers.py"):
            continue
        text = script.read_text(encoding="utf-8", errors="ignore")
        if not re.search(r"(optimi[sz]e|compress|minif|resize|thumbnail)", text, re.I):
            continue
        for pattern, why in SCRIPT_PATTERNS:
            if pattern.search(text):
                risks.append({"where": str(script.relative_to(repo)), "risk": f"script {why}",
                              "fix": "skip *.uhdr.jpg and *.p3.jpg in it: re-saving drops the gain map and the P3 profile"})
                break
    if any(repo.glob("wrangler.*")):
        risks.append({"where": "wrangler config", "risk": "Cloudflare: Polish or Image Resizing re-encodes JPEGs if enabled for the zone (not visible in the repo)",
                      "fix": "keep Polish off for the image paths, or check the served bytes still hold the gain map"})
    return risks


# ---------- subcommands ----------
def work_directory(arguments):
    repo = Path(arguments.repo).expanduser().resolve()
    work = Path(arguments.work).expanduser().resolve() if arguments.work else repo / ".image-peak"
    work.mkdir(parents=True, exist_ok=True)
    return repo, work


def audit(arguments):
    repo, work = work_directory(arguments)
    images = [analyse(path, repo) for path in sorted(walk(repo, IMAGE_EXTENSIONS)) if not path.name.endswith(TIER_SUFFIXES)]
    find_references(repo, images)
    risks = pipeline_risks(repo)
    result = {"repo": str(repo), "images": images, "pipeline risks": risks}
    (work / "audit.json").write_text(json.dumps(result, indent=2))
    lines = [f"# image-peak audit: {repo.name}", "",
             "| Image | Size | Clipped | Saturated | Used in | Recommendation |", "|---|---|---|---|---|---|"]
    for image in images:
        references = image.get("references", [])
        used = ", ".join(sorted({f"{r['file']}:{r['line']} ({r['kind']})" for r in references})[:4]) or "not referenced"
        lines.append(f"| `{image['path']}` | {image['size']} | {image['clipped highlights']} | {image['saturated colour']} | {used} | "
                     f"**{image['recommendation']}**: {image['reason']} |")
    lines += ["", "## Pipeline risks (would strip gain maps or colour profiles)", ""]
    lines += [f"- `{r['where']}`: {r['risk']}. Fix: {r['fix']}." for r in risks] or ["- none found in the repo"]
    (work / "audit.md").write_text("\n".join(lines) + "\n")
    upgrade_count = sum(i["recommendation"] == "upgrade" for i in images)
    print(f"{len(images)} images, {upgrade_count} recommended for upgrade, {len(risks)} pipeline risks")
    for image in images:
        print(f"  {image['recommendation']:7} {image['path']}  ({image['reason']})")
    for risk in risks:
        print(f"  RISK {risk['where']}: {risk['risk']}")
    print(f"wrote {work / 'audit.md'}")


def percentage(value):
    return float(str(value).rstrip("%")) if value is not None else 0.0


DARK_EDIT_PROMPT = ("Edit the input image. Output the same frame at the same size with identical framing, camera position and every "
                    "object, light and reflection in exactly the same place; it is the next frame of a tripod exposure bracket. "
                    "Change only the exposure: {stops} darker, so everything that is white or nearly white in the input (light "
                    "sources, sky, snow, fire, reflections) shows its full colour and texture with nothing clipped anywhere, while "
                    "midtones and shadows fall towards black. Do not add, remove or move anything. Real camera photograph, no tone "
                    "mapping. No text, no logos, no watermarks.")


def upgrade(arguments):
    repo, work = work_directory(arguments)
    audit_file = work / "audit.json"
    if not audit_file.exists():
        sys.exit("FAIL: run audit first")
    images = json.loads(audit_file.read_text())["images"]
    if arguments.images:
        wanted = {str(Path(p)) for p in arguments.images}
        selected = [i for i in images if i["path"] in wanted]
        hard_skips = ("transparency", "small", "gain map")
        for image in selected:
            if image["recommendation"] == "skip" and any(word in image["reason"] for word in hard_skips):
                sys.exit(f"FAIL: {image['path']} cannot be upgraded: {image['reason']}")
    else:
        selected = [i for i in images if i["recommendation"] == "upgrade"]
    adapter = None
    if arguments.generator:
        sys.path.insert(0, str(SCRIPTS))
        adapter = arguments.generator
    manifest_file = work / "manifest.json"
    manifest = json.loads(manifest_file.read_text()) if manifest_file.exists() else {}
    pending_edits, failures = [], []
    for image in selected:
        original = repo / image["path"]
        slug = re.sub(r"[^A-Za-z0-9]+", "-", str(Path(image["path"]).with_suffix(""))).strip("-").lower()
        stem = original.stem
        folder = work / slug
        frames = folder / "frames"
        frames.mkdir(parents=True, exist_ok=True)
        base = frames / f"{stem}.base.png"
        if not base.exists():
            to_srgb(Image.open(original)).save(base)  # lossless, sRGB, original size
        dark = next((p for p in frames.glob(f"{stem}.dark.*") if p.suffix.lower() in IMAGE_EXTENSIONS), None)
        if dark is None and adapter:
            dark = frames / f"{stem}.dark.png"
            print(f"dark edit for {image['path']} ({adapter})")
            if not run_adapter(adapter, DARK_EDIT_PROMPT.format(stops="about 4 stops"), dark, base):
                print(f"  generator failed; building {image['path']} single-frame")
                dark = None
        if dark is None and arguments.plan_only:
            pending_edits.append({"image": image["path"], "input_image": str(base), "save_edit_to": str(frames / f"{stem}.dark.png"),
                                  "prompt": DARK_EDIT_PROMPT.format(stops="about 4 stops"),
                                  "stronger_prompt": DARK_EDIT_PROMPT.format(stops="5 to 6 stops")})
            continue
        code = build(base, dark, folder, stem, image["path"], arguments.headroom)
        if code == 3 and adapter:
            print(f"  dark edit recovered too little; regenerating once, stronger")
            if run_adapter(adapter, DARK_EDIT_PROMPT.format(stops="5 to 6 stops"), dark, base):
                code = build(base, dark, folder, stem, image["path"], arguments.headroom)
        if code == 3:
            print(f"  building {image['path']} single-frame instead")
            dark = None
            code = build(base, None, folder, stem, image["path"], arguments.headroom)
        if code != 0:
            failures.append(image["path"])
            continue
        report = json.loads((folder / f"{stem}.report.json").read_text())
        ship_hdr = percentage(report["pixels above SDR white"]) >= 0.5
        ship_p3 = percentage(report["P3 SDR pixels outside sRGB"]) >= 0.5
        single = dark is None
        shipped = {}
        if ship_hdr or ship_p3:
            # Single frame: the SDR tier is the original's pixels, so the original stays the fallback.
            tiers = (["uhdr"] if ship_hdr else []) + (["p3"] if ship_p3 else []) + ([] if single else ["sdr"])
            for tier in tiers:
                target = original.with_name(f"{stem}.{tier}.jpg")
                shutil.copyfile(folder / f"{stem}.{tier}.jpg", target)
                shipped[tier] = original.with_name(target.name).name
        manifest[image["path"]] = {
            "frames": "single frame" if single else "base + generator dark edit",
            "shipped": shipped, "fallback": shipped.get("sdr", original.name),
            "pixels above SDR white": report["pixels above SDR white"], "P3 SDR pixels outside sRGB": report["P3 SDR pixels outside sRGB"],
            "HDR peak": report["HDR peak in file (x SDR white, 99.95th pct)"], "checks passed": report["all checks passed"],
            "preview": str(folder / "preview.html"),
        }
        verdict = ", ".join(shipped) if shipped else "nothing earned its bytes; left as is"
        print(f"  {image['path']}: {verdict} (peak {manifest[image['path']]['HDR peak']}x, above white {report['pixels above SDR white']}, P3 {report['P3 SDR pixels outside sRGB']})")
    manifest_file.write_text(json.dumps(manifest, indent=2))
    if pending_edits:
        (work / "pending-edits.json").write_text(json.dumps(pending_edits, indent=2))
        print(f"{len(pending_edits)} dark edits to make with your image tool: see {work / 'pending-edits.json'}; then run upgrade again")
    if failures:
        print("FAIL: " + ", ".join(failures))
        sys.exit(1)


def run_adapter(adapter_name, prompt, output_path, input_image):
    bundled = SCRIPTS / "generators" / f"{adapter_name}.sh"
    runners = {".sh": ["bash"], ".py": [sys.executable], ".js": ["node"], ".mjs": ["node"], ".ps1": ["pwsh", "-File"]}
    path = bundled if bundled.exists() else Path(adapter_name).expanduser()
    command = runners.get(path.suffix.lower(), []) + [str(path)]
    prompt_file = output_path.with_suffix(".prompt.txt")
    prompt_file.write_text(prompt)
    for attempt in (1, 2):
        result = subprocess.run(command + ["edit", str(prompt_file), str(output_path), str(input_image)], capture_output=True, text=True, timeout=900)
        if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
            return True
        print(f"  adapter attempt {attempt} failed (exit {result.returncode}): {(result.stderr or result.stdout)[-300:]}", file=sys.stderr)
    return False


def build(base, dark, folder, stem, label, headroom):
    command = [sys.executable, str(SCRIPTS / "build_tiers.py"), str(base), str(dark or base), str(folder), "--slug", stem,
               "--headroom", headroom, "--prompt", label, "--keep-size"]
    if dark is None:
        command.append("--single-frame")
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode not in (0, 3):
        print(f"  build failed for {label}: {result.stderr.strip()[-400:]}", file=sys.stderr)
    return result.returncode


def rewrite(arguments):
    repo, work = work_directory(arguments)
    audit_result = json.loads((work / "audit.json").read_text())
    manifest = json.loads((work / "manifest.json").read_text()) if (work / "manifest.json").exists() else {}
    edits, manual = {}, []
    for image in audit_result["images"]:
        entry = manifest.get(image["path"])
        if not entry or not entry["shipped"]:
            continue
        for reference in image.get("references", []):
            if reference["kind"] == "img-tag":
                edits.setdefault(reference["file"], []).append((image, entry, reference))
            else:
                manual.append((image, entry, reference))
    diffs = []
    for file_name, items in edits.items():
        path = repo / file_name
        original_text = path.read_text(encoding="utf-8")
        text = original_text
        jsx = path.suffix.lower() in (".jsx", ".tsx") or "className=" in text
        replacements = []
        for image, entry, reference in items:
            original_name = Path(image["path"]).name
            for match in re.finditer(r"<img\b[^>]*" + re.escape(original_name) + r"[^>]*>", text):
                tag = match.group(0)
                preceding = text[max(0, match.start() - 400):match.start()].lower()
                if preceding.rfind("<picture") > preceding.rfind("</picture>"):
                    continue
                if not re.search(r"\bsrc\s*=\s*[\"'][^\"']*" + re.escape(original_name), tag):
                    continue
                source_value = re.search(r"\bsrc\s*=\s*[\"']([^\"']*)[\"']", tag).group(1)
                directory = source_value[: len(source_value) - len(original_name)]
                line_start = text.rfind("\n", 0, match.start()) + 1
                indent = re.match(r"[ \t]*", text[line_start:match.start()]).group(0) if text[line_start:match.start()].strip() == "" else ""
                srcset = "srcSet" if jsx else "srcset"
                sources = []
                if "uhdr" in entry["shipped"]:
                    sources.append(f'{indent}  <source media="(dynamic-range: high)" {srcset}="{directory}{entry["shipped"]["uhdr"]}"{" /" if jsx else ""}>')
                if "p3" in entry["shipped"]:
                    sources.append(f'{indent}  <source media="(color-gamut: p3)" {srcset}="{directory}{entry["shipped"]["p3"]}"{" /" if jsx else ""}>')
                new_tag = tag.replace(source_value, directory + entry["fallback"], 1)
                block = "<picture>\n" + "\n".join(sources) + f"\n{indent}  {new_tag}\n{indent}</picture>"
                replacements.append((match.start(), match.end(), block))
        for start, end, block in sorted(set(replacements), reverse=True):
            text = text[:start] + block + text[end:]
        if text != original_text:
            diffs.append("".join(difflib.unified_diff(original_text.splitlines(True), text.splitlines(True), f"a/{file_name}", f"b/{file_name}")))
            if arguments.apply:
                path.write_text(text, encoding="utf-8")
    (work / "markup.patch").write_text("".join(diffs))
    lines = [f"# image-peak rewrite: {repo.name}", "", f"{'Applied' if arguments.apply else 'Patch only (not applied)'}: "
             f"{len(diffs)} files with <img> to <picture> changes. Patch: `{work / 'markup.patch'}`.", "",
             "## Handle by hand", ""]
    for image, entry, reference in manual:
        name = Path(image["path"]).name
        stem = Path(name).stem
        hint = {
            "css-url": f"add `@media (color-gamut: p3) {{ <same selector> {{ background-image: url(…/{entry['shipped'].get('p3', name)}) }} }}`"
                       + (f" and the same under `(dynamic-range: high)` with `{entry['shipped']['uhdr']}`" if "uhdr" in entry["shipped"] else ""),
            "markdown-image": "replace with the <picture> block from the image's preview folder (raw HTML) if the renderer allows it",
            "import": "render the imported image with <picture> where it is used; import the tier files beside it",
            "string": "this is data: render it with <picture> in the component that outputs it, deriving the tier names from the base name",
            "img-in-picture": "already inside a <picture>: add the <source> lines by hand",
            "img-other-attribute": "referenced from srcset or another attribute: extend that srcset by hand",
        }.get(reference["kind"], "check by hand")
        lines.append(f"- `{reference['file']}:{reference['line']}` ({reference['kind']}, `{reference['reference']}`): {hint}")
    if not manual:
        lines.append("- nothing")
    lines += ["", "## Pipeline risks", ""]
    lines += [f"- `{r['where']}`: {r['risk']}. Fix: {r['fix']}." for r in audit_result["pipeline risks"]] or ["- none found"]
    lines += ["", "## CSS to add once", "", "```css", "img { dynamic-range-limit: standard; }          /* calm HDR in grids and body copy */",
              ".lightbox img, .hero img { dynamic-range-limit: no-limit; }  /* full HDR where an image is the point */", "```"]
    (work / "rewrite.md").write_text("\n".join(lines) + "\n")
    print(f"{len(diffs)} files {'rewritten' if arguments.apply else 'in the patch'}; {len(manual)} references to handle by hand; see {work / 'rewrite.md'}")


def main(argv):
    parser = argparse.ArgumentParser(prog="image_peak.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("audit", "upgrade", "rewrite"):
        command = commands.add_parser(name)
        command.add_argument("repo")
        command.add_argument("--work")
    commands.choices["upgrade"].add_argument("--images", nargs="+")
    commands.choices["upgrade"].add_argument("--generator")
    commands.choices["upgrade"].add_argument("--plan-only", action="store_true")
    commands.choices["upgrade"].add_argument("--headroom", default="auto")
    commands.choices["rewrite"].add_argument("--apply", action="store_true")
    arguments = parser.parse_args(argv)
    {"audit": audit, "upgrade": upgrade, "rewrite": rewrite}[arguments.command](arguments)


if __name__ == "__main__":
    main(sys.argv[1:])
