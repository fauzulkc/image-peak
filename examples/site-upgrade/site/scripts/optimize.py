"""Compress every JPEG in public/images."""
from pathlib import Path
from PIL import Image
for path in Path("public/images").glob("*.jpg"):
    Image.open(path).save(path, "JPEG", quality=75, optimize=True)
