#!/usr/bin/env python3
"""Copy Dot X logo into assets and build dotx.ico."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
LOGO = ASSETS / "logo.png"
ICON = ASSETS / "dotx.ico"

SOURCE = Path(
    r"C:\Users\Administrator\.cursor\projects\c-Users-Administrator-Projects-fivem-pc-check\assets"
    r"\c__Users_Administrator_AppData_Roaming_Cursor_User_workspaceStorage_empty-window_images_"
    r"New_Project-de85e067-0faf-45e6-b7b1-9602b1464577.png"
)


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    if not SOURCE.is_file():
        print(f"Source logo not found: {SOURCE}")
        return 1

    shutil.copy2(SOURCE, LOGO)

    try:
        from PIL import Image
    except ImportError:
        import subprocess

        subprocess.check_call([sys.executable, "-m", "pip", "install", "pillow"])
        from PIL import Image

    img = Image.open(LOGO).convert("RGBA")
    pixels = img.load()
    width, height = img.size
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if r < 40 and g < 40 and b < 40:
                pixels[x, y] = (r, g, b, 0)
    img.save(LOGO)

    img.save(
        ICON,
        format="ICO",
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
    )
    print(f"Prepared {LOGO.name} ({width}x{height}) and {ICON.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
