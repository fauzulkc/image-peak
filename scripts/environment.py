"""Self-installing runtime for true-image. Standard library only, so any Python 3.8+ can start it.

ensure_environment(): if the image libraries are importable, return. Otherwise create (or repair) the
environment at TRUE_IMAGE_VENV (default ~/.venvs/true-image), install requirements.txt into it, and run
the same command again inside it. Nobody has to install anything by hand, whichever agent or person
calls true-image, on macOS, Linux, WSL or Windows.

Creation order: the stdlib venv module; then uv (which also fetches a suitable Python when the local one
is too old); then virtualenv installed with pip --user. The first that works wins.
"""
import os, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = ROOT / "requirements.txt"
MINIMUM_PYTHON = (3, 10)


def environment_directory():
    return Path(os.environ.get("TRUE_IMAGE_VENV", Path.home() / ".venvs" / "true-image")).expanduser()


def environment_python(directory):
    return directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def libraries_ready():
    try:
        import cv2, imagecodecs, numpy, PIL  # noqa: F401
        return bool(imagecodecs.ULTRAHDR.available)
    except Exception:
        return False


def runs(command):
    try:
        return subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    except OSError:
        return False


def say(message):
    print(f"true-image: {message}", file=sys.stderr, flush=True)


def create(directory, python):
    if runs([str(python), "-c", "import sys; sys.exit(sys.version_info < (3, 10))"]):
        return True
    if directory.exists():
        shutil.rmtree(directory, ignore_errors=True)  # broken or too old: start clean
    directory.parent.mkdir(parents=True, exist_ok=True)
    if sys.version_info >= MINIMUM_PYTHON and runs([sys.executable, "-m", "venv", str(directory)]) and runs([str(python), "-m", "pip", "--version"]):
        return True
    uv = shutil.which("uv")
    if uv and runs([uv, "venv", "--python", "3.12", str(directory)]):
        return True
    if sys.version_info >= MINIMUM_PYTHON and (runs([sys.executable, "-m", "virtualenv", str(directory)]) or (
            runs([sys.executable, "-m", "pip", "install", "--user", "--quiet", "virtualenv"])
            and runs([sys.executable, "-m", "virtualenv", str(directory)]))):
        return True
    return False


def install(directory, python):
    if runs([str(python), "-m", "pip", "--version"]):
        runs([str(python), "-m", "pip", "install", "--quiet", "--upgrade", "pip"])
        command = [str(python), "-m", "pip", "install", "--quiet", "--upgrade", "-r", str(REQUIREMENTS)]
    elif shutil.which("uv"):
        command = [shutil.which("uv"), "pip", "install", "--quiet", "--python", str(python), "-r", str(REQUIREMENTS)]
    else:
        return False
    return subprocess.run(command, stdout=sys.stderr).returncode == 0


def ensure_environment():
    """Return when the libraries import; otherwise set up and re-run this command inside the environment."""
    if libraries_ready():
        return
    directory = environment_directory()
    python = environment_python(directory)
    if not os.environ.get("TRUE_IMAGE_BOOTSTRAPPED") and runs(
            [str(python), "-c", "import cv2, imagecodecs, numpy, PIL, sys; sys.exit(not imagecodecs.ULTRAHDR.available)"]):
        handover(python)  # set up on an earlier run: hand over without touching pip
    if os.environ.get("TRUE_IMAGE_BOOTSTRAPPED"):
        sys.exit("true-image: the environment was set up but the image libraries still do not import. "
                 f"Delete {directory} and run again, or see docs/getting-started.md#troubleshooting")
    say(f"first run: setting up {directory} (about a minute, once)")
    if not create(directory, python):
        sys.exit("true-image: could not create a Python 3.10+ environment. Install one of: Python 3.10+ with venv "
                 "(Debian/Ubuntu: sudo apt install python3-venv), or uv (https://docs.astral.sh/uv/)")
    if not install(directory, python):
        sys.exit(f"true-image: installing {REQUIREMENTS.name} into {directory} failed (see the pip output above)")
    say("ready")
    handover(python)


def handover(python):
    """Run this same command inside the environment and exit with its status."""
    environment = dict(os.environ, TRUE_IMAGE_BOOTSTRAPPED="1")
    sys.exit(subprocess.run([str(python), "-I", *sys.argv], env=environment).returncode)


def doctor():
    """Print what true-image will use: the environment, the libraries, and the generator CLIs found."""
    import cv2, imagecodecs, numpy, PIL
    print(f"python       {sys.version.split()[0]} at {sys.executable}")
    print(f"libraries    numpy {numpy.__version__}, opencv {cv2.__version__}, pillow {PIL.__version__}, "
          f"imagecodecs {imagecodecs.__version__} ({imagecodecs.ultrahdr_version()})")
    print(f"bash         {shutil.which('bash') or 'not found: the bundled cursor/agy adapters need bash; plan/build and Python adapters do not'}")
    search_path = os.pathsep.join([str(Path.home() / ".local" / "bin"), os.environ.get("PATH", "")])
    for name, command in (("cursor", "agent"), ("agy", "agy")):
        found = shutil.which(command, path=search_path)
        print(f"generator    {name:7} {'found at ' + found if found else 'not installed (optional)'}")
    print("status       ready")
