"""One prompt in, three verified delivery tiers out (Ultra HDR, P3 SDR, sRGB SDR), with any image generator.

Subcommands (run inside WSL with ~/.venvs/image-peak/bin/python):

  plan  "<scene prompt>" --slug NAME --out DIR [--no-people] [--aspect 3:2]
        Writes DIR/NAME/plan.json and prints the two generator-neutral prompts and where each frame goes.
        Use this when an agent generates the frames with its own tool (an MCP image tool, a harness's
        built-in image tool): generate the base, save it to the printed path, then run the dark edit on
        that saved base and save it too.

  generate --slug NAME --out DIR --generator ADAPTER [--stronger]
        Runs an adapter for any frame still missing. ADAPTER is a bundled name (cursor, agy) or a path to
        any executable that follows the adapter contract (see SKILL.md).

  build --slug NAME --out DIR [--headroom auto|N]
        Builds and verifies the tiers from whatever frames exist. Exit 3 = regenerate the dark edit with
        the stronger prompt (generate --stronger, or the agent re-runs plan.json's dark_prompt_stronger).
        With no dark frame it builds from the base alone (single-frame mode, for text-only generators).

  run   "<scene prompt>" --slug NAME --out DIR --generator ADAPTER [...]
        plan + generate + build, regenerating the dark edit once if it recovered too little.

  audit | upgrade | rewrite  REPO [...]
        Upgrade an existing site or repo's images in place (see site_upgrade.py).
"""
import argparse, json, subprocess, sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent

# Existing sites and repos: audit, upgrade, rewrite (see site_upgrade.py).
if len(sys.argv) > 1 and sys.argv[1] in ("audit", "upgrade", "rewrite"):
    sys.path.insert(0, str(SCRIPTS))
    import site_upgrade
    site_upgrade.main(sys.argv[1:])
    sys.exit(0)
ADAPTERS = SCRIPTS / "generators"
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")


def scene_folder(arguments):
    folder = Path(arguments.out).expanduser().resolve() / arguments.slug
    (folder / "frames").mkdir(parents=True, exist_ok=True)
    return folder


def find_frame(folder, slug, role):
    for suffix in IMAGE_SUFFIXES:
        candidate = folder / "frames" / f"{slug}.{role}{suffix}"
        if candidate.exists() and candidate.stat().st_size > 0:
            return candidate
    return None


def make_plan(arguments):
    folder = scene_folder(arguments)
    constraints = "No text, no lettering, no signs with words, no logos, no watermarks." + (" No people." if arguments.no_people else "")
    base_prompt = (f"{arguments.prompt}. A real, unedited camera photograph on a tripod, exposed for the midtones so the "
                   "scene reads naturally; the brightest light sources, sky, snow or reflections may clip to white. "
                   f"Natural lens and grain, no HDR look, no tone mapping. {constraints} Landscape {arguments.aspect}.")

    def dark_prompt(stops):
        return ("Edit the input image. Output the same frame at the same size with identical framing, camera position and "
                "every object, light and reflection in exactly the same place; it is the next frame of a tripod exposure "
                f"bracket. Change only the exposure: {stops} darker, so everything that was white in the input (light "
                "sources, fire, sky, snow, reflections) shows its full colour and texture with nothing clipped anywhere, "
                "while midtones and shadows fall towards black. Keep the same moment, weather and colours; do not add, "
                f"remove or move anything. Real camera photograph, natural grain, no tone mapping. {constraints}")

    plan = {
        "slug": arguments.slug,
        "scene prompt": arguments.prompt,
        "base_prompt": base_prompt,
        "base_path": str(folder / "frames" / f"{arguments.slug}.base.jpg"),
        "dark_prompt": dark_prompt("about 4 stops"),
        "dark_prompt_stronger": dark_prompt("5 to 6 stops"),
        "dark_path": str(folder / "frames" / f"{arguments.slug}.dark.jpg"),
        "dark_input": "the saved base image (an edit of it, not a new generation)",
        "build": f"build --slug {arguments.slug} --out {arguments.out}",
    }
    (folder / "plan.json").write_text(json.dumps(plan, indent=2))
    return folder, plan


