# -*- coding: utf-8 -*-
"""ClearFast - Windows temizlik ve sistem durumu araci.

Guvenli varsayilanlar yalnizca gecici/onbellek/gunluk klasorlerini hedefler.
Projeler, belgeler, tarayici profilleri, sifreler, sohbet gecmisleri ve yapay
zeka model depolari varsayilan temizlik kapsaminda DEGILDIR.
"""
from __future__ import annotations

import os
import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path

import cf_core as core
import cf_metrics as metrics
import cf_ui as ui
from cf_ui import px

SIDEBAR_W = 228
HEADER_H = 62
FOOTER_H = 46
PAGE_PAD = 26
GAP = 14


def resource_path(name: str) -> Path:
    """PyInstaller ile paketlendiginde de calisan varlik yolu."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


# --------------------------------------------------------------------------- #
# Kucuk yardimci bilesenler
# --------------------------------------------------------------------------- #

def field(master, label: str, value: str, bg: str, *, label_w: int = 96,
          mono: bool = False) -> tk.Label:
    """Etiket + deger satiri. Etiket genisligi sabit oldugu icin sutunlar hizali kalir."""
    row = tk.Frame(master, bg=bg)
    row.pack(fill="x", pady=px(3))
    holder = tk.Frame(row, bg=bg, width=px(label_w))
    holder.pack(side="left", fill="y")
    holder.pack_propagate(False)
    tk.Label(holder, text=label, font=ui.fonts["small"], fg=ui.SUBTLE, bg=bg,
             anchor="w").pack(fill="x")
    val = tk.Label(row, text=value, font=ui.fonts["mono"] if mono else ui.fonts["body"],
                   fg=ui.FG, bg=bg, anchor="w", justify="left")
    val.pack(side="left", fill="x", expand=True)

    def wrap(event) -> None:
        # Yalnizca gercekten degistiginde ayarla; aksi halde sonsuz dongu olur.
        if abs(int(val.cget("wraplength")) - event.width) > 4:
            val.configure(wraplength=max(px(80), event.width))

    val.bind("<Configure>", wrap)
    return val


class Stat(tk.Frame):
    """Baslik + buyuk deger + ipucu (+ istege bagli doluluk cubugu)."""

    def __init__(self, master, title: str, *, bg: str, meter: bool = False) -> None:
        super().__init__(master, bg=bg)
        tk.Label(self, text=ui.tr_upper(title), font=ui.fonts["tiny"], fg=ui.SUBTLE, bg=bg,
                 anchor="w").pack(fill="x")
        self.value = tk.Label(self, text="—", font=ui.fonts["big"], fg=ui.FG, bg=bg, anchor="w")
        self.value.pack(fill="x", pady=(px(6), 0))
        self.meter = ui.Meter(self, bg=bg) if meter else None
        if self.meter:
            self.meter.pack(fill="x", pady=(px(10), 0))
        self.hint = tk.Label(self, text="", font=ui.fonts["small"], fg=ui.MUTED, bg=bg, anchor="w")
        self.hint.pack(fill="x", pady=(px(8), 0))

    def set(self, value: str, hint: str = "", ratio: float | None = None,
            color: str | None = None) -> None:
        self.value.configure(text=value)
        self.hint.configure(text=hint)
        if self.meter is not None and ratio is not None:
            self.meter.set(ratio, color)


class NavItem(tk.Canvas):
    def __init__(self, master, text: str, icon_name: str, command) -> None:
        self._bg = ui.CARD
        super().__init__(master, bg=self._bg, highlightthickness=0, bd=0,
                         height=px(38), cursor="hand2")
        self._text, self._icon = text, icon_name
        self._active = False
        self._hover = False
        self._command = command
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<Button-1>", lambda e: self._command())

    def _set_hover(self, value: bool) -> None:
        self._hover = value
        self._draw()

    def set_active(self, value: bool) -> None:
        self._active = value
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1:
            return
        if self._active:
            fill, fg = ui.SUNKEN, ui.FG
        elif self._hover:
            fill, fg = ui.SUNKEN, ui.FG
        else:
            fill, fg = self._bg, ui.MUTED
        ui.round_rect(self, 0, 0, w, h, px(8), fill, None, 0, self._bg)
        size = px(16)
        self.create_image(px(11), (h - size) // 2, anchor="nw",
                          image=ui.icon(self._icon, size, fg, fill))
        self.create_text(px(11) + size + px(10), h // 2 + 1, text=self._text,
                         font=ui.fonts["section"] if self._active else ui.fonts["body"],
                         fill=fg, anchor="w")


class TargetRow(tk.Frame):
    """Temizleyici listesinde bir hedefin tum klasorlerini temsil eden satir."""

    def __init__(self, master, group: core.ScanGroup, *, on_toggle, on_focus) -> None:
        super().__init__(master, bg=ui.CARD, height=px(54))
        self.group = group
        self._on_toggle = on_toggle
        self._on_focus = on_focus
        self.pack_propagate(False)

        self.check = ui.Checkbox(self, command=lambda _v: self._toggle(), bg=ui.CARD)
        self.check.pack(side="left", padx=(px(16), px(12)))

        right = tk.Frame(self, bg=ui.CARD, width=px(92))
        right.pack(side="right", fill="y", padx=(px(10), px(16)))
        right.pack_propagate(False)
        self.size_label = tk.Label(right, text=core.human_bytes(group.size),
                                   font=ui.fonts["section"],
                                   fg=ui.FG if group.size else ui.SUBTLE, bg=ui.CARD,
                                   anchor="e")
        self.size_label.place(relx=1.0, rely=0.5, anchor="e")

        self.badge_holder = tk.Frame(self, bg=ui.CARD, width=px(76))
        self.badge_holder.pack(side="right", fill="y")
        self.badge_holder.pack_propagate(False)
        tone, text = self._risk_badge(group.target)
        self.badge = None
        if text:
            self.badge = ui.Badge(self.badge_holder, text, tone, bg=ui.CARD)
            self.badge.place(relx=1.0, rely=0.5, anchor="e")

        middle = tk.Frame(self, bg=ui.CARD)
        middle.pack(side="left", fill="both", expand=True)
        self.title_label = tk.Label(middle, text=group.target.title, font=ui.fonts["body"],
                                    fg=ui.FG, bg=ui.CARD, anchor="w")
        self.title_label.pack(fill="x", pady=(px(9), 0))
        self.path_label = tk.Label(middle, text="", font=ui.fonts["mono"], fg=ui.SUBTLE,
                                   bg=ui.CARD, anchor="w")
        self.path_label.pack(fill="x", pady=(px(2), 0))
        count = len(group.rows)
        self._full_path = (group.location if count == 1
                           else f"{count} klasör · {group.location}")
        middle.bind("<Configure>", self._fit_path)

        ui.bind_tree(self, "<Button-1>", self._click)
        ui.bind_tree(self, "<Double-Button-1>", self._reveal)
        ui.bind_tree(self, "<Enter>", lambda e: self._set_hover(True))
        ui.bind_tree(self, "<Leave>", lambda e: self._set_hover(False))

    @staticmethod
    def _risk_badge(target: core.CleanupTarget) -> tuple[str, str]:
        if target.risk == "Opsiyonel":
            return "warn", "Opsiyonel"
        if target.requires_admin:
            return "outline", "Yönetici"
        return "muted", ""

    def _fit_path(self, event) -> None:
        self.path_label.configure(
            text=ui.ellipsize(ui.fonts["mono"], self._full_path, max(px(60), event.width - px(8))))

    def _click(self, _e=None) -> str:
        self.check.set(not self.check.get())
        self._toggle()
        return "break"

    def _toggle(self) -> None:
        self._on_toggle(self.group, self.check.get())

    def _reveal(self, _e=None) -> str:
        if self.group.rows:
            core.reveal(self.group.rows[0].path)
        return "break"

    def _set_hover(self, value: bool) -> None:
        color = ui.SUNKEN if value else ui.CARD
        for widget in (self, self.badge_holder, self.title_label, self.path_label,
                       self.size_label):
            widget.configure(bg=color)
        for child in self.winfo_children():
            if isinstance(child, tk.Frame):
                child.configure(bg=color)
        self.check.set_bg(color)
        if self.badge is not None:
            self.badge.set_bg(color)
        if value:
            self._on_focus(self.group)

    def set_checked(self, value: bool) -> None:
        self.check.set(value)


# --------------------------------------------------------------------------- #
# Sayfalar
# --------------------------------------------------------------------------- #

class Page(tk.Frame):
    """Baslik blogu + icerik alani olan ortak sayfa iskeleti."""

    def __init__(self, master, title: str, description: str, *, scroll: bool = True) -> None:
        super().__init__(master, bg=ui.BG)
        head = tk.Frame(self, bg=ui.BG)
        head.pack(fill="x", padx=px(PAGE_PAD), pady=(px(22), px(16)))
        self.actions = tk.Frame(head, bg=ui.BG)
        self.actions.pack(side="right", anchor="n")
        texts = tk.Frame(head, bg=ui.BG)
        texts.pack(side="left", fill="x", expand=True)
        tk.Label(texts, text=title, font=ui.fonts["display"], fg=ui.FG, bg=ui.BG,
                 anchor="w").pack(fill="x")
        tk.Label(texts, text=description, font=ui.fonts["small"], fg=ui.MUTED, bg=ui.BG,
                 anchor="w").pack(fill="x", pady=(px(4), 0))

        if scroll:
            area = ui.ScrollArea(self, bg=ui.BG)
            area.pack(fill="both", expand=True, padx=(px(PAGE_PAD), px(PAGE_PAD - 8)),
                      pady=(0, px(18)))
            self.content = area.inner
        else:
            self.content = tk.Frame(self, bg=ui.BG)
            self.content.pack(fill="both", expand=True, padx=px(PAGE_PAD), pady=(0, px(18)))


class SystemPage(Page):
    def __init__(self, master, app: "ClearFastApp") -> None:
        super().__init__(master, "Sistem",
                         "Donanım, bellek ve depolama durumunun tek ekranda özeti.")
        self.app = app
        ui.Button(self.actions, "Yenile", app.refresh_system, variant="outline",
                  bg=ui.BG).pack(side="right")

        stats = tk.Frame(self.content, bg=ui.BG)
        stats.pack(fill="x")
        for i in range(3):
            stats.columnconfigure(i, weight=1, uniform="stat")
        self.stat_ram = self._stat_card(stats, 0, "Bellek", meter=True)
        self.stat_disk = self._stat_card(stats, 1, "Sistem diski", meter=True)
        self.stat_clean = self._stat_card(stats, 2, "Temizlenebilir", meter=False)

        columns = tk.Frame(self.content, bg=ui.BG)
        columns.pack(fill="x", pady=(px(GAP), 0))
        columns.columnconfigure(0, weight=7)
        columns.columnconfigure(1, weight=5)

        self.hw_card, self.hw_body = self._titled_card(columns, 0, "Donanım")
        self.drive_card, self.drive_body = self._titled_card(columns, 1, "Sürücüler")

        self.last_disks: list[dict] = []
        self.last_gpus: list[dict] = []
        self.health_card = ui.Card(self.content, bg=ui.BG)
        self.health_card.pack(fill="x", pady=(px(GAP), 0))
        tk.Label(self.health_card.body, text="Fiziksel disk sağlığı", font=ui.fonts["section"],
                 fg=ui.FG, bg=ui.CARD, anchor="w").pack(fill="x", pady=(0, px(10)))
        self.health_body = tk.Frame(self.health_card.body, bg=ui.CARD)
        self.health_body.pack(fill="x")

        ui.Alert(self.content, "Bu bir SMART analizi değildir",
                 "ClearFast, Windows'un Get-PhysicalDisk sağlık durumunu gösterir. Ayrıntılı "
                 "SSD ömür yüzdesi için üreticinin aracını veya CrystalDiskInfo gibi özel bir "
                 "program kullanın.", tone="info", bg=ui.BG).pack(fill="x", pady=(px(GAP), 0))

    def _stat_card(self, parent, column: int, title: str, *, meter: bool) -> Stat:
        card = ui.Card(parent, bg=ui.BG, pady=18)
        card.grid(row=0, column=column, sticky="ew",
                  padx=(0 if column == 0 else px(GAP) // 2, 0 if column == 2 else px(GAP) // 2))
        stat = Stat(card.body, title, bg=ui.CARD, meter=meter)
        stat.pack(fill="x")
        return stat

    def _titled_card(self, parent, column: int, title: str) -> tuple[ui.Card, tk.Frame]:
        card = ui.Card(parent, bg=ui.BG)
        card.grid(row=0, column=column, sticky="new",
                  padx=(0, px(GAP) // 2) if column == 0 else (px(GAP) // 2, 0))
        tk.Label(card.body, text=title, font=ui.fonts["section"], fg=ui.FG, bg=ui.CARD,
                 anchor="w").pack(fill="x", pady=(0, px(10)))
        inner = tk.Frame(card.body, bg=ui.CARD)
        inner.pack(fill="x")
        return card, inner

    # -- veri ---------------------------------------------------------------- #
    def render(self, snap: dict, specs: dict, modules: list[dict]) -> None:
        total, avail = snap["ram_total"], snap["ram_available"]
        used = max(0, total - avail)
        ratio = (used / total) if total else 0.0
        self.stat_ram.set(
            core.human_bytes(used),
            f"{core.human_bytes(total)} toplam · {core.human_bytes(avail)} boş",
            ratio, ui.DANGER if ratio > 0.9 else (ui.WARN if ratio > 0.75 else ui.PRIMARY))

        letter = snap["system_drive"].rstrip("\\")
        drive = next((d for d in snap["drives"] if d["root"].upper() == letter.upper()), None)
        if drive:
            fill = (drive["used"] / drive["total"]) if drive["total"] else 0.0
            self.stat_disk.set(
                core.human_bytes(drive["free"]),
                f"{letter} sürücüsünde boş · %{fill * 100:.0f} dolu", fill,
                ui.DANGER if fill > 0.92 else (ui.WARN if fill > 0.8 else ui.PRIMARY))

        for child in self.hw_body.winfo_children():
            child.destroy()
        label_w = 104
        if specs.get("model"):
            field(self.hw_body, "Bilgisayar", specs["model"], ui.CARD, label_w=label_w)
        if specs.get("board"):
            field(self.hw_body, "Anakart", specs["board"], ui.CARD, label_w=label_w)
        if specs.get("bios"):
            bios = specs["bios"]
            if specs.get("bios_date"):
                bios += f"  ({specs['bios_date']})"
            field(self.hw_body, "BIOS", bios, ui.CARD, label_w=label_w)

        cpu_text = specs.get("cpu_name") or snap["cpu"]
        cores, threads = specs.get("cpu_cores"), specs.get("cpu_threads")
        if cores:
            cpu_text += f"\n{cores} çekirdek · {threads} iş parçacığı"
            if specs.get("cpu_mhz"):
                cpu_text += f" · {specs['cpu_mhz'] / 1000:.1f} GHz".replace(".", ",")
        field(self.hw_body, "İşlemci", cpu_text, ui.CARD, label_w=label_w)

        ram_text = core.human_bytes(total)
        if modules:
            speed = modules[0]["configured"] or modules[0]["speed"]
            kind = modules[0]["type"] or "RAM"
            ram_text += (f"\n{len(modules)} × {core.human_bytes(modules[0]['capacity'])} "
                         f"{kind}" + (f" {speed} MHz" if speed else ""))
        field(self.hw_body, "Bellek", ram_text, ui.CARD, label_w=label_w)

        if snap["gpus"]:
            for index, gpu in enumerate(snap["gpus"]):
                text = gpu["name"]
                if gpu.get("driver"):
                    text += f"\nSürücü {gpu['driver']}"
                field(self.hw_body, "Ekran kartı" if index == 0 else "", text, ui.CARD,
                      label_w=label_w)
        else:
            field(self.hw_body, "Ekran kartı", "Okunamadı", ui.CARD, label_w=label_w)

        windows = snap["windows"]
        if specs.get("os_build"):
            windows = (f"{specs.get('os_caption') or 'Windows'}\n"
                       f"Sürüm {specs.get('os_version', '')} (yapı {specs['os_build']})"
                       f" · {specs.get('os_arch', '')}").strip()
        field(self.hw_body, "İşletim sistemi", windows, ui.CARD, label_w=label_w)

        uptime = specs.get("uptime_hours") or 0
        if uptime:
            days, rest = divmod(float(uptime), 24)
            hours, minutes = divmod(rest, 1)
            parts = []
            if days:
                parts.append(f"{int(days)} gün")
            if hours:
                parts.append(f"{int(hours)} saat")
            parts.append(f"{int(minutes * 60)} dakika")
            text = " ".join(parts)
            if specs.get("boot_time"):
                text += f"\nSon açılış: {specs['boot_time']}"
            field(self.hw_body, "Açık kalma", text, ui.CARD, label_w=label_w)

        field(self.hw_body, "Yetki", "Yönetici olarak çalışıyor" if snap["admin"]
              else "Standart kullanıcı", ui.CARD, label_w=label_w)

        for child in self.drive_body.winfo_children():
            child.destroy()
        if not snap["drives"]:
            tk.Label(self.drive_body, text="Sürücü bilgisi okunamadı.", font=ui.fonts["small"],
                     fg=ui.MUTED, bg=ui.CARD, anchor="w").pack(fill="x")
        for drive in snap["drives"]:
            ratio = (drive["used"] / drive["total"]) if drive["total"] else 0.0
            block = tk.Frame(self.drive_body, bg=ui.CARD)
            block.pack(fill="x", pady=(0, px(12)))
            line = tk.Frame(block, bg=ui.CARD)
            line.pack(fill="x")
            tk.Label(line, text=drive["root"], font=ui.fonts["section"], fg=ui.FG,
                     bg=ui.CARD, anchor="w").pack(side="left")
            tk.Label(line, text=f"{core.human_bytes(drive['free'])} boş / "
                                f"{core.human_bytes(drive['total'])}",
                     font=ui.fonts["small"], fg=ui.MUTED, bg=ui.CARD,
                     anchor="e").pack(side="right")
            meter = ui.Meter(block, bg=ui.CARD)
            meter.pack(fill="x", pady=(px(7), 0))
            meter.set(ratio, ui.DANGER if ratio > 0.92 else (ui.WARN if ratio > 0.8 else ui.PRIMARY))

        self.after_idle(self._balance_columns)

        self.last_disks = snap["disks"]
        self.last_gpus = snap["gpus"]

        for child in self.health_body.winfo_children():
            child.destroy()
        if not snap["disks"]:
            tk.Label(self.health_body, text="Get-PhysicalDisk bilgisi okunamadı.",
                     font=ui.fonts["small"], fg=ui.MUTED, bg=ui.CARD, anchor="w").pack(fill="x")
        for disk in snap["disks"]:
            line = tk.Frame(self.health_body, bg=ui.CARD)
            line.pack(fill="x", pady=px(4))
            label, tone = core.health_label(disk["health"])
            ui.Badge(line, label, tone if tone != "muted" else "muted",
                     bg=ui.CARD).pack(side="right", padx=(px(10), 0))
            tk.Label(line, text=f"{disk['media']} · {core.human_bytes(disk['size'])}",
                     font=ui.fonts["small"], fg=ui.MUTED, bg=ui.CARD,
                     anchor="e").pack(side="right")
            tk.Label(line, text=disk["name"], font=ui.fonts["body"], fg=ui.FG, bg=ui.CARD,
                     anchor="w").pack(side="left", fill="x", expand=True)

    def _balance_columns(self) -> None:
        """Yan yana iki kart ayni yukseklikte dursun."""
        self.update_idletasks()
        tallest = max(card.body.winfo_reqheight() + px(32)
                      for card in (self.hw_card, self.drive_card))
        for card in (self.hw_card, self.drive_card):
            card.set_min_height(tallest)

    def set_cleanable(self, total: int, count: int) -> None:
        self.stat_clean.set(core.human_bytes(total),
                            f"{count} konumda yeniden oluşturulabilir veri")


class CleanerPage(Page):
    def __init__(self, master, app: "ClearFastApp") -> None:
        super().__init__(master, "Temizleyici",
                         "Yalnızca yeniden oluşturulabilir geçici, önbellek ve günlük klasörleri.",
                         scroll=False)
        self.app = app
        self.rows: dict[str, TargetRow] = {}
        self.groups: dict[str, core.ScanGroup] = {}
        self.checked: set[str] = set()
        self.location_count = 0

        self.scan_btn = ui.Button(self.actions, "Yeniden tara", app.scan_cleanup,
                                  variant="outline", bg=ui.BG)
        self.scan_btn.pack(side="left", padx=(0, px(8)))
        self.clean_btn = ui.Button(self.actions, "Seçilenleri temizle", app.clean_selected,
                                   variant="primary", icon_name="sparkle", bg=ui.BG)
        self.clean_btn.pack(side="left")

        summary = ui.Card(self.content, bg=ui.BG, pady=18)
        summary.pack(fill="x")
        grid = tk.Frame(summary.body, bg=ui.CARD)
        grid.pack(fill="x")
        grid.columnconfigure(0, weight=0, minsize=px(150))
        grid.columnconfigure(1, weight=0, minsize=px(150))
        grid.columnconfigure(2, weight=1)
        self.stat_found = Stat(grid, "Bulunan", bg=ui.CARD)
        self.stat_found.grid(row=0, column=0, sticky="w")
        self.stat_selected = Stat(grid, "Seçili", bg=ui.CARD)
        self.stat_selected.grid(row=0, column=1, sticky="w")
        buttons = tk.Frame(grid, bg=ui.CARD)
        buttons.grid(row=0, column=2, sticky="e")
        ui.Button(buttons, "Güvenli seçim", self.select_safe, variant="outline",
                  bg=ui.CARD).pack(side="left", padx=(0, px(8)))
        ui.Button(buttons, "Seçimi kaldır", self.clear_selection, variant="ghost",
                  bg=ui.CARD).pack(side="left")

        self.alerts = tk.Frame(self.content, bg=ui.BG)
        self.alerts.pack(fill="x")
        self.alert_optional = ui.Alert(
            self.alerts, "Opsiyonel paket önbelleği seçildi",
            "pip / npm önbelleği silinirse paketler bir sonraki kurulumda yeniden indirilir. "
            "Veri kaybı olmaz, yalnızca ilk kurulum yavaşlar.", tone="warn", bg=ui.BG)
        self.alert_admin = ui.Alert(
            self.alerts, "Yönetici yetkisi olmadan çalışıyorsunuz",
            "Windows Temp içindeki bazı öğeler silinemeyecek ve sessizce atlanacak. "
            "Tamamı için ClearFast'i yönetici olarak çalıştırın.", tone="info", bg=ui.BG)

        list_card = ui.Card(self.content, bg=ui.BG, padx=0, pady=0, autoheight=False)
        list_card.pack(fill="both", expand=True, pady=(px(GAP), 0))
        self.list_area = ui.ScrollArea(list_card.body, bg=ui.CARD, pady=8)
        self.list_area.pack(fill="both", expand=True)
        self.list_body = self.list_area.inner

        ui.Separator(list_card.body).pack(fill="x")
        detail = tk.Frame(list_card.body, bg=ui.CARD, height=px(54))
        detail.pack(fill="x")
        detail.pack_propagate(False)
        self.detail_title = tk.Label(detail, text="Bir satırın üzerine gelin",
                                     font=ui.fonts["small"], fg=ui.FG, bg=ui.CARD, anchor="w")
        self.detail_title.pack(fill="x", padx=px(16), pady=(px(10), 0))
        self.detail_path = tk.Label(detail, text="Çift tıklamak klasörü Gezgin'de açar.",
                                    font=ui.fonts["mono"], fg=ui.SUBTLE, bg=ui.CARD, anchor="w")
        self.detail_path.pack(fill="x", padx=px(16), pady=(px(3), 0))
        detail.bind("<Configure>", self._fit_detail)
        self._detail_full = ""

    # -- liste --------------------------------------------------------------- #
    def render(self, rows: list[core.ScanRow]) -> None:
        for child in self.list_body.winfo_children():
            child.destroy()
        self.rows.clear()
        self.groups.clear()
        self.checked.clear()
        self.location_count = len(rows)

        groups = core.group_rows(rows)
        current = None
        for group in groups:
            if group.target.category != current:
                current = group.target.category
                header = tk.Frame(self.list_body, bg=ui.CARD)
                header.pack(fill="x", pady=(px(12) if self.rows else px(4), px(2)))
                tk.Label(header, text=ui.tr_upper(current), font=ui.fonts["tiny"], fg=ui.SUBTLE,
                         bg=ui.CARD, anchor="w").pack(fill="x", padx=px(16))
            widget = TargetRow(self.list_body, group, on_toggle=self._on_toggle,
                               on_focus=self._on_focus)
            widget.pack(fill="x")
            self.rows[group.key] = widget
            self.groups[group.key] = group
            if group.target.default_selected:
                widget.set_checked(True)
                self.checked.add(group.key)

        if not groups:
            tk.Label(self.list_body, text="Temizlenecek bir şey bulunamadı.",
                     font=ui.fonts["body"], fg=ui.MUTED, bg=ui.CARD).pack(pady=px(40))
        self.update_summary()

    def _on_toggle(self, group: core.ScanGroup, checked: bool) -> None:
        if checked:
            self.checked.add(group.key)
        else:
            self.checked.discard(group.key)
        self.update_summary()

    def _on_focus(self, group: core.ScanGroup) -> None:
        self.detail_title.configure(text=group.target.description)
        count = len(group.rows)
        self._detail_full = (group.location if count == 1
                             else f"{count} klasör · {group.location}")
        self._fit_detail()

    def _fit_detail(self, _event=None) -> None:
        if not self._detail_full:
            return
        width = max(px(120), self.detail_path.winfo_width())
        self.detail_path.configure(text=ui.ellipsize(ui.fonts["mono"], self._detail_full, width))

    # -- secim --------------------------------------------------------------- #
    def select_safe(self) -> None:
        for key, group in self.groups.items():
            wanted = group.target.default_selected
            self.rows[key].set_checked(wanted)
            if wanted:
                self.checked.add(key)
            else:
                self.checked.discard(key)
        self.update_summary()

    def clear_selection(self) -> None:
        for key in self.groups:
            self.rows[key].set_checked(False)
        self.checked.clear()
        self.update_summary()

    def chosen_groups(self) -> list[core.ScanGroup]:
        return [self.groups[key] for key in self.checked if key in self.groups]

    def selection(self) -> list[core.ScanRow]:
        return [row for group in self.chosen_groups() for row in group.rows]

    def update_summary(self) -> None:
        total = sum(group.size for group in self.groups.values())
        chosen = self.chosen_groups()
        selected = sum(group.size for group in chosen)
        folders = sum(len(group.rows) for group in chosen)
        self.stat_found.set(core.human_bytes(total),
                            f"{len(self.groups)} kaynak · {self.location_count} klasör")
        self.stat_selected.set(core.human_bytes(selected),
                               f"{len(chosen)} kaynak · {folders} klasör")
        self.app.system_page.set_cleanable(total, self.location_count)

        optional = any(not group.target.default_selected for group in chosen)
        admin_needed = (not self.app.is_admin) and any(group.target.requires_admin
                                                       for group in chosen)
        self._toggle_alert(self.alert_optional, optional)
        self._toggle_alert(self.alert_admin, admin_needed)
        self.clean_btn.set_enabled(bool(chosen) and not self.app.working)

    @staticmethod
    def _toggle_alert(alert: ui.Alert, visible: bool) -> None:
        # winfo_ismapped() sayfa gizliyken her zaman False doner; yerlesim
        # yoneticisinin durumu (winfo_manager) dogru olcuttur.
        managed = bool(alert.winfo_manager())
        if visible and not managed:
            alert.pack(fill="x", pady=(px(GAP), 0))
        elif not visible and managed:
            alert.pack_forget()


class ProtectedPage(Page):
    def __init__(self, master, app: "ClearFastApp") -> None:
        super().__init__(master, "Korunanlar",
                         "Büyük yer kaplayabilir ama çöp değildir; ClearFast bunlara dokunmaz.")
        self.app = app
        ui.Button(self.actions, "Boyutları tara", app.scan_watch, variant="outline",
                  bg=ui.BG).pack(side="right")
        ui.Alert(self.content, "Bu klasörler asla otomatik silinmez",
                 "Model depoları, eklentiler ve kullanıcı verisi yeniden oluşturulamaz ya da "
                 "yeniden indirilmesi saatler sürer. ClearFast bunları yalnızca raporlar.",
                 tone="warn", bg=ui.BG).pack(fill="x")
        self.body = tk.Frame(self.content, bg=ui.BG)
        self.body.pack(fill="x", pady=(px(GAP), 0))

    def render(self, rows: list[tuple[str, Path, int, str]]) -> None:
        for child in self.body.winfo_children():
            child.destroy()
        if not rows:
            card = ui.Card(self.body, bg=ui.BG)
            card.pack(fill="x")
            tk.Label(card.body, text="Bu bilgisayarda korunan bir depo bulunamadı.",
                     font=ui.fonts["body"], fg=ui.MUTED, bg=ui.CARD, anchor="w").pack(fill="x")
            return
        for title, path, size, note in rows:
            card = ui.Card(self.body, bg=ui.BG, pady=15)
            card.pack(fill="x", pady=(0, px(10)))
            head = tk.Frame(card.body, bg=ui.CARD)
            head.pack(fill="x")
            tk.Label(head, text=core.human_bytes(size), font=ui.fonts["section"], fg=ui.FG,
                     bg=ui.CARD, anchor="e").pack(side="right")
            ui.Badge(head, "Korunuyor", "ok", bg=ui.CARD).pack(side="right", padx=(0, px(10)))
            tk.Label(head, text=title, font=ui.fonts["body"], fg=ui.FG, bg=ui.CARD,
                     anchor="w").pack(side="left", fill="x", expand=True)
            tk.Label(card.body, text=str(path), font=ui.fonts["mono"], fg=ui.SUBTLE, bg=ui.CARD,
                     anchor="w").pack(fill="x", pady=(px(6), 0))
            tk.Label(card.body, text=note, font=ui.fonts["small"], fg=ui.MUTED, bg=ui.CARD,
                     anchor="w", justify="left").pack(fill="x", pady=(px(4), 0))


class MetricCard(ui.Card):
    """Baslik + buyuk deger + aciklama + canli grafik."""

    def __init__(self, master, title: str, color: str = ui.PRIMARY, tint: str = "#E4E4E7",
                 y_max: float = 100.0) -> None:
        super().__init__(master, bg=ui.BG, pady=18)
        tk.Label(self.body, text=ui.tr_upper(title), font=ui.fonts["tiny"], fg=ui.SUBTLE,
                 bg=ui.CARD, anchor="w").pack(fill="x")
        self.value = tk.Label(self.body, text="—", font=ui.fonts["big"], fg=ui.FG, bg=ui.CARD,
                              anchor="w")
        self.value.pack(fill="x", pady=(px(6), 0))
        self.hint = tk.Label(self.body, text="", font=ui.fonts["small"], fg=ui.MUTED,
                             bg=ui.CARD, anchor="w")
        self.hint.pack(fill="x", pady=(px(4), 0))
        self.chart = ui.LineChart(self.body, color=color, tint=tint, y_max=y_max,
                                  height=76, bg=ui.CARD)
        self.chart.pack(fill="x", pady=(px(14), 0))

    def update(self, value: str, hint: str = "", point: float | None = None) -> None:
        self.value.configure(text=value)
        if hint:
            self.hint.configure(text=hint)
        self.chart.push(point)


class ProcessRow(tk.Frame):
    """Surec listesinde tek satir; icerigi yerinde guncellenir."""

    def __init__(self, master) -> None:
        super().__init__(master, bg=ui.CARD, height=px(34))
        self.pack_propagate(False)
        self.ram = tk.Label(self, text="", font=ui.fonts["section"], fg=ui.FG, bg=ui.CARD,
                            anchor="e", width=10)
        self.ram.pack(side="right", padx=(px(12), px(18)))
        self.cpu = tk.Label(self, text="", font=ui.fonts["section"], fg=ui.FG, bg=ui.CARD,
                            anchor="e", width=7)
        self.cpu.pack(side="right")
        self.meter = ui.Meter(self, height=4, bg=ui.CARD)
        self.meter.pack(side="right", padx=(px(14), px(10)), pady=px(14))
        self.meter.configure(width=px(74))
        self.name = tk.Label(self, text="", font=ui.fonts["body"], fg=ui.FG, bg=ui.CARD,
                             anchor="w")
        self.name.pack(side="left", padx=(px(18), 0))
        self.count = tk.Label(self, text="", font=ui.fonts["small"], fg=ui.SUBTLE, bg=ui.CARD,
                              anchor="w")
        self.count.pack(side="left", padx=(px(8), 0))

    def show(self, row: dict, sort_key: str, peak_cpu: float, peak_ram: int) -> None:
        self.name.configure(text=row["name"])
        self.count.configure(text=f"{row['count']} işlem" if row["count"] > 1 else "")
        self.cpu.configure(text=f"%{row['cpu']:.1f}",
                           fg=ui.FG if row["cpu"] >= 0.1 else ui.SUBTLE)
        self.ram.configure(text=core.human_bytes(row["ram"]))
        # Cubuklar listedeki en buyuk degere gore olceklenir; boylece dusuk
        # kullanimda bile siralama gorsel olarak okunur.
        if sort_key == "cpu":
            ratio = row["cpu"] / peak_cpu if peak_cpu > 0 else 0.0
        else:
            ratio = row["ram"] / peak_ram if peak_ram > 0 else 0.0
        self.meter.set(min(1.0, ratio), ui.PRIMARY)

    def clear(self) -> None:
        for widget in (self.name, self.count, self.cpu, self.ram):
            widget.configure(text="")
        self.meter.set(0.0)


class PerformancePage(Page):
    ROWS = 12

    def __init__(self, master, app: "ClearFastApp") -> None:
        super().__init__(master, "Performans",
                         "Canlı işlemci, bellek ve ekran kartı kullanımı ile sistemi en çok "
                         "yoran uygulamalar.", scroll=False)
        self.app = app
        self.sort_key = "cpu"

        cards = tk.Frame(self.content, bg=ui.BG)
        cards.pack(fill="x")
        for i in range(3):
            cards.columnconfigure(i, weight=1, uniform="metric")
        self.cpu_card = MetricCard(cards, "İşlemci")
        self.cpu_card.grid(row=0, column=0, sticky="ew", padx=(0, px(GAP) // 2))
        self.ram_card = MetricCard(cards, "Bellek")
        self.ram_card.grid(row=0, column=1, sticky="ew", padx=px(GAP) // 2)
        self.gpu_card = MetricCard(cards, "Ekran kartı")
        self.gpu_card.grid(row=0, column=2, sticky="ew", padx=(px(GAP) // 2, 0))
        self.gpu_card.hint.configure(text="Canlı kullanım okunuyor…")

        table = ui.Card(self.content, bg=ui.BG, padx=0, pady=0, autoheight=False)
        table.pack(fill="both", expand=True, pady=(px(GAP), 0))
        head = tk.Frame(table.body, bg=ui.CARD)
        head.pack(fill="x", pady=(px(16), px(10)))
        tk.Label(head, text="Sistemi en çok yoran uygulamalar", font=ui.fonts["section"],
                 fg=ui.FG, bg=ui.CARD, anchor="w").pack(side="left", padx=(px(18), 0))
        self.sort_ram = ui.Button(head, "Belleğe göre", lambda: self.set_sort("ram"),
                                  variant="ghost", height=28, pad=11, bg=ui.CARD)
        self.sort_ram.pack(side="right", padx=(px(6), px(18)))
        self.sort_cpu = ui.Button(head, "İşlemciye göre", lambda: self.set_sort("cpu"),
                                  variant="secondary", height=28, pad=11, bg=ui.CARD)
        self.sort_cpu.pack(side="right")
        ui.Separator(table.body).pack(fill="x")

        legend = tk.Frame(table.body, bg=ui.CARD)
        legend.pack(fill="x", pady=(px(8), px(2)))
        tk.Label(legend, text="BELLEK", font=ui.fonts["tiny"], fg=ui.SUBTLE, bg=ui.CARD,
                 anchor="e", width=10).pack(side="right", padx=(px(12), px(18)))
        tk.Label(legend, text="İŞLEMCİ", font=ui.fonts["tiny"], fg=ui.SUBTLE, bg=ui.CARD,
                 anchor="e", width=7).pack(side="right")
        tk.Label(legend, text="UYGULAMA", font=ui.fonts["tiny"], fg=ui.SUBTLE, bg=ui.CARD,
                 anchor="w").pack(side="left", padx=(px(18), 0))

        area = ui.ScrollArea(table.body, bg=ui.CARD, pady=2)
        area.pack(fill="both", expand=True, pady=(0, px(6)))
        self.rows = [ProcessRow(area.inner) for _ in range(self.ROWS)]
        for row in self.rows:
            row.pack(fill="x")

    def set_sort(self, key: str) -> None:
        if self.sort_key == key:
            return
        self.sort_key = key
        self.sort_cpu._spec = ui._BUTTON_VARIANTS["secondary" if key == "cpu" else "ghost"]
        self.sort_ram._spec = ui._BUTTON_VARIANTS["secondary" if key == "ram" else "ghost"]
        self.sort_cpu._draw()
        self.sort_ram._draw()
        self.app.refresh_processes()

    def render_processes(self, rows: list[dict]) -> None:
        ordered = sorted(rows, key=lambda r: -r["ram"]) if self.sort_key == "ram" else rows
        peak_cpu = max((r["cpu"] for r in ordered[:self.ROWS]), default=0.0)
        peak_ram = max((r["ram"] for r in ordered[:self.ROWS]), default=0)
        for index, widget in enumerate(self.rows):
            if index < len(ordered):
                widget.show(ordered[index], self.sort_key, peak_cpu, peak_ram)
            else:
                widget.clear()

    def render_gpu(self, gpus: list[dict]) -> None:
        if not gpus:
            self.gpu_card.value.configure(text="—")
            self.gpu_card.hint.configure(
                text="Canlı kullanım için NVIDIA sürücüsü (nvidia-smi) gerekir.")
            return
        gpu = gpus[0]
        load = gpu["load"]
        self.gpu_card.update(
            f"%{load:.0f}" if load is not None else "—",
            f"{gpu['name']} · {gpu['temperature']:.0f}°C"
            if gpu.get("temperature") is not None else gpu["name"],
            load)


class HealthPage(Page):
    def __init__(self, master, app: "ClearFastApp") -> None:
        super().__init__(master, "Donanım sağlığı",
                         "Bellek modülleri, ekran kartı sıcaklığı ve disk aşınma sayaçları.")
        self.app = app
        ui.Button(self.actions, "Yenile", app.refresh_health, variant="outline",
                  bg=ui.BG).pack(side="right")

        self.ram_card = ui.Card(self.content, bg=ui.BG)
        self.ram_card.pack(fill="x")
        tk.Label(self.ram_card.body, text="Bellek modülleri", font=ui.fonts["section"],
                 fg=ui.FG, bg=ui.CARD, anchor="w").pack(fill="x", pady=(0, px(10)))
        self.ram_body = tk.Frame(self.ram_card.body, bg=ui.CARD)
        self.ram_body.pack(fill="x")

        self.gpu_card = ui.Card(self.content, bg=ui.BG)
        self.gpu_card.pack(fill="x", pady=(px(GAP), 0))
        tk.Label(self.gpu_card.body, text="Ekran kartı", font=ui.fonts["section"], fg=ui.FG,
                 bg=ui.CARD, anchor="w").pack(fill="x", pady=(0, px(10)))
        self.gpu_body = tk.Frame(self.gpu_card.body, bg=ui.CARD)
        self.gpu_body.pack(fill="x")

        self.disk_card = ui.Card(self.content, bg=ui.BG)
        self.disk_card.pack(fill="x", pady=(px(GAP), 0))
        tk.Label(self.disk_card.body, text="Disk aşınma ve sıcaklık sayaçları",
                 font=ui.fonts["section"], fg=ui.FG, bg=ui.CARD,
                 anchor="w").pack(fill="x", pady=(0, px(10)))
        self.disk_body = tk.Frame(self.disk_card.body, bg=ui.CARD)
        self.disk_body.pack(fill="x")

        ui.Alert(self.content, "Bu değerler nereden geliyor?",
                 "Bellek bilgisi Windows CIM'den, ekran kartı ölçümleri NVIDIA sürücüsünden "
                 "(nvidia-smi), disk aşınma sayaçları ise Get-StorageReliabilityCounter'dan "
                 "okunur. Windows, RAM için bir sağlık yüzdesi bildirmez; modül bilgisi ve "
                 "Bellek Tanılama aracı bu boşluğu doldurur.",
                 tone="info", bg=ui.BG).pack(fill="x", pady=(px(GAP), 0))

    @staticmethod
    def _clear(frame: tk.Frame) -> None:
        for child in frame.winfo_children():
            child.destroy()

    def render_memory(self, modules: list[dict], total: int) -> None:
        self._clear(self.ram_body)
        if not modules:
            tk.Label(self.ram_body, text="Modül bilgisi okunamadı.", font=ui.fonts["small"],
                     fg=ui.MUTED, bg=ui.CARD, anchor="w").pack(fill="x")
        for module in modules:
            line = tk.Frame(self.ram_body, bg=ui.CARD)
            line.pack(fill="x", pady=px(4))
            speed = module["configured"] or module["speed"]
            tk.Label(line, text=f"{speed} MHz" if speed else "—", font=ui.fonts["section"],
                     fg=ui.FG, bg=ui.CARD, anchor="e", width=10).pack(side="right")
            tk.Label(line, text=core.human_bytes(module["capacity"]), font=ui.fonts["section"],
                     fg=ui.FG, bg=ui.CARD, anchor="e", width=9).pack(side="right")
            if module["type"]:
                ui.Badge(line, module["type"], "muted", bg=ui.CARD).pack(side="right",
                                                                        padx=(0, px(12)))
            label = module["bank"] or module["slot"]
            tk.Label(line, text=f"{label} · {module['part'] or 'Model bilinmiyor'}",
                     font=ui.fonts["body"], fg=ui.FG, bg=ui.CARD,
                     anchor="w").pack(side="left", fill="x", expand=True)

        foot = tk.Frame(self.ram_body, bg=ui.CARD)
        foot.pack(fill="x", pady=(px(12), 0))
        ui.Button(foot, "Windows Bellek Tanılama", self.app.open_memory_diagnostic,
                  variant="outline", bg=ui.CARD).pack(side="right")
        tk.Label(foot, text=f"Toplam {core.human_bytes(total)} · {len(modules)} modül takılı",
                 font=ui.fonts["small"], fg=ui.MUTED, bg=ui.CARD,
                 anchor="w").pack(side="left", pady=px(8))

    def render_gpu(self, gpus: list[dict], fallback: list[dict]) -> None:
        self._clear(self.gpu_body)
        if not gpus:
            for gpu in fallback or [{"name": "Ekran kartı bilgisi okunamadı"}]:
                field(self.gpu_body, "Model", gpu.get("name", "—"), ui.CARD, label_w=110)
                if gpu.get("driver"):
                    field(self.gpu_body, "Sürücü", gpu["driver"], ui.CARD, label_w=110)
            tk.Label(self.gpu_body,
                     text="Sıcaklık, fan ve VRAM ölçümleri için NVIDIA sürücüsü gerekir.",
                     font=ui.fonts["small"], fg=ui.SUBTLE, bg=ui.CARD,
                     anchor="w").pack(fill="x", pady=(px(8), 0))
            return

        for gpu in gpus:
            field(self.gpu_body, "Model", gpu["name"], ui.CARD, label_w=110)
            field(self.gpu_body, "Sürücü", gpu["driver"], ui.CARD, label_w=110)
            grid = tk.Frame(self.gpu_body, bg=ui.CARD)
            grid.pack(fill="x", pady=(px(12), 0))
            for i in range(3):
                grid.columnconfigure(i, weight=1, uniform="gpu")

            temp = gpu.get("temperature")
            self._gauge(grid, 0, "Sıcaklık", f"{temp:.0f}°C" if temp is not None else "—",
                        (temp or 0) / 95.0,
                        ui.DANGER if (temp or 0) > 85 else (ui.WARN if (temp or 0) > 75
                                                           else ui.OK))
            used, total = gpu.get("memory_used"), gpu.get("memory_total")
            ratio = (used / total) if used is not None and total else 0.0
            self._gauge(grid, 1, "Video bellek",
                        f"{used:.0f} / {total:.0f} MB" if used is not None else "—", ratio,
                        ui.DANGER if ratio > 0.92 else ui.PRIMARY)
            fan, power = gpu.get("fan"), gpu.get("power")
            self._gauge(grid, 2, "Fan", f"%{fan:.0f}" if fan is not None else "—",
                        (fan or 0) / 100.0, ui.PRIMARY)
            if power is not None:
                watt = f"{power:.1f}".replace(".", ",")
                tk.Label(self.gpu_body, text=f"Anlık güç tüketimi: {watt} W",
                         font=ui.fonts["small"], fg=ui.MUTED, bg=ui.CARD,
                         anchor="w").pack(fill="x", pady=(px(12), 0))

    @staticmethod
    def _gauge(parent, column: int, title: str, value: str, ratio: float, color: str) -> None:
        box = tk.Frame(parent, bg=ui.CARD)
        box.grid(row=0, column=column, sticky="ew",
                 padx=(0, px(16)) if column < 2 else (0, 0))
        tk.Label(box, text=ui.tr_upper(title), font=ui.fonts["tiny"], fg=ui.SUBTLE, bg=ui.CARD,
                 anchor="w").pack(fill="x")
        tk.Label(box, text=value, font=ui.fonts["number"], fg=ui.FG, bg=ui.CARD,
                 anchor="w").pack(fill="x", pady=(px(4), 0))
        meter = ui.Meter(box, bg=ui.CARD)
        meter.pack(fill="x", pady=(px(8), 0))
        meter.set(max(0.0, min(1.0, ratio)), color)

    def render_disks(self, disks: list[dict], reliability: list[dict], note: str | None) -> None:
        self._clear(self.disk_body)
        by_name = {row["name"]: row for row in reliability}
        if not disks:
            tk.Label(self.disk_body, text="Disk bilgisi okunamadı.", font=ui.fonts["small"],
                     fg=ui.MUTED, bg=ui.CARD, anchor="w").pack(fill="x")
        for disk in disks:
            block = tk.Frame(self.disk_body, bg=ui.CARD)
            block.pack(fill="x", pady=(0, px(14)))
            head = tk.Frame(block, bg=ui.CARD)
            head.pack(fill="x")
            label, tone = core.health_label(disk["health"])
            ui.Badge(head, label, tone, bg=ui.CARD).pack(side="right")
            tk.Label(head, text=f"{disk['media']} · {core.human_bytes(disk['size'])}",
                     font=ui.fonts["small"], fg=ui.MUTED, bg=ui.CARD,
                     anchor="e").pack(side="right", padx=(0, px(10)))
            tk.Label(head, text=disk["name"], font=ui.fonts["body"], fg=ui.FG, bg=ui.CARD,
                     anchor="w").pack(side="left", fill="x", expand=True)

            counters = by_name.get(disk["name"])
            if not counters:
                continue
            grid = tk.Frame(block, bg=ui.CARD)
            grid.pack(fill="x", pady=(px(10), 0))
            for i in range(3):
                grid.columnconfigure(i, weight=1, uniform="disk")
            wear = counters.get("wear")
            self._gauge(grid, 0, "Aşınma",
                        f"%{wear}" if wear is not None else "—", (wear or 0) / 100.0,
                        ui.DANGER if (wear or 0) > 80 else (ui.WARN if (wear or 0) > 50
                                                            else ui.OK))
            temp = counters.get("temperature")
            self._gauge(grid, 1, "Sıcaklık", f"{temp}°C" if temp is not None else "—",
                        (temp or 0) / 80.0,
                        ui.DANGER if (temp or 0) > 70 else (ui.WARN if (temp or 0) > 55
                                                            else ui.OK))
            hours = counters.get("hours")
            self._gauge(grid, 2, "Çalışma süresi",
                        f"{hours:,} saat".replace(",", ".") if hours is not None else "—",
                        min(1.0, (hours or 0) / 43800.0), ui.PRIMARY)
            errors = (counters.get("read_errors") or 0) + (counters.get("write_errors") or 0)
            tk.Label(block, text=f"Toplam okuma/yazma hatası: {errors}",
                     font=ui.fonts["small"], fg=ui.DANGER if errors else ui.MUTED, bg=ui.CARD,
                     anchor="w").pack(fill="x", pady=(px(10), 0))

        if note:
            ui.Alert(self.disk_body, "Aşınma sayaçları okunamadı", note + " ClearFast'i "
                     "yönetici olarak çalıştırdığınızda aşınma, sıcaklık ve hata sayaçları "
                     "da burada görünür.", tone="warn",
                     bg=ui.CARD).pack(fill="x", pady=(px(6), 0))


class LogPage(Page):
    def __init__(self, master, app: "ClearFastApp") -> None:
        super().__init__(master, "İşlem günlüğü",
                         "Bu oturumda yapılan tarama ve temizlik işlemleri.", scroll=False)
        self.app = app
        ui.Button(self.actions, "Temizle", self.clear, variant="ghost",
                  bg=ui.BG).pack(side="right")
        card = ui.Card(self.content, bg=ui.BG, padx=4, pady=4, autoheight=False)
        card.pack(fill="both", expand=True)
        self.text = tk.Text(card.body, bg=ui.CARD, fg=ui.FG, relief="flat", wrap="word",
                            padx=px(14), pady=px(12), font=ui.fonts["mono"],
                            highlightthickness=0, insertwidth=0, cursor="arrow",
                            selectbackground=ui.SUNKEN, selectforeground=ui.FG)
        self.text.pack(fill="both", expand=True)
        self.text.tag_configure("time", foreground=ui.SUBTLE)
        self.text.tag_configure("body", foreground=ui.FG)
        self.text.configure(state="disabled")

    def append(self, message: str) -> None:
        self.text.configure(state="normal")
        self.text.insert("end", time.strftime("%H:%M:%S  "), "time")
        self.text.insert("end", message + "\n", "body")
        self.text.see("end")
        self.text.configure(state="disabled")

    def clear(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")


# --------------------------------------------------------------------------- #
# Uygulama
# --------------------------------------------------------------------------- #

class ClearFastApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        ui.init(self)
        ui.apply_ttk_theme(self)

        self.title(f"{core.APP_NAME} {core.APP_VERSION}")
        self.geometry(f"{px(1120)}x{px(748)}")
        self.minsize(px(980), px(660))
        self.configure(bg=ui.BG)
        self._set_icon()

        self.target_defs = core.targets()
        self.is_admin = core.is_admin()
        self.cpu_monitor = metrics.CpuMonitor()
        self.process_monitor = metrics.ProcessMonitor()
        self.cpu_monitor.sample()          # ilk ornek referans olusturur
        self.process_monitor.sample()
        self.gpus: list[dict] = []
        self.specs: dict = {}
        self.modules: list[dict] = []
        self.active_page = "system"
        self._proc_busy = False
        self._gpu_busy = False
        self._health_loaded = False
        self._tick = 0
        self.working = False
        self._jobs = 0
        # Is parcaciklari sonuclarini buraya birakir; yalnizca ana is parcacigi okur.
        self._results: queue.Queue = queue.Queue()

        self._build_chrome()
        self._build_pages()
        self.select_page("system")

        self._pump()
        self.after(120, self.refresh_system)
        self.after(200, self.scan_cleanup)
        self.after(280, self.scan_watch)
        self.after(1000, self._live_tick)

    def _set_icon(self) -> None:
        ico = resource_path("assets/ClearFast.ico")
        try:
            if ico.exists():
                self.iconbitmap(default=str(ico))
                return
        except tk.TclError:
            pass
        try:
            self.iconphoto(True, ui.app_mark(px(64), ui.BG))
        except tk.TclError:
            pass

    # -- iskelet ------------------------------------------------------------- #
    def _build_chrome(self) -> None:
        header = tk.Frame(self, bg=ui.CARD, height=px(HEADER_H))
        header.pack(fill="x")
        header.pack_propagate(False)
        ui.Separator(self).pack(fill="x")

        brand = tk.Frame(header, bg=ui.CARD)
        brand.pack(side="left", padx=px(22))
        mark = tk.Label(brand, image=ui.app_mark(px(26), ui.CARD), bg=ui.CARD)
        mark.pack(side="left", padx=(0, px(10)))
        tk.Label(brand, text=core.APP_NAME, font=ui.fonts["title"], fg=ui.FG,
                 bg=ui.CARD).pack(side="left")
        ui.Badge(brand, core.APP_VERSION, "outline", bg=ui.CARD).pack(side="left", padx=px(10))

        right = tk.Frame(header, bg=ui.CARD)
        right.pack(side="right", padx=px(22))
        ui.Badge(right, "Yönetici" if self.is_admin else "Standart kullanıcı",
                 "ok" if self.is_admin else "muted", bg=ui.CARD).pack(side="right")

        body = tk.Frame(self, bg=ui.BG)
        body.pack(fill="both", expand=True)

        sidebar = tk.Frame(body, bg=ui.CARD, width=px(SIDEBAR_W))
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        tk.Frame(body, bg=ui.BORDER, width=1).pack(side="left", fill="y")

        nav = tk.Frame(sidebar, bg=ui.CARD)
        nav.pack(fill="x", padx=px(12), pady=px(16))
        self.nav_items: dict[str, NavItem] = {}
        for key, label, glyph in (("system", "Sistem", "monitor"),
                                  ("performance", "Performans", "activity"),
                                  ("health", "Donanım sağlığı", "gauge"),
                                  ("cleaner", "Temizleyici", "sparkle"),
                                  ("protected", "Korunanlar", "lock"),
                                  ("log", "İşlem günlüğü", "list")):
            item = NavItem(nav, label, glyph, lambda k=key: self.select_page(k))
            item.pack(fill="x", pady=px(2))
            self.nav_items[key] = item

        # Alttan yukari dogru: iletisim, ayirac, oturum ozeti.
        ui.LinkBar(sidebar, bg=ui.CARD, fg=ui.SUBTLE, hover_fg=ui.FG,
                   hover_bg=ui.SUNKEN, caption_fg=ui.SUBTLE).pack(
            side="bottom", fill="x", padx=px(16), pady=(px(12), px(16)))
        ui.Separator(sidebar).pack(side="bottom", fill="x", padx=px(16))

        side_foot = tk.Frame(sidebar, bg=ui.CARD)
        side_foot.pack(side="bottom", fill="x", padx=px(16), pady=(0, px(14)))
        self.reclaimed_total = 0
        self.reclaimed_label = tk.Label(side_foot, text="Bu oturumda 0 B kazanıldı",
                                        font=ui.fonts["small"], fg=ui.SUBTLE, bg=ui.CARD,
                                        anchor="w", justify="left", wraplength=px(SIDEBAR_W - 40))
        self.reclaimed_label.pack(fill="x")

        self.page_host = tk.Frame(body, bg=ui.BG)
        self.page_host.pack(side="left", fill="both", expand=True)

        ui.Separator(self).pack(fill="x", side="bottom")
        footer = tk.Frame(self, bg=ui.CARD, height=px(FOOTER_H))
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        self.status = tk.Label(footer, text="Hazır", font=ui.fonts["small"], fg=ui.MUTED,
                               bg=ui.CARD, anchor="w")
        self.status.pack(side="left", padx=px(22))
        self.activity = ui.ActivityBar(footer, bg=ui.CARD)
        self.activity.pack(side="right", padx=px(22))
        self.live = tk.Label(footer, text="", font=ui.fonts["small"], fg=ui.SUBTLE, bg=ui.CARD)
        self.live.pack(side="right", padx=(0, px(16)))

    def _build_pages(self) -> None:
        self.system_page = SystemPage(self.page_host, self)
        self.performance_page = PerformancePage(self.page_host, self)
        self.health_page = HealthPage(self.page_host, self)
        self.cleaner_page = CleanerPage(self.page_host, self)
        self.protected_page = ProtectedPage(self.page_host, self)
        self.log_page = LogPage(self.page_host, self)
        self.pages = {"system": self.system_page, "performance": self.performance_page,
                      "health": self.health_page, "cleaner": self.cleaner_page,
                      "protected": self.protected_page, "log": self.log_page}
        self.log("ClearFast başlatıldı. Varsayılan liste yalnızca önbellek, geçici dosya "
                 "ve günlük klasörlerini hedefler.")

    def select_page(self, key: str) -> None:
        self.active_page = key
        if key == "performance":
            self.refresh_processes()
            self.refresh_gpu()
        elif key == "health" and not self._health_loaded:
            self.refresh_health()
        for name, page in self.pages.items():
            if name == key:
                page.pack(fill="both", expand=True)
            else:
                page.pack_forget()
            self.nav_items[name].set_active(name == key)

    # -- durum --------------------------------------------------------------- #
    def log(self, message: str) -> None:
        self.log_page.append(message)

    def _pump(self) -> None:
        """Is parcaciklarindan gelen sonuclari ana is parcaciginda uygular."""
        while True:
            try:
                callback, args = self._results.get_nowait()
            except queue.Empty:
                break
            callback(*args)
        self.after(40, self._pump)

    def _run_async(self, work, done, quiet: bool = False) -> None:
        """work() arka planda calisir, done(sonuc) ana is parcaciginda cagrilir."""

        def worker() -> None:
            try:
                result = work()
            except Exception as exc:  # arka plan hatasi arayuzu dusurmesin
                if quiet:
                    self._results.put((lambda: None, ()))
                    return
                self._results.put((self._on_worker_error, (exc,)))
                return
            self._results.put((done, (result,)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_worker_error(self, exc: Exception) -> None:
        self.log(f"İşlem sırasında beklenmeyen hata: {exc}")
        self._set_working(False)
        self._end("Hata oluştu")

    def _begin(self, message: str) -> None:
        self._jobs += 1
        self.status.configure(text=message)
        self.activity.start()

    def _end(self, message: str = "Hazır") -> None:
        self._jobs = max(0, self._jobs - 1)
        if self._jobs == 0:
            self.activity.stop()
            self.status.configure(text=message)

    def _set_working(self, value: bool) -> None:
        self.working = value
        self.cleaner_page.scan_btn.set_enabled(not value)
        self.cleaner_page.clean_btn.set_enabled(not value and bool(self.cleaner_page.checked))

    def _live_tick(self) -> None:
        """Saniyede bir: islemci/bellek ucuz olculur, agir isler is parcaciginda."""
        self._tick += 1
        total, avail = core.memory_info()
        used = max(0, total - avail)
        ram_pct = (used / total * 100) if total else 0.0
        cpu_pct = self.cpu_monitor.sample()

        if total:
            self.live.configure(text=f"Bellek %{ram_pct:.0f} · {core.human_bytes(avail)} boş")

        page = self.performance_page
        if cpu_pct is not None:
            page.cpu_card.update(
                f"%{cpu_pct:.0f}",
                f"{self.specs.get('cpu_name') or 'İşlemci'} · {self.cpu_monitor.cores} çekirdek",
                cpu_pct)
        if total:
            page.ram_card.update(f"%{ram_pct:.0f}",
                                 f"{core.human_bytes(used)} / {core.human_bytes(total)} "
                                 f"kullanımda", ram_pct)

        if self.active_page == "performance":
            if self._tick % 2 == 0:
                self.refresh_processes()
            if self._tick % 3 == 0:
                self.refresh_gpu()
        elif self.active_page == "health" and self._tick % 4 == 0:
            self.refresh_gpu()

        self.after(1000, self._live_tick)

    def refresh_processes(self) -> None:
        if self._proc_busy:
            return
        self._proc_busy = True

        def done(rows: list[dict]) -> None:
            self._proc_busy = False
            self.performance_page.render_processes(rows[:self.performance_page.ROWS * 2])

        self._run_async(self.process_monitor.sample, done, quiet=True)

    def refresh_gpu(self) -> None:
        if self._gpu_busy:
            return
        self._gpu_busy = True

        def done(rows: list[dict]) -> None:
            self._gpu_busy = False
            self.gpus = rows
            self.performance_page.render_gpu(rows)
            if self._health_loaded:
                self.health_page.render_gpu(rows, self.system_page.last_gpus)

        self._run_async(metrics.gpu_status, done, quiet=True)

    def refresh_health(self) -> None:
        self._begin("Donanım sağlığı okunuyor…")

        def work() -> dict:
            reliability, note = metrics.storage_reliability()
            return {"modules": metrics.memory_modules(), "gpus": metrics.gpu_status(),
                    "reliability": reliability, "note": note}

        def done(data: dict) -> None:
            self._health_loaded = True
            self.modules = data["modules"] or self.modules
            total = core.memory_info()[0]
            self.health_page.render_memory(self.modules, total)
            self.health_page.render_gpu(data["gpus"], self.system_page.last_gpus)
            self.health_page.render_disks(self.system_page.last_disks, data["reliability"],
                                          data["note"])
            self.log("Donanım sağlığı bilgileri yenilendi.")
            self._end()

        self._run_async(work, done)

    def open_memory_diagnostic(self) -> None:
        if not ui.ask(self, "Windows Bellek Tanılama",
                      "Windows'un bellek testi aracı açılacak.",
                      detail="Test yalnızca bilgisayar yeniden başlatıldığında çalışır; araç "
                             "size şimdi mi yoksa sonraki açılışta mı çalıştıracağınızı "
                             "soracaktır. Açık işlerinizi kaydedin.",
                      tone="warn", confirm="Aracı aç"):
            return
        try:
            os.startfile("mdsched.exe")
            self.log("Windows Bellek Tanılama aracı açıldı.")
        except OSError as exc:
            ui.inform(self, "Araç açılamadı", str(exc), tone="danger")

    # -- isler --------------------------------------------------------------- #
    def refresh_system(self) -> None:
        self._begin("Sistem bilgileri okunuyor…")

        def work() -> dict:
            return {"snap": core.system_snapshot(), "specs": metrics.full_specs(),
                    "modules": metrics.memory_modules()}

        self._run_async(work, self._after_system)

    def _after_system(self, data: dict) -> None:
        snap = data["snap"]
        self.is_admin = snap["admin"]
        self.specs = data["specs"]
        self.modules = data["modules"]
        self.system_page.render(snap, self.specs, self.modules)
        self.health_page.render_memory(self.modules, snap["ram_total"])
        self.log("Sistem bilgileri yenilendi.")
        self._end()

    def scan_cleanup(self) -> None:
        if self.working:
            return
        self._begin("Gereksiz dosyalar taranıyor…")
        self._set_working(True)
        self._run_async(lambda: core.scan_targets(self.target_defs), self._after_scan)

    def _after_scan(self, rows: list[core.ScanRow]) -> None:
        self.cleaner_page.render(rows)
        total = sum(row.size for row in rows)
        self.log(f"Tarama tamamlandı: {len(rows)} konum, toplam {core.human_bytes(total)}.")
        self._set_working(False)
        self._end()

    def scan_watch(self) -> None:
        self._begin("Korunan klasörler ölçülüyor…")
        self._run_async(core.scan_watch, self._after_watch)

    def _after_watch(self, rows) -> None:
        self.protected_page.render(rows)
        if rows:
            total = sum(row[2] for row in rows)
            self.log(f"Korunan depolar ölçüldü: {core.human_bytes(total)} (silinmez).")
        self._end()

    def clean_selected(self) -> None:
        if self.working:
            return
        chosen = self.cleaner_page.selection()
        if not chosen:
            ui.inform(self, "Seçim yok", "Temizlemek için en az bir kaynak seçin.")
            return

        total = sum(row.size for row in chosen)
        by_target: dict[str, int] = {}
        for row in chosen:
            by_target[row.target.title] = by_target.get(row.target.title, 0) + row.size
        items = tuple(f"{title} — {core.human_bytes(size)}"
                      for title, size in sorted(by_target.items(), key=lambda kv: -kv[1]))

        if not ui.ask(self, "Temizliği onaylayın",
                      f"{len(chosen)} konumdaki yaklaşık {core.human_bytes(total)} veri "
                      f"kalıcı olarak silinecek.",
                      items=items[:8],
                      detail="Kilitli veya erişilemeyen dosyalar atlanır. Silinen veriler Geri "
                             "Dönüşüm Kutusu'na gitmez.",
                      tone="danger", confirm="Temizle", confirm_variant="danger"):
            return

        self._begin("Seçili dosyalar temizleniyor…")
        self._set_working(True)

        def work() -> tuple:
            reclaimed = deleted = 0
            errors: list[str] = []
            details: list[tuple[str, Path, int, int]] = []
            for row in chosen:
                count, freed, errs = core.delete_contents(row.path)
                reclaimed += freed
                deleted += count
                errors.extend(errs)
                details.append((row.target.title, row.path, freed, len(errs)))
            return reclaimed, deleted, errors, details

        self._run_async(work, self._after_clean)

    def _after_clean(self, result: tuple) -> None:
        reclaimed, deleted, errors, details = result
        for title, path, size, skipped in details:
            note = f" · {skipped} öğe atlandı" if skipped else ""
            self.log(f"{title}: {core.human_bytes(size)} temizlendi{note}  ({path})")
        self.log(f"Temizlik tamamlandı. Yaklaşık {core.human_bytes(reclaimed)} alan kazanıldı, "
                 f"{deleted} öğe silindi, {len(errors)} öğe atlandı.")
        self.reclaimed_total += reclaimed
        self.reclaimed_label.configure(
            text=f"Bu oturumda {core.human_bytes(self.reclaimed_total)} kazanıldı")
        self._set_working(False)
        self._end()

        ui.inform(self, "Temizlik tamamlandı",
                  f"Yaklaşık {core.human_bytes(reclaimed)} alan kazanıldı.",
                  detail=(f"{deleted} öğe silindi. Kilitli olduğu için atlanan öğe: {len(errors)}."
                          if errors else f"{deleted} öğe silindi."),
                  tone="ok")
        self.scan_cleanup()
        self.after(400, self.scan_watch)


def main() -> None:
    """Tek giris noktasi.

    Kurulum ve kaldirma ayri bir EXE degil, ayni programin bir kipidir:
    ayri bir kurucu ikili gomulu tasimadigi icin virus tarayicilarin
    "dropper" kalibina takilmaz.

        ClearFast.exe              uygulamayi acar
        ClearFast.exe --setup      kurulum sihirbazini acar
        ClearFast.exe --uninstall  kaldirma sihirbazini acar
    """
    if os.name != "nt":
        print("ClearFast su anda yalnizca Windows icin tasarlanmistir.")
        return
    ui.enable_dpi_awareness()
    if "--setup" in sys.argv or "--uninstall" in sys.argv:
        import ClearFastSetup
        ClearFastSetup.run()
        return
    ClearFastApp().mainloop()


if __name__ == "__main__":
    main()
