# -*- coding: utf-8 -*-
"""Convert a PNG to a Windows .ico file (multi-size) for PyInstaller.

Usage:
  py scripts/make_icon_ico.py assets/gestionale.png assets/gestionale.ico

Requires:
  Pillow (pip install pillow)
"""

from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("Usage: make_icon_ico.py <input.png> <output.ico>")
        return 2

    src = Path(argv[1]).expanduser().resolve()
    dst = Path(argv[2]).expanduser().resolve()

    if not src.exists() or not src.is_file():
        print(f"Input PNG not found: {src}")
        return 2

    try:
        from PIL import Image  # type: ignore
    except Exception as exc:
        print("Pillow is required to generate .ico. Install with: pip install pillow")
        print(f"Details: {exc}")
        return 3

    dst.parent.mkdir(parents=True, exist_ok=True)

    img = Image.open(src).convert("RGBA")
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

    # Pillow will auto-resize for each size listed.
    img.save(dst, format="ICO", sizes=sizes)
    print(str(dst))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
