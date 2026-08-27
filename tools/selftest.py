# -*- coding: utf-8 -*-
"""ClearFast butunluk testi.

Hicbir sey kullanicinin sistemine kalici olarak dokunmaz: kurulum ve kisayol
testleri gecici bir klasorde yapilir, kayit defteri girdisi test sonunda
silinir. Zaten kurulu bir ClearFast varsa kurulum testi atlanir.

Kullanim:  py -3 tools/selftest.py
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
import traceback
import winreg
from pathlib import Path

# Turkce konsol kod sayfasi (cp1254) kutu karakterlerini kodlayamaz.
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

PASS, FAIL, SKIP = "GECTI", "KALDI", "ATLANDI"
results: list[tuple[str, str, str]] = []


def check(name: str, condition, detail: str = "") -> bool:
    state = PASS if condition else FAIL
    results.append((name, state, detail))
    print(f"  [{state:>7}] {name}" + (f"  - {detail}" if detail else ""))
    return bool(condition)


def skip(name: str, why: str) -> None:
    results.append((name, SKIP, why))
    print(f"  [{SKIP:>7}] {name}  - {why}")


def section(title: str) -> None:
    print(f"\n{title}\n" + "─" * len(title))


# --------------------------------------------------------------------------- #

def test_raster() -> None:
    section("1. Çizim katmanı (cf_raster)")
    import cf_raster as r

    surf = r.Surface(32, 32, r.hex_rgba("#FFFFFF"))
    surf.fill(r.sdf_round_rect(2, 2, 30, 30, 8), r.hex_rgba("#18181B"))
    png = surf.png_bytes()
    check("PNG imzası doğru", png[:8] == b"\x89PNG\r\n\x1a\n")
    check("PNG boyutu makul", 100 < len(png) < 5000, f"{len(png)} bayt")

    corner = surf.buf[0:4]
    center = surf.buf[(16 * 32 + 16) * 4:(16 * 32 + 16) * 4 + 4]
    check("Köşe boş, merkez dolu", tuple(corner[:3]) == (255, 255, 255)
          and tuple(center[:3]) == (24, 24, 27))

    ico = ROOT / "assets" / "ClearFast.ico"
    check("Uygulama simgesi var", ico.exists() and ico.stat().st_size > 1000,
          f"{ico.stat().st_size} bayt" if ico.exists() else "yok")


def test_core() -> None:
    section("2. Çekirdek mantık (cf_core)")
    import cf_core as core

    targets = core.targets()
    check("Hedef listesi dolu", len(targets) >= 25, f"{len(targets)} hedef")
    check("Anahtarlar benzersiz", len({t.key for t in targets}) == len(targets))
    check("Tüm kategoriler tanımlı",
          all(t.category in core.CATEGORY_ORDER for t in targets))
    check("Her hedefin açıklaması var", all(len(t.description) > 20 for t in targets))
    risky = [t for t in targets if not t.default_selected and t.risk != "Opsiyonel"]
    check("Seçili olmayanlar 'Opsiyonel' işaretli", not risky,
          ", ".join(t.key for t in risky) if risky else "")

    check("Eksik ortam değişkeni güvenli", "__CLEARFAST_ENV_MISSING" in
          str(core.env_path("KESINLIKLE_OLMAYAN_DEGISKEN_X9")))
    check("Boyut biçimi Türkçe", core.human_bytes(1536 * 1024 * 1024) == "1,50 GB",
          core.human_bytes(1536 * 1024 * 1024))

    # Ad eslesmeli tarama uygulama kokunu asla dondurmemeli.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "SahteUygulama"
        (root / "Cache" / "alt").mkdir(parents=True)
        (root / "Cache" / "alt" / "x.bin").write_bytes(b"x" * 100)
        (root / "User Data" / "onemli").mkdir(parents=True)
        (root / "User Data" / "onemli" / "sifreler.db").write_bytes(b"gizli")
        (root / "pip" / "cache").mkdir(parents=True)
        found = core.chromium_caches([root])
        check("Yalnızca önbellek klasörü eşleşti", found == [root / "Cache"],
              str([p.name for p in found]))
        check("Uygulama kökü hedeflenmedi", root not in found)
        check("Kullanıcı verisi hedeflenmedi",
              not any("User Data" in str(p) for p in found))
        check("Paket yöneticisi klasörü atlandı",
              not any("pip" in str(p) for p in found))

    rows = core.scan_targets(targets)
    groups = core.group_rows(rows)
    check("Tarama sonuç üretti", len(rows) > 0, f"{len(rows)} klasör")
    check("Gruplama tutarlı", sum(len(g.rows) for g in groups) == len(rows),
          f"{len(groups)} kaynak")


def test_deletion_safety() -> None:
    section("3. Silme güvenliği (delete_contents)")
    import cf_core as core

    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp) / "onbellek"
        (folder / "alt").mkdir(parents=True)
        (folder / "a.txt").write_text("x" * 500)
        (folder / "alt" / "b.txt").write_text("y" * 500)
        locked_path = folder / "kilitli.bin"
        locked_path.write_bytes(b"z" * 100)

        locked = open(locked_path, "rb")            # dosyayi kilitli tut
        try:
            deleted, freed, errors = core.delete_contents(folder)
        finally:
            locked.close()

        check("Klasörün kendisi duruyor", folder.exists())
        check("İçerik silindi", not (folder / "a.txt").exists()
              and not (folder / "alt").exists())
        check("Kazanılan alan raporlandı", freed >= 1000, f"{freed} bayt")
        check("Silinen öğe sayıldı", deleted >= 2, str(deleted))
        # Windows acik dosyayi silmeye izin verebilir; ikisi de kabul edilir,
        # onemli olan hatanin islemi durdurmamasi.
        check("Kilitli dosya işlemi durdurmadı", isinstance(errors, list))

        core.delete_contents(Path(tmp) / "hic_olmayan")
        check("Var olmayan yol hata vermiyor", True)


def test_metrics() -> None:
    section("4. Ölçümler (cf_metrics)")
    import cf_metrics as m

    cpu = m.CpuMonitor()
    check("İlk örnek referans", cpu.sample() is None)
    time.sleep(1.0)
    value = cpu.sample()
    check("İşlemci yüzdesi okundu", value is not None and 0 <= value <= 100,
          f"%{value:.1f}" if value is not None else "okunamadı")

    procs = m.ProcessMonitor()
    procs.sample()
    time.sleep(1.0)
    rows = procs.sample()
    check("Süreç listesi alındı", len(rows) > 10, f"{len(rows)} grup")
    check("Süreçler ada göre gruplandı", all("name" in r and "count" in r for r in rows))
    check("Bellek değerleri makul", all(r["ram"] >= 0 for r in rows))

    total, avail = m.CpuMonitor().cores, None
    import cf_core as core
    total_ram, avail_ram = core.memory_info()
    check("Fiziksel bellek okundu", total_ram > 0,
          core.human_bytes(total_ram))
    check("Boş bellek tutarlı", 0 < avail_ram <= total_ram)

    modules = m.memory_modules()
    check("Bellek modülleri okundu", len(modules) > 0,
          f"{len(modules)} modül" if modules else "okunamadı")
    if modules:
        check("Modül kapasiteleri geçerli", all(x["capacity"] > 0 for x in modules))

    specs = m.full_specs()
    check("Sistem künyesi okundu", bool(specs.get("cpu_name")),
          specs.get("cpu_name", "")[:40])
    check("Çekirdek sayısı geçerli", int(specs.get("cpu_threads") or 0) > 0)

    gpus = m.gpu_status()
    if gpus:
        check("Ekran kartı ölçümü", gpus[0]["load"] is not None,
              f"{gpus[0]['name']} %{gpus[0]['load']:.0f}")
    else:
        skip("Ekran kartı ölçümü", "nvidia-smi yok")

    rel, note = m.storage_reliability()
    if rel:
        check("Disk aşınma sayaçları", True, f"{len(rel)} disk")
    else:
        skip("Disk aşınma sayaçları", note or "okunamadı")


def test_win() -> None:
    section("5. Windows arayüzü (cf_win)")
    import cf_win

    desktop = cf_win.known_folder(cf_win.FOLDERID_Desktop)
    programs = cf_win.known_folder(cf_win.FOLDERID_Programs)
    check("Masaüstü yolu bulundu", desktop is not None and desktop.exists(), str(desktop))
    check("Başlat menüsü bulundu", programs is not None and programs.exists())

    mine = cf_win.running_pids(Path(sys.executable).name)
    check("Süreç arama çalışıyor", os.getpid() in mine or len(mine) > 0)
    check("Kendini hariç tutma", os.getpid() not in
          cf_win.running_pids(Path(sys.executable).name, exclude_pid=os.getpid()))

    with tempfile.TemporaryDirectory() as tmp:
        link = Path(tmp) / "test.lnk"
        target = ROOT / "dist" / "ClearFast" / "ClearFast.exe"
        if not target.exists():
            skip("Kısayol oluşturma", "önce Build.bat çalıştırın")
            return
        ok = cf_win.create_shortcut(link, target, description="Test",
                                    working_dir=target.parent, icon=target)
        check("Kısayol oluşturuldu", ok and link.stat().st_size > 500,
              f"{link.stat().st_size} bayt" if ok else "")
        raw = link.read_bytes()
        check("Kısayol hedefi doğru", b"C\x00l\x00e\x00a\x00r\x00F\x00a\x00s\x00t" in raw
              or b"ClearFast" in raw)


def test_installer() -> None:
    section("6. Kurulum ve kaldırma")
    import ClearFastSetup as st

    if st.read_installed() is not None:
        skip("Kurulum turu", "sistemde zaten kurulu bir ClearFast var")
        return
    source = st.program_dir()
    if not (source / st.EXE_NAME).exists():
        skip("Kurulum turu", "önce Build.bat çalıştırın")
        return

    tmp = Path(tempfile.mkdtemp(prefix="clearfast-test-"))
    target = tmp / "ClearFast"
    try:
        steps = []
        t0 = time.time()
        exe = st.install(target, desktop_shortcut=False, menu_shortcut=False,
                         report=lambda r, t: steps.append(t))
        check("Kurulum tamamlandı", exe.exists(), f"{time.time() - t0:.1f} sn")
        files = sum(1 for _ in target.rglob("*") if _.is_file())
        check("Dosyalar kopyalandı", files > 100, f"{files} dosya")
        check("Çalışma zamanı yanında", (target / "_internal").is_dir())

        info = st.read_installed()
        check("Sistem kaydı yazıldı", info and info["location"] == str(target))
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, st.REG_KEY) as key:
            uninstall_cmd = winreg.QueryValueEx(key, "UninstallString")[0]
        check("Kaldırma komutu doğru", uninstall_cmd.endswith("--uninstall")
              and str(target) in uninstall_cmd)

        # Kaynak ile hedef ayni klasor oldugunda kurulum reddedilmeli.
        # (Koruma, hicbir dosya islemi yapilmadan once devreye girer.)
        try:
            st.install(source, False, False, lambda r, t: None)
            check("Aynı klasöre kurma engellendi", False, "engellenmedi")
        except RuntimeError:
            check("Aynı klasöre kurma engellendi", True)

        st.uninstall(target, report=lambda r, t: None)
        check("Sistem kaydı silindi", st.read_installed() is None)
        remaining = list(target.rglob("*")) if target.exists() else []
        check("Dosyalar kaldırıldı", not remaining, f"{len(remaining)} dosya kaldı")
    finally:
        st.delete_registry()
        shutil.rmtree(tmp, ignore_errors=True)


def test_ui() -> None:
    section("7. Arayüz (tüm sayfalar)")
    import tkinter as tk

    import cf_core as core
    import cf_ui as ui
    import ClearFast

    errors: list[str] = []
    ui.enable_dpi_awareness()
    app = ClearFast.ClearFastApp()
    app.report_callback_exception = lambda *a: errors.append(
        "".join(traceback.format_exception(*a)))

    def pump(seconds: float) -> None:
        end = time.time() + seconds
        while time.time() < end:
            app.update()
            time.sleep(0.02)

    pump(10)
    check("Pencere açıldı", app.winfo_width() > 500,
          f"{app.winfo_width()}x{app.winfo_height()}")
    check("Tarama tamamlandı", len(app.cleaner_page.groups) > 0,
          f"{len(app.cleaner_page.groups)} kaynak")
    check("Sistem bilgisi geldi", bool(app.specs.get("cpu_name")))

    for page in ("system", "performance", "health", "cleaner", "protected", "log"):
        app.select_page(page)
        pump(2.5)
        check(f"Sayfa açıldı: {page}", app.pages[page].winfo_ismapped())

    app.select_page("cleaner")
    pump(1)
    before = len(app.cleaner_page.checked)
    app.cleaner_page.clear_selection()
    check("Seçim temizlendi", not app.cleaner_page.checked)
    app.cleaner_page.select_safe()
    check("Güvenli seçim geri geldi", len(app.cleaner_page.checked) == before)

    optional = [k for k, g in app.cleaner_page.groups.items()
                if not g.target.default_selected]
    if optional:
        app.cleaner_page.rows[optional[0]]._click()
        pump(0.5)
        check("Opsiyonel uyarısı belirdi",
              bool(app.cleaner_page.alert_optional.winfo_manager()))
        app.cleaner_page.rows[optional[0]]._click()
        pump(0.5)
        check("Uyarı geri kayboldu",
              not app.cleaner_page.alert_optional.winfo_manager())

    dialog = ui.Dialog(app, "Test", "Onay penceresi", items=("bir", "iki"),
                       tone="danger", confirm="Sil", confirm_variant="danger")
    pump(0.8)
    check("Onay penceresi çizildi", dialog.winfo_width() > 300,
          f"{dialog.winfo_width()}x{dialog.winfo_height()}")
    dialog.destroy()

    links = []

    def collect(widget):
        if isinstance(widget, ui.IconButton):
            links.append(widget)
        for child in widget.winfo_children():
            collect(child)

    collect(app)
    check("İletişim bağlantıları yerinde", len(links) == len(ui.CONTACT_LINKS),
          f"{len(links)} bağlantı")

    pump(1)
    app.destroy()
    check("Arayüz hatası yok", not errors, errors[0][:120] if errors else "")


def main() -> None:
    print("ClearFast bütünlük testi")
    print("=" * 60)
    tests = [test_raster, test_core, test_deletion_safety, test_metrics,
             test_win, test_installer, test_ui]
    for test in tests:
        try:
            test()
        except Exception:
            results.append((test.__name__, FAIL, "istisna"))
            print(f"  [{FAIL:>7}] {test.__name__} sırasında istisna:")
            traceback.print_exc()

    passed = sum(1 for _, s, _ in results if s == PASS)
    failed = sum(1 for _, s, _ in results if s == FAIL)
    skipped = sum(1 for _, s, _ in results if s == SKIP)
    print("\n" + "=" * 60)
    print(f"SONUC:  {passed} gecti | {failed} kaldi | {skipped} atlandi")
    if failed:
        print("\nBaşarısız olanlar:")
        for name, state, detail in results:
            if state == FAIL:
                print(f"  - {name}  {detail}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
