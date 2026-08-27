# -*- coding: utf-8 -*-
"""ClearFast kurulum ve kaldirma sihirbazi.

Ayri bir kurucu ikili YOKTUR: bu modul, ClearFast.exe --setup ile ayni
programin bir kipi olarak calisir ve icinde gomulu bir EXE tasimaz.
Kurulum, programin bulundugu klasorun hedefe kopyalanmasidir. Bu sayede
"kendi icinden EXE cikaran program" (dropper) kalibi hic olusmaz.

Yonetici yetkisi gerektirmeyen, kullanici bazli kurulum:
  %LOCALAPPDATA%\\Programs\\ClearFast

  ClearFast.exe --setup      kurulum
  ClearFast.exe --uninstall  kaldirma
"""
from __future__ import annotations

import os
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import winreg
from pathlib import Path

import cf_ui as ui
from cf_ui import px

APP_NAME = "ClearFast"
APP_VERSION = "0.3.1"
APP_PUBLISHER = "ClearFast"
EXE_NAME = "ClearFast.exe"
REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\ClearFast"

CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008

WINDOW_W, WINDOW_H = 700, 556
HERO_W = 240


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


def program_dir() -> Path:
    """Kurulacak icerigin bulundugu klasor: programin kendi klasoru."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # Kaynaktan calistirilirken derlenmis klasor kullanilir.
    return Path(__file__).resolve().parent / "dist" / APP_NAME


def program_size(folder: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(folder):
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                continue
    return total


def same_folder(a: Path, b: Path) -> bool:
    try:
        return a.resolve().samefile(b.resolve())
    except OSError:
        return str(a).rstrip("\\").lower() == str(b).rstrip("\\").lower()


def default_install_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "Programs" / APP_NAME


def run_ps(script: str, timeout: int = 20) -> str:
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=timeout,
            creationflags=CREATE_NO_WINDOW, encoding="utf-8", errors="replace")
        return result.stdout.strip()
    except Exception:
        return ""


def shell_folders() -> dict[str, Path | None]:
    """Masaustu ve Baslat menusu yollari (OneDrive yonlendirmesini de dogru alir)."""
    out = run_ps("[Environment]::GetFolderPath('Desktop'); "
                 "[Environment]::GetFolderPath('Programs')")
    lines = [line.strip() for line in out.splitlines() if line.strip()]
    desktop = Path(lines[0]) if len(lines) > 0 else None
    programs = Path(lines[1]) if len(lines) > 1 else None
    if desktop is None:
        candidate = Path.home() / "Desktop"
        desktop = candidate if candidate.exists() else None
    return {"desktop": desktop, "programs": programs}


def ps_quote(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def make_shortcut(link: Path, target: Path, description: str) -> bool:
    link.parent.mkdir(parents=True, exist_ok=True)
    script = (
        f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut({ps_quote(link)}); "
        f"$s.TargetPath = {ps_quote(target)}; "
        f"$s.WorkingDirectory = {ps_quote(target.parent)}; "
        f"$s.IconLocation = {ps_quote(str(target) + ',0')}; "
        f"$s.Description = {ps_quote(description)}; "
        f"$s.Save()")
    run_ps(script)
    return link.exists()


def app_is_running() -> bool:
    """Baska bir ClearFast penceresi acik mi? Kurulum kipinin kendisi sayilmaz."""
    out = run_ps(f"@(Get-Process -Name '{Path(EXE_NAME).stem}' -ErrorAction "
                 f"SilentlyContinue | Where-Object {{ $_.Id -ne {os.getpid()} }}).Count",
                 timeout=12)
    return out.strip().isdigit() and int(out.strip()) > 0


def human_bytes(value: int) -> str:
    size = float(max(0, value))
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            text = f"{size:.0f}" if unit in ("B", "KB") else f"{size:.1f}".replace(".", ",")
            return f"{text} {unit}"
        size /= 1024
    return f"{value} B"


# --------------------------------------------------------------------------- #
# Kurulum / kaldirma islemleri
# --------------------------------------------------------------------------- #

def read_installed() -> dict | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY) as key:
            def value(name: str) -> str:
                try:
                    return str(winreg.QueryValueEx(key, name)[0])
                except OSError:
                    return ""
            return {"location": value("InstallLocation"), "version": value("DisplayVersion")}
    except OSError:
        return None


def write_registry(install_dir: Path, size_bytes: int) -> None:
    exe = install_dir / EXE_NAME
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_WRITE) as key:
        def put(name: str, value, kind=winreg.REG_SZ) -> None:
            winreg.SetValueEx(key, name, 0, kind, value)

        put("DisplayName", APP_NAME)
        put("DisplayVersion", APP_VERSION)
        put("Publisher", APP_PUBLISHER)
        put("DisplayIcon", f"{exe},0")
        put("InstallLocation", str(install_dir))
        put("UninstallString", f'"{exe}" --uninstall')
        put("QuietUninstallString", f'"{exe}" --uninstall --silent')
        put("EstimatedSize", max(1, size_bytes // 1024), winreg.REG_DWORD)
        put("NoModify", 1, winreg.REG_DWORD)
        put("NoRepair", 1, winreg.REG_DWORD)


def delete_registry() -> None:
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, REG_KEY)
    except OSError:
        pass


def install(install_dir: Path, desktop_shortcut: bool, menu_shortcut: bool, report) -> Path:
    """Programin klasorunu hedefe kopyalar; ilerlemeyi report(oran, metin) bildirir."""
    source = program_dir()
    if not (source / EXE_NAME).exists():
        raise FileNotFoundError(
            f"Kaynak klasörde {EXE_NAME} bulunamadı: {source}\n"
            "ZIP arşivini tamamen çıkardığınızdan emin olun.")
    if same_folder(source, install_dir):
        raise RuntimeError("ClearFast zaten bu klasörde çalışıyor. "
                           "Kurulum için farklı bir hedef seçin.")

    report(0.08, "Önceki sürüm denetleniyor…")
    if app_is_running():
        raise RuntimeError("ClearFast şu anda çalışıyor. Kapatıp kurulumu yeniden başlatın.")

    report(0.22, "Klasör hazırlanıyor…")
    install_dir.mkdir(parents=True, exist_ok=True)

    report(0.40, "Dosyalar kopyalanıyor…")
    shutil.copytree(source, install_dir, dirs_exist_ok=True)
    target = install_dir / EXE_NAME

    report(0.76, "Kısayollar oluşturuluyor…")
    folders = shell_folders()
    if menu_shortcut and folders["programs"]:
        make_shortcut(folders["programs"] / f"{APP_NAME}.lnk", target,
                      "Windows temizlik ve sistem durumu aracı")
    if desktop_shortcut and folders["desktop"]:
        make_shortcut(folders["desktop"] / f"{APP_NAME}.lnk", target,
                      "Windows temizlik ve sistem durumu aracı")

    report(0.92, "Sistem kaydı yazılıyor…")
    write_registry(install_dir, program_size(install_dir))

    report(1.0, "Tamamlandı")
    return target


def uninstall(install_dir: Path, report) -> None:
    report(0.15, "Uygulama durumu denetleniyor…")
    if app_is_running():
        raise RuntimeError("ClearFast şu anda çalışıyor. Kapatıp kaldırmayı yeniden deneyin.")

    report(0.40, "Kısayollar siliniyor…")
    folders = shell_folders()
    for folder in (folders["desktop"], folders["programs"]):
        if not folder:
            continue
        link = folder / f"{APP_NAME}.lnk"
        try:
            link.unlink(missing_ok=True)
        except OSError:
            pass

    report(0.70, "Sistem kaydı siliniyor…")
    delete_registry()

    report(0.90, "Dosyalar kaldırılıyor…")
    # Kaldirici kendi klasorunun icinde oldugu icin silme islemi cikistan sonraya birakilir.
    subprocess.Popen(
        f'cmd /c ping 127.0.0.1 -n 3 >nul & rmdir /s /q "{install_dir}"',
        creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW, close_fds=True)
    report(1.0, "Tamamlandı")


# --------------------------------------------------------------------------- #
# Arayuz
# --------------------------------------------------------------------------- #

class SetupApp(tk.Tk):
    def __init__(self, mode: str = "install") -> None:
        super().__init__()
        ui.init(self)
        ui.apply_ttk_theme(self)
        self.mode = mode
        self.title(f"{APP_NAME} Kurulumu" if mode == "install" else f"{APP_NAME} Kaldırma")
        self.geometry(f"{px(WINDOW_W)}x{px(WINDOW_H)}")
        self.resizable(False, False)
        self.configure(bg=ui.CARD)
        self._set_icon()

        self.results: queue.Queue = queue.Queue()
        self.existing = read_installed()
        start_dir = (self.existing or {}).get("location") or str(default_install_dir())
        self.path_var = tk.StringVar(value=start_dir)
        self.launch_after = True
        self.error: str | None = None
        self.installed_exe: Path | None = None

        self._build()
        self.select_page("options")
        self._pump()
        self._center()

    def _set_icon(self) -> None:
        ico = resource_path("assets/ClearFast.ico")
        try:
            if ico.exists():
                self.iconbitmap(default=str(ico))
                return
        except tk.TclError:
            pass
        try:
            self.iconphoto(True, ui.app_mark(px(64), ui.CARD))
        except tk.TclError:
            pass

    def _center(self) -> None:
        self.update_idletasks()
        w, h = px(WINDOW_W), px(WINDOW_H)
        x = (self.winfo_screenwidth() - w) // 2
        y = max(0, (self.winfo_screenheight() - h) // 2 - px(30))
        self.geometry(f"{w}x{h}+{x}+{y}")

    # -- iskelet ------------------------------------------------------------- #
    def _build(self) -> None:
        hero = tk.Frame(self, bg=ui.PRIMARY, width=px(HERO_W))
        hero.pack(side="left", fill="y")
        hero.pack_propagate(False)

        top = tk.Frame(hero, bg=ui.PRIMARY)
        top.pack(fill="x", padx=px(28), pady=(px(34), 0))
        tk.Label(top, image=ui.sparkle_mark(px(44), "#FFFFFF", ui.PRIMARY),
                 bg=ui.PRIMARY).pack(anchor="w")
        tk.Label(top, text=APP_NAME, font=ui.fonts["display"], fg="#FFFFFF",
                 bg=ui.PRIMARY, anchor="w").pack(fill="x", pady=(px(14), 0))
        tk.Label(top, text=f"Sürüm {APP_VERSION}", font=ui.fonts["small"], fg="#8B8B93",
                 bg=ui.PRIMARY, anchor="w").pack(fill="x", pady=(px(2), 0))

        steps = tk.Frame(hero, bg=ui.PRIMARY)
        steps.pack(fill="x", padx=px(28), pady=(px(34), 0))
        labels = (("options", "Seçenekler"), ("progress", "Kurulum"), ("done", "Bitti")) \
            if self.mode == "install" else \
            (("options", "Onay"), ("progress", "Kaldırma"), ("done", "Bitti"))
        self.step_widgets: dict[str, tk.Label] = {}
        for index, (key, label) in enumerate(labels, start=1):
            row = tk.Frame(steps, bg=ui.PRIMARY)
            row.pack(fill="x", pady=px(5))
            dot = tk.Label(row, text="●", font=ui.fonts["tiny"], fg="#3F3F46", bg=ui.PRIMARY)
            dot.pack(side="left", padx=(0, px(10)))
            text = tk.Label(row, text=f"{index}. {label}", font=ui.fonts["body"], fg="#71717A",
                            bg=ui.PRIMARY, anchor="w")
            text.pack(side="left")
            self.step_widgets[key] = text
            self.step_widgets[key + "_dot"] = dot

        ui.LinkBar(hero, bg=ui.PRIMARY, fg="#8B8B93", hover_fg="#FFFFFF",
                   hover_bg="#27272A", caption_fg="#6B6B73").pack(
            side="bottom", fill="x", padx=px(26), pady=(px(14), px(24)))
        tk.Frame(hero, bg="#27272A", height=1).pack(side="bottom", fill="x", padx=px(28))
        tk.Label(hero, text="Yönetici yetkisi gerekmez.\nYalnızca bu kullanıcı için kurulur.",
                 font=ui.fonts["small"], fg="#6B6B73", bg=ui.PRIMARY, anchor="w",
                 justify="left").pack(side="bottom", fill="x", padx=px(28),
                                      pady=(px(20), px(18)))

        self.host = tk.Frame(self, bg=ui.CARD)
        self.host.pack(side="left", fill="both", expand=True)

        self.pages = {
            "options": (self._page_options() if self.mode == "install" else self._page_confirm()),
            "progress": self._page_progress(),
            "done": self._page_done(),
        }

    def _page_shell(self, title: str, description: str) -> tuple[tk.Frame, tk.Frame, tk.Frame]:
        page = tk.Frame(self.host, bg=ui.CARD)
        head = tk.Frame(page, bg=ui.CARD)
        head.pack(fill="x", padx=px(32), pady=(px(34), px(18)))
        page.title_label = tk.Label(head, text=title, font=ui.fonts["display"], fg=ui.FG,
                                    bg=ui.CARD, anchor="w")
        page.title_label.pack(fill="x")
        tk.Label(head, text=description, font=ui.fonts["small"], fg=ui.MUTED, bg=ui.CARD,
                 anchor="w", justify="left",
                 wraplength=px(WINDOW_W - HERO_W - 64)).pack(fill="x", pady=(px(6), 0))
        body = tk.Frame(page, bg=ui.CARD)
        body.pack(fill="both", expand=True, padx=px(32))
        ui.Separator(page).pack(fill="x")
        footer = tk.Frame(page, bg=ui.CARD)
        footer.pack(fill="x", padx=px(32), pady=px(18))
        return page, body, footer

    # -- sayfalar ------------------------------------------------------------ #
    def _page_options(self) -> tk.Frame:
        updating = self.existing is not None
        page, body, footer = self._page_shell(
            "Güncelleme" if updating else "ClearFast kurulumu",
            f"Yüklü sürüm {self.existing['version']} yenisiyle değiştirilecek."
            if updating else
            "Kurulum klasörünü onaylayın ve kısayol tercihlerinizi seçin.")

        tk.Label(body, text="KURULUM KLASÖRÜ", font=ui.fonts["tiny"], fg=ui.SUBTLE, bg=ui.CARD,
                 anchor="w").pack(fill="x")
        row = tk.Frame(body, bg=ui.CARD)
        row.pack(fill="x", pady=(px(8), 0))
        ui.Input(row, self.path_var, bg=ui.CARD).pack(side="left", fill="x", expand=True)
        ui.Button(row, "Gözat", self._browse, variant="outline",
                  bg=ui.CARD).pack(side="left", padx=(px(8), 0))

        size = program_size(program_dir())
        tk.Label(body, text=f"Gereken alan: yaklaşık {human_bytes(size)}",
                 font=ui.fonts["small"], fg=ui.SUBTLE, bg=ui.CARD,
                 anchor="w").pack(fill="x", pady=(px(8), 0))

        options = tk.Frame(body, bg=ui.CARD)
        options.pack(fill="x", pady=(px(22), 0))
        self.opt_menu = ui.CheckRow(options, "Başlat menüsüne ekle",
                                    "ClearFast'i Windows aramasından açabilirsiniz.", bg=ui.CARD)
        self.opt_menu.pack(fill="x", pady=(0, px(12)))
        self.opt_desktop = ui.CheckRow(options, "Masaüstü kısayolu oluştur", bg=ui.CARD)
        self.opt_desktop.pack(fill="x", pady=(0, px(12)))
        self.opt_launch = ui.CheckRow(options, "Kurulumdan sonra ClearFast'i çalıştır",
                                      bg=ui.CARD)
        self.opt_launch.pack(fill="x")

        ui.Alert(body, "Kaldırmak istediğinizde",
                 "ClearFast, Windows Ayarlar › Uygulamalar listesinde görünür. "
                 "Kurulum klasöründe ClearFast.exe --uninstall de aynı işi yapar.",
                 tone="info", bg=ui.CARD).pack(side="bottom", fill="x", pady=(px(16), px(20)))

        ui.Button(footer, "Kur", self._start_install, variant="primary",
                  bg=ui.CARD).pack(side="right")
        ui.Button(footer, "Vazgeç", self.destroy, variant="ghost",
                  bg=ui.CARD).pack(side="right", padx=(0, px(8)))
        return page

    def _page_confirm(self) -> tk.Frame:
        location = (self.existing or {}).get("location") or str(default_install_dir())
        page, body, footer = self._page_shell(
            "ClearFast kaldırılsın mı?",
            "Uygulama dosyaları, kısayollar ve sistem kaydı silinecek.")
        card = ui.Card(body, fill=ui.SUNKEN, border=ui.BORDER, radius=10, padx=14, pady=12,
                       bg=ui.CARD)
        card.pack(fill="x")
        tk.Label(card.body, text="Kaldırılacak klasör", font=ui.fonts["label"], fg=ui.FG,
                 bg=ui.SUNKEN, anchor="w").pack(fill="x")
        tk.Label(card.body, text=location, font=ui.fonts["mono"], fg=ui.MUTED, bg=ui.SUNKEN,
                 anchor="w").pack(fill="x", pady=(px(4), 0))
        ui.Alert(body, "Temizlenen dosyalar geri gelmez",
                 "ClearFast'in daha önce sildiği geçici dosyalar bu işlemle geri getirilmez; "
                 "yalnızca uygulamanın kendisi kaldırılır.",
                 tone="info", bg=ui.CARD).pack(fill="x", pady=(px(16), 0))
        self.path_var.set(location)

        ui.Button(footer, "Kaldır", self._start_uninstall, variant="danger",
                  bg=ui.CARD).pack(side="right")
        ui.Button(footer, "Vazgeç", self.destroy, variant="ghost",
                  bg=ui.CARD).pack(side="right", padx=(0, px(8)))
        return page

    def _page_progress(self) -> tk.Frame:
        page, body, footer = self._page_shell(
            "Kuruluyor" if self.mode == "install" else "Kaldırılıyor",
            "Bu işlem yalnızca birkaç saniye sürer.")
        holder = tk.Frame(body, bg=ui.CARD)
        holder.pack(fill="x", pady=(px(20), 0))
        self.progress = ui.Meter(holder, height=8, bg=ui.CARD)
        self.progress.pack(fill="x")
        self.progress_text = tk.Label(holder, text="Hazırlanıyor…", font=ui.fonts["small"],
                                      fg=ui.MUTED, bg=ui.CARD, anchor="w")
        self.progress_text.pack(fill="x", pady=(px(12), 0))
        spacer = tk.Frame(footer, bg=ui.CARD, width=1, height=px(34))
        spacer.pack(side="right")
        return page

    def _page_done(self) -> tk.Frame:
        page, body, footer = self._page_shell("Hazır", "")
        self.done_page = page
        self.done_icon = tk.Canvas(body, bg=ui.CARD, highlightthickness=0, bd=0,
                                   width=px(46), height=px(46))
        self.done_icon.pack(anchor="w", pady=(px(4), px(18)))
        self.done_text = tk.Label(body, text="", font=ui.fonts["body"], fg=ui.MUTED,
                                  bg=ui.CARD, anchor="w", justify="left",
                                  wraplength=px(WINDOW_W - HERO_W - 64))
        self.done_text.pack(fill="x")
        self.done_button = ui.Button(footer, "Bitir", self._finish, variant="primary",
                                     bg=ui.CARD)
        self.done_button.pack(side="right")
        return page

    # -- akis ---------------------------------------------------------------- #
    def select_page(self, key: str) -> None:
        for name, page in self.pages.items():
            if name == key:
                page.pack(fill="both", expand=True)
            else:
                page.pack_forget()
        order = ["options", "progress", "done"]
        active = order.index(key)
        for index, name in enumerate(order):
            done = index < active
            current = index == active
            self.step_widgets[name].configure(
                fg="#FAFAFA" if current else ("#A1A1AA" if done else "#71717A"))
            self.step_widgets[name + "_dot"].configure(
                fg="#FAFAFA" if current else ("#52525B" if done else "#3F3F46"))

    def _browse(self) -> None:
        from tkinter import filedialog
        chosen = filedialog.askdirectory(parent=self, title="Kurulum klasörünü seçin",
                                         initialdir=self.path_var.get() or str(Path.home()))
        if chosen:
            path = Path(chosen)
            if path.name.lower() != APP_NAME.lower():
                path = path / APP_NAME
            self.path_var.set(str(path))

    def _pump(self) -> None:
        while True:
            try:
                callback, args = self.results.get_nowait()
            except queue.Empty:
                break
            callback(*args)
        self.after(40, self._pump)

    def _report(self, ratio: float, text: str) -> None:
        self.results.put((self._apply_progress, (ratio, text)))

    def _apply_progress(self, ratio: float, text: str) -> None:
        self.progress.set(ratio, ui.PRIMARY)
        self.progress_text.configure(text=text)

    def _start_install(self) -> None:
        target = Path(self.path_var.get().strip().strip('"'))
        if not target.is_absolute():
            ui.inform(self, "Geçersiz klasör",
                      "Lütfen tam bir klasör yolu girin. Örnek: "
                      r"C:\Users\Ad\AppData\Local\Programs\ClearFast", tone="warn")
            return
        self.launch_after = self.opt_launch.get()
        desktop, menu = self.opt_desktop.get(), self.opt_menu.get()
        self.select_page("progress")

        def worker() -> None:
            try:
                exe = install(target, desktop, menu, self._report)
                self.results.put((self._after_install, (exe, None)))
            except Exception as exc:
                self.results.put((self._after_install, (None, str(exc))))

        threading.Thread(target=worker, daemon=True).start()

    def _start_uninstall(self) -> None:
        target = Path(self.path_var.get().strip())
        self.select_page("progress")

        def worker() -> None:
            try:
                uninstall(target, self._report)
                self.results.put((self._after_uninstall, (None,)))
            except Exception as exc:
                self.results.put((self._after_uninstall, (str(exc),)))

        threading.Thread(target=worker, daemon=True).start()

    def _after_install(self, exe: Path | None, error: str | None) -> None:
        self.error = error
        self.installed_exe = exe
        self._render_done(
            ok_title="ClearFast kuruldu",
            ok_text=f"Uygulama {exe.parent} klasörüne yerleştirildi. Başlat menüsünden veya "
                    f"kısayoldan açabilirsiniz." if exe else "",
            fail_title="Kurulum tamamlanamadı")

    def _after_uninstall(self, error: str | None) -> None:
        self.error = error
        self._render_done(
            ok_title="ClearFast kaldırıldı",
            ok_text="Uygulama dosyaları, kısayollar ve sistem kaydı silindi. "
                    "Klasör birkaç saniye içinde tamamen temizlenecek.",
            fail_title="Kaldırma tamamlanamadı")

    def _render_done(self, ok_title: str, ok_text: str, fail_title: str) -> None:
        tone = "danger" if self.error else "ok"
        color, back, edge = ui.TONES[tone]
        size = px(46)
        self.done_icon.delete("all")
        ui.round_rect(self.done_icon, 0, 0, size, size, px(12), back, edge, px(1), ui.CARD)
        self.done_icon.create_image(size // 2 - px(11), size // 2 - px(11), anchor="nw",
                                    image=ui.icon("check" if not self.error else "bang",
                                                  px(22), color, back))
        self.done_page.title_label.configure(text=fail_title if self.error else ok_title)
        self.done_text.configure(text=self.error or ok_text)
        self.done_button.set_text("Kapat" if self.error else "Bitir")
        self.select_page("done")

    def _finish(self) -> None:
        if (self.mode == "install" and not self.error and self.launch_after
                and self.installed_exe and self.installed_exe.exists()):
            try:
                subprocess.Popen([str(self.installed_exe)], cwd=str(self.installed_exe.parent),
                                 creationflags=DETACHED_PROCESS, close_fds=True)
            except OSError:
                pass
        self.destroy()


def run() -> None:
    """ClearFast.exe --setup / --uninstall tarafindan cagrilir."""
    mode = "uninstall" if "--uninstall" in sys.argv else "install"
    SetupApp(mode).mainloop()


def main() -> None:
    if os.name != "nt":
        print("ClearFast kurulumu yalnizca Windows icin tasarlanmistir.")
        return
    ui.enable_dpi_awareness()
    run()


if __name__ == "__main__":
    main()
