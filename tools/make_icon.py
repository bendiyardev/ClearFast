# -*- coding: utf-8 -*-
"""assets/ClearFast.ico dosyasini uretir. Harici bagimlilik yoktur.

Kullanim:  py -3 tools/make_icon.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cf_raster import Surface, hex_rgba, sdf_round_rect, write_ico  # noqa: E402

MARK_BG = "#18181B"
MARK_FG = "#FFFFFF"
SIZES = (16, 20, 24, 32, 48, 64, 128, 256)


def sparkle_mask(cx: float, cy: float, radius: float, power: float = 0.55):
    """Dort uclu 'parilti' sekli: |x|^p + |y|^p <= r^p."""
    limit = radius ** power

    def inside(px: float, py: float) -> bool:
        return abs(px - cx) ** power + abs(py - cy) ** power <= limit

    return inside


def render(size: int) -> Surface:
    surf = Surface(size, size)
    surf.fill(sdf_round_rect(0, 0, size, size, size * 0.226), hex_rgba(MARK_BG))
    fg = hex_rgba(MARK_FG)
    ss = 4 if size <= 64 else 3
    if size <= 32:
        surf.fill_mask(sparkle_mask(size * 0.5, size * 0.5, size * 0.36), fg, ss=ss)
    else:
        surf.fill_mask(sparkle_mask(size * 0.435, size * 0.415, size * 0.30), fg, ss=ss)
        surf.fill_mask(sparkle_mask(size * 0.715, size * 0.700, size * 0.150), fg, ss=ss)
    return surf


def main() -> None:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(root, "assets")
    os.makedirs(out_dir, exist_ok=True)
    surfaces = []
    for size in SIZES:
        print(f"  {size}x{size} ...", flush=True)
        surfaces.append(render(size))
    ico = os.path.join(out_dir, "ClearFast.ico")
    write_ico(ico, surfaces)
    with open(os.path.join(out_dir, "ClearFast-256.png"), "wb") as fh:
        fh.write(surfaces[-1].png_bytes())
    print("Hazir:", ico, f"({os.path.getsize(ico)} bayt)")


if __name__ == "__main__":
    main()