def resolve_adapter(name):
    bundled = ADAPTERS / f"{name}.sh"
    if bundled.exists():
        return ["bash", str(bundled)]
    path = Path(name).expanduser()
    if path.exists():
        return ["bash", str(path)] if path.suffix == ".sh" else [str(path)]
    sys.exit(f"FAIL: no adapter '{name}' (bundled: {', '.join(p.stem for p in ADAPTERS.glob('*.sh'))}, or pass a path)")


def run_adapter(adapter, mode, prompt, output_path, input_image=None):
    prompt_file = output_path.with_suffix(".prompt.txt")
    prompt_file.write_text(prompt)
    command = adapter + [mode, str(prompt_file), str(output_path)] + ([str(input_image)] if input_image else [])
    for attempt in (1, 2):
        result = subprocess.run(command, capture_output=True, text=True, timeout=900)
        if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
            return
        print(f"  adapter {mode} attempt {attempt} failed (exit {result.returncode}):\n{result.stdout[-500:]}{result.stderr[-500:]}", file=sys.stderr)
    sys.exit(f"FAIL: the generator did not produce {output_path.name}")


def generate(arguments, plan, folder, stronger=False):
    adapter = resolve_adapter(arguments.generator)
    base = find_frame(folder, arguments.slug, "base")
    if base is None:
        print(f"generating the base photo ({arguments.generator})")
        base = Path(plan["base_path"])
        run_adapter(adapter, "create", plan["base_prompt"], base)
    dark = find_frame(folder, arguments.slug, "dark")
    if dark is None or stronger:
        print(f"generating the darker edit of that same frame ({arguments.generator}{', stronger' if stronger else ''})")
        run_adapter(adapter, "edit", plan["dark_prompt_stronger" if stronger else "dark_prompt"], Path(plan["dark_path"]), base)


def build(arguments, folder):
    base = find_frame(folder, arguments.slug, "base")
    if base is None:
        sys.exit(f"FAIL: no base frame in {folder / 'frames'} (expected {arguments.slug}.base.jpg/.png/.webp)")
    dark = find_frame(folder, arguments.slug, "dark")
    plan_file = folder / "plan.json"
    prompt = json.loads(plan_file.read_text())["scene prompt"] if plan_file.exists() else ""
    command = [sys.executable, str(SCRIPTS / "build_tiers.py"), str(base), str(dark or base), str(folder),
               "--slug", arguments.slug, "--headroom", arguments.headroom, "--prompt", prompt]
    if dark is None:
        command.append("--single-frame")
    return subprocess.run(command).returncode


parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
commands = parser.add_subparsers(dest="command", required=True)
for name in ("plan", "run"):
    command = commands.add_parser(name)
    command.add_argument("prompt")
    command.add_argument("--no-people", action="store_true")
    command.add_argument("--aspect", default="3:2")
for name in ("plan", "generate", "build", "run"):
    command = commands.choices[name] if name in commands.choices else commands.add_parser(name)
    command.add_argument("--slug", required=True)
    command.add_argument("--out", required=True)
    if name in ("generate", "run"):
        command.add_argument("--generator", required=True)
    if name == "generate":
        command.add_argument("--stronger", action="store_true")
    if name in ("build", "run"):
        command.add_argument("--headroom", default="auto")
arguments = parser.parse_args()

if arguments.command == "plan":
    folder, plan = make_plan(arguments)
    print(json.dumps(plan, indent=2))
elif arguments.command == "generate":
    folder = scene_folder(arguments)
    generate(arguments, json.loads((folder / "plan.json").read_text()), folder, stronger=arguments.stronger)
elif arguments.command == "build":
    sys.exit(build(arguments, scene_folder(arguments)))
else:  # run
    folder, plan = make_plan(arguments)
    generate(arguments, plan, folder)
    code = build(arguments, folder)
    if code == 3:
        print("the dark edit recovered too little; regenerating it once, stronger")
        generate(arguments, plan, folder, stronger=True)
        code = build(arguments, folder)
    if code == 0:
        print(f"\nOK  {folder}\n    {arguments.slug}.uhdr.jpg  {arguments.slug}.p3.jpg  {arguments.slug}.sdr.jpg  "
              f"{arguments.slug}.picture.html  preview.html")
    sys.exit(code)
