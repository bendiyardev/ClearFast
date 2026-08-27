# -*- coding: utf-8 -*-
"""Gelistirme yardimcisi: bir Tk penceresini acip PNG olarak yakalar.

Kullanim:  py -3 tools/_shot.py <cikti.png> [bekleme_saniye] [sayfa]
"""
from __future__ import annotations

import ctypes
import os
import sys
import time
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cf_raster  # noqa: E402


def capture(hwnd: int, out_path: str) -> tuple[int, int]:
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top

    hdc = user32.GetWindowDC(hwnd)
    mem_dc = gdi32.CreateCompatibleDC(hdc)
    bitmap = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mem_dc, bitmap)
    user32.PrintWindow(hwnd, mem_dc, 2)  # PW_RENDERFULLCONTENT

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                    ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD)]

    info = BITMAPINFOHEADER()
    info.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    info.biWidth, info.biHeight = w, -h  # negatif = ustten alta
    info.biPlanes, info.biBitCount = 1, 32
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mem_dc, bitmap, 0, h, buf, ctypes.byref(info), 0)

    surf = cf_raster.Surface(w, h)
    src = bytearray(buf.raw)
    for i in range(0, len(src), 4):
        src[i], src[i + 2] = src[i + 2], src[i]  # BGRA -> RGBA
        src[i + 3] = 255
    surf.buf = src
    with open(out_path, "wb") as fh:
        fh.write(surf.png_bytes())

    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(mem_dc)
    user32.ReleaseDC(hwnd, hdc)
    return w, h


def main() -> None:
    out = sys.argv[1]
    wait = float(sys.argv[2]) if len(sys.argv) > 2 else 6.0
    page = sys.argv[3] if len(sys.argv) > 3 else None

    import cf_ui as ui
    ui.enable_dpi_awareness()

    if os.environ.get("CF_SHOT_TARGET") == "setup":
        import ClearFastSetup
        app = ClearFastSetup.SetupApp()
    else:
        import ClearFast
        app = ClearFast.ClearFastApp()

    deadline = time.time() + wait
    while time.time() < deadline:
        app.update()
        time.sleep(0.02)
    app.update_idletasks()
    hwnd = ctypes.windll.user32.GetParent(app.winfo_id()) or app.winfo_id()

    for name in (page.split(",") if page else [None]):
        if name:
            app.select_page(name)
            for _ in range(30):
                app.update()
                time.sleep(0.02)
        target = out if not name else out.replace(".png", f"-{name}.png")
        w, h = capture(hwnd, target)
        print(f"yakalandi: {target} ({w}x{h})")
    app.destroy()


if __name__ == "__main__":
    main()
