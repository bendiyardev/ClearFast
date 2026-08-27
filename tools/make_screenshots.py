# -*- coding: utf-8 -*-
"""docs/img altina belgeleme icin ekran goruntuleri uretir.

Uygulama ve kurulum programi ayri islemlerde acilir (Tk tek kok destekler).
Kullanim:  py -3 tools/make_screenshots.py
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

OUT = ROOT / "docs" / "img"


# Belgeleme goruntulerinde gercek kullanici adi gorunmesin.
REAL_HOME = str(Path.home())
FAKE_HOME = str(Path(REAL_HOME).parent / "kullanici")


def mask_paths(widget) -> None:
    """Widget agacindaki metinlerde ev klasoru yolunu ornek bir adla degistirir."""
    import tkinter as tk

    for attr in ("_full_path", "_detail_full"):
        value = getattr(widget, attr, None)
        if isinstance(value, str) and REAL_HOME in value:
            setattr(widget, attr, value.replace(REAL_HOME, FAKE_HOME))

    if isinstance(widget, tk.Text):
        state = str(widget.cget("state"))
        widget.configure(state="normal")
        body = widget.get("1.0", "end-1c")
        if REAL_HOME in body:
            widget.delete("1.0", "end")
            widget.insert("1.0", body.replace(REAL_HOME, FAKE_HOME))
        widget.configure(state=state)
    else:
        try:
            text = widget.cget("text")
        except tk.TclError:
            text = None
        if isinstance(text, str) and REAL_HOME in text:
            widget.configure(text=text.replace(REAL_HOME, FAKE_HOME))

    for child in widget.winfo_children():
        mask_paths(child)


def pump(app, seconds: float) -> None:
    end = time.time() + seconds
    while time.time() < end:
        app.update()
        time.sleep(0.02)


def hwnd_of(app) -> int:
    app.update_idletasks()
    return ctypes.windll.user32.GetParent(app.winfo_id()) or app.winfo_id()


def shoot_app() -> None:
    import cf_core as core
    import cf_ui as ui
    import ClearFast
    from _shot import capture

    ui.enable_dpi_awareness()
    app = ClearFast.ClearFastApp()
    pump(app, 10)
    hwnd = hwnd_of(app)

    plan = [("system", 3), ("performance", 18), ("health", 8),
            ("cleaner", 3), ("protected", 3), ("log", 2)]
    for page, wait in plan:
        app.select_page(page)
        pump(app, wait)
        mask_paths(app)
        pump(app, 0.4)
        capture(hwnd, str(OUT / f"{page}.png"))
        print("  ", page)

    # Silme onayi: gercek secimle olusturulur.
    app.select_page("cleaner")
    pump(app, 1)
    chosen = app.cleaner_page.selection()
    total = sum(row.size for row in chosen)
    by_target: dict[str, int] = {}
    for row in chosen:
        by_target[row.target.title] = by_target.get(row.target.title, 0) + row.size
    items = tuple(f"{title} — {core.human_bytes(size)}"
                  for title, size in sorted(by_target.items(), key=lambda kv: -kv[1]))
    dialog = ui.Dialog(
        app, "Temizliği onaylayın",
        f"{len(chosen)} konumdaki yaklaşık {core.human_bytes(total)} veri kalıcı olarak "
        f"silinecek.",
        items=items[:6],
        detail="Kilitli veya erişilemeyen dosyalar atlanır. Silinen veriler Geri Dönüşüm "
               "Kutusu'na gitmez.",
        tone="danger", confirm="Temizle", confirm_variant="danger")
    pump(app, 1.2)
    mask_paths(dialog)
    pump(app, 0.3)
    capture(hwnd_of(dialog), str(OUT / "confirm.png"))
    print("   confirm")
    dialog.destroy()
    app.destroy()


def shoot_setup() -> None:
    import cf_ui as ui
    import ClearFastSetup
    from _shot import capture

    ui.enable_dpi_awareness()
    setup = ClearFastSetup.SetupApp("install")
    setup.path_var.set(setup.path_var.get().replace(REAL_HOME, FAKE_HOME))
    pump(setup, 2)
    mask_paths(setup)
    pump(setup, 0.3)
    hwnd = hwnd_of(setup)
    capture(hwnd, str(OUT / "setup-options.png"))
    print("   setup-options")

    setup._apply_progress(0.62, "Kaldırma aracı yerleştiriliyor…")
    setup.select_page("progress")
    pump(setup, 1)
    capture(hwnd, str(OUT / "setup-progress.png"))
    print("   setup-progress")

    setup._after_install(
        Path(FAKE_HOME) / "AppData" / "Local" / "Programs" / "ClearFast" / "ClearFast.exe",
        None)
    pump(setup, 1)
    capture(hwnd, str(OUT / "setup-done.png"))
    print("   setup-done")
    setup.destroy()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) > 1 and sys.argv[1] == "--setup":
        shoot_setup()
        return
    if len(sys.argv) > 1 and sys.argv[1] == "--app":
        shoot_app()
        return

    print("Uygulama ekranlari:")
    subprocess.run([sys.executable, __file__, "--app"], check=True, cwd=str(ROOT))
    print("Kurulum ekranlari:")
    subprocess.run([sys.executable, __file__, "--setup"], check=True, cwd=str(ROOT))
    total = sum(p.stat().st_size for p in OUT.glob("*.png"))
    print(f"\n{len(list(OUT.glob('*.png')))} görüntü · {total / 1048576:.1f} MB · {OUT}")


if __name__ == "__main__":
    main()
