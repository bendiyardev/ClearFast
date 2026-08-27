# -*- coding: utf-8 -*-
"""ClearFast tasarim sistemi.

shadcn/ui token yaklasimini Tk uzerine tasir: tek bir renk paleti, tek tipografi
olcegi, 4px tabanli bosluk sistemi ve kenari yumusatilmis yuvarlak koseler.
Harici bagimlilik yoktur; yuvarlak koseler cf_raster ile uretilen kucuk PNG
parcalarindan gelir.
"""
from __future__ import annotations

import ctypes
import os
import tkinter as tk
import webbrowser
from tkinter import font as tkfont
from tkinter import ttk

from cf_raster import (Surface, hex_rgba, polygon_mask, sdf_capsule, sdf_circle,
                       sdf_ellipse, sdf_half_plane_above, sdf_intersect, sdf_ring,
                       sdf_round_rect, sdf_stroke)

# --------------------------------------------------------------------------- #
# Renk tokenleri (shadcn "zinc" acik tema)
# --------------------------------------------------------------------------- #
BG = "#FAFAFA"           # uygulama zemini
CARD = "#FFFFFF"         # yuzey
SUNKEN = "#F4F4F5"       # ikincil yuzey / hover
BORDER = "#E4E4E7"
BORDER_STRONG = "#D4D4D8"
FG = "#09090B"           # ana metin
MUTED = "#71717A"        # ikincil metin
SUBTLE = "#A1A1AA"       # ucuncul metin
PRIMARY = "#18181B"
PRIMARY_HOVER = "#27272A"
PRIMARY_FG = "#FAFAFA"

DANGER = "#DC2626"
DANGER_HOVER = "#B91C1C"
DANGER_BG = "#FEF2F2"
DANGER_BORDER = "#FECACA"

WARN = "#B45309"
WARN_BG = "#FFFBEB"
WARN_BORDER = "#FDE68A"

OK = "#15803D"
OK_BG = "#F0FDF4"
OK_BORDER = "#BBF7D0"

INFO = "#3F3F46"
INFO_BG = "#F4F4F5"
INFO_BORDER = "#E4E4E7"

TONES = {
    "info": (INFO, INFO_BG, INFO_BORDER),
    "warn": (WARN, WARN_BG, WARN_BORDER),
    "danger": (DANGER, DANGER_BG, DANGER_BORDER),
    "ok": (OK, OK_BG, OK_BORDER),
}

GLYPH_FOR_TONE = {"info": "info", "warn": "bang", "danger": "bang", "ok": "check"}

# Gelistirici iletisim baglantilari. (ikon, servis, kullanici, adres)
CONTACT_LINKS = (
    ("telegram", "Telegram", "@dyrdev", "https://t.me/dyrdev"),
    ("x", "X", "@diyrdev", "https://x.com/diyrdev"),
    ("github", "GitHub", "bendiyardev", "https://github.com/bendiyardev"),
    ("globe", "R10.net", "dyrdev", "https://www.r10.net/profil/226267-dyrdev.html"),
)
CONTACT_HANDLE = "@dyrdev"

# Yaricaplar (tasarim pikseli; px() ile olceklenir)
R_CARD = 12
R_BUTTON = 8
R_CHECK = 5

_scale = 1.0
fonts: dict[str, tkfont.Font] = {}


# --------------------------------------------------------------------------- #
# DPI ve baslatma
# --------------------------------------------------------------------------- #

def enable_dpi_awareness() -> None:
    """Tk penceresinin bulanik olceklenmesini onler. Tk() cagrilmadan once."""
    if os.name != "nt":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor v2
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def px(value: float) -> int:
    """Tasarim pikselini ekran pikseline cevirir."""
    return int(round(value * _scale))


def _pick_family(root: tk.Misc, candidates: tuple[str, ...], fallback: str) -> str:
    available = {name.lower() for name in tkfont.families(root)}
    for name in candidates:
        if name.lower() in available:
            return name
    return fallback


def init(root: tk.Misc) -> None:
    """Olcek ve tipografiyi hazirlar. Tk() olusturulduktan hemen sonra cagrilir."""
    global _scale
    dpi = root.winfo_fpixels("1i")
    _scale = max(1.0, dpi / 96.0)
    root.tk.call("tk", "scaling", dpi / 72.0)

    ui = _pick_family(root, ("Segoe UI Variable Text", "Segoe UI"), "TkDefaultFont")
    med = _pick_family(root, ("Segoe UI Semibold", "Segoe UI"), ui)
    disp = _pick_family(root, ("Segoe UI Variable Display", "Segoe UI Semibold", "Segoe UI"), med)
    mono = _pick_family(root, ("Cascadia Mono", "Consolas", "Courier New"), "TkFixedFont")

    def mk(family: str, size: int, weight: str = "normal") -> tkfont.Font:
        return tkfont.Font(root=root, family=family, size=size, weight=weight)

    fonts.update({
        "display": mk(disp, 18, "bold"),
        "title": mk(med, 13),
        "section": mk(med, 10),
        "label": mk(med, 9),
        "body": mk(ui, 10),
        "small": mk(ui, 9),
        "tiny": mk(med, 8),
        "number": mk(med, 12),
        "big": mk(disp, 16, "bold"),
        "mono": mk(mono, 8),
        "button": mk(med, 10),
    })


def tr_upper(text: str) -> str:
    """Turkce buyuk harf: i -> I(noktali), i(noktasiz) -> I."""
    return text.replace("i", "İ").replace("ı", "I").upper()


def ellipsize(font: tkfont.Font, text: str, max_px: int) -> str:
    """Metni verilen genislige sigacak sekilde ... ile kisaltir."""
    if max_px <= 0 or font.measure(text) <= max_px:
        return text
    ell = "…"
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if font.measure(text[:mid] + ell) <= max_px:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo] + ell if lo else ell


def bind_tree(widget: tk.Misc, sequence: str, handler) -> None:
    """Bir satirin tum alt bilesenlerine ayni olayi baglar."""
    widget.bind(sequence, handler)
    for child in widget.winfo_children():
        bind_tree(child, sequence, handler)


def open_url(url: str) -> None:
    """Baglantiyi varsayilan tarayicida acar."""
    try:
        webbrowser.open_new_tab(url)
    except Exception:
        pass


def bg_of(widget: tk.Misc) -> str:
    try:
        return str(widget.cget("bg"))
    except tk.TclError:
        return BG


# --------------------------------------------------------------------------- #
# Gorsel onbellek: yuvarlak koseler ve ikonlar
# --------------------------------------------------------------------------- #
_images: dict[tuple, tk.PhotoImage] = {}


def _corner(radius: int, fill: str, border: str | None, bw: int, bg: str, which: str) -> tk.PhotoImage:
    key = ("corner", radius, fill, border, bw, bg, which)
    img = _images.get(key)
    if img is not None:
        return img
    r = float(radius)
    cx = r if which in ("nw", "sw") else 0.0
    cy = r if which in ("nw", "ne") else 0.0
    surf = Surface(radius, radius, hex_rgba(bg))
    if border and bw > 0:
        surf.fill(sdf_circle(cx, cy, r), hex_rgba(border))
        surf.fill(sdf_circle(cx, cy, max(0.0, r - bw)), hex_rgba(fill))
    else:
        surf.fill(sdf_circle(cx, cy, r), hex_rgba(fill))
    img = tk.PhotoImage(data=surf.png_b64())
    _images[key] = img
    return img


def round_rect(canvas: tk.Canvas, x0: int, y0: int, x1: int, y1: int, radius: int,
               fill: str, border: str | None = None, bw: int = 1,
               bg: str | None = None, tags: str = "surface") -> None:
    """Canvas uzerine kenari yumusatilmis yuvarlak dikdortgen cizer."""
    bg = bg or bg_of(canvas)
    w, h = x1 - x0, y1 - y0
    if w <= 0 or h <= 0:
        return
    r = max(0, min(radius, w // 2, h // 2))
    bw = bw if border else 0
    if r:
        for which, ax, ay in (("nw", x0, y0), ("ne", x1 - r, y0),
                              ("sw", x0, y1 - r), ("se", x1 - r, y1 - r)):
            canvas.create_image(ax, ay, image=_corner(r, fill, border, bw, bg, which),
                                anchor="nw", tags=tags)
    if bw:
        canvas.create_rectangle(x0 + r, y0, x1 - r, y0 + bw, fill=border, outline="", tags=tags)
        canvas.create_rectangle(x0 + r, y1 - bw, x1 - r, y1, fill=border, outline="", tags=tags)
        canvas.create_rectangle(x0, y0 + r, x0 + bw, y1 - r, fill=border, outline="", tags=tags)
        canvas.create_rectangle(x1 - bw, y0 + r, x1, y1 - r, fill=border, outline="", tags=tags)
    canvas.create_rectangle(x0 + r, y0 + bw, x1 - r, y1 - bw, fill=fill, outline="", tags=tags)
    if r > bw:
        canvas.create_rectangle(x0 + bw, y0 + r, x0 + r, y1 - r, fill=fill, outline="", tags=tags)
        canvas.create_rectangle(x1 - r, y0 + r, x1 - bw, y1 - r, fill=fill, outline="", tags=tags)


# --------------------------------------------------------------------------- #
# Ikonlar: kapsul/halka SDF'lerinden olusan ince konturlar
# --------------------------------------------------------------------------- #

def _sparkle_mask(cx: float, cy: float, radius: float, power: float = 0.55):
    limit = radius ** power

    def inside(x: float, y: float) -> bool:
        return abs(x - cx) ** power + abs(y - cy) ** power <= limit

    return inside


def _icon_shapes(name: str, s: float, w: float) -> list:
    """s = kutu boyutu, w = kontur kalinligi."""
    if name == "sparkle":
        return [("mask", _sparkle_mask(s * 0.42, s * 0.42, s * 0.34)),
                ("mask", _sparkle_mask(s * 0.75, s * 0.75, s * 0.16))]
    if name == "monitor":
        return [sdf_stroke(sdf_round_rect(s * 0.12, s * 0.16, s * 0.88, s * 0.66, s * 0.10), w),
                sdf_capsule(s * 0.5, s * 0.66, s * 0.5, s * 0.84, w),
                sdf_capsule(s * 0.30, s * 0.86, s * 0.70, s * 0.86, w)]
    if name == "lock":
        return [sdf_stroke(sdf_round_rect(s * 0.16, s * 0.44, s * 0.84, s * 0.88, s * 0.12), w),
                sdf_intersect(sdf_ring(s * 0.5, s * 0.46, s * 0.21, w),
                              sdf_half_plane_above(s * 0.46))]
    if name == "list":
        return [sdf_capsule(s * 0.16, s * 0.26, s * 0.84, s * 0.26, w),
                sdf_capsule(s * 0.16, s * 0.50, s * 0.84, s * 0.50, w),
                sdf_capsule(s * 0.16, s * 0.74, s * 0.62, s * 0.74, w)]
    if name == "activity":
        return [sdf_capsule(s * 0.08, s * 0.5, s * 0.30, s * 0.5, w),
                sdf_capsule(s * 0.30, s * 0.5, s * 0.42, s * 0.18, w),
                sdf_capsule(s * 0.42, s * 0.18, s * 0.58, s * 0.82, w),
                sdf_capsule(s * 0.58, s * 0.82, s * 0.70, s * 0.5, w),
                sdf_capsule(s * 0.70, s * 0.5, s * 0.92, s * 0.5, w)]
    if name == "gauge":
        return [sdf_intersect(sdf_ring(s * 0.5, s * 0.66, s * 0.36, w),
                              sdf_half_plane_above(s * 0.66)),
                sdf_capsule(s * 0.5, s * 0.66, s * 0.68, s * 0.42, w)]
    if name == "telegram":
        # Kagit ucak silueti: tek parca cokgen.
        plane = [(0.96, 0.11), (0.04, 0.46), (0.34, 0.57), (0.41, 0.88),
                 (0.55, 0.66), (0.78, 0.84)]
        return [("mask", polygon_mask([(x * s, y * s) for x, y in plane]))]
    if name == "x":
        thick = w * 1.15
        return [sdf_capsule(s * 0.17, s * 0.17, s * 0.83, s * 0.83, thick),
                sdf_capsule(s * 0.83, s * 0.17, s * 0.17, s * 0.83, thick)]
    if name == "github":
        # Octocat silueti: govde + iki kulak + kuyruk.
        return [sdf_circle(s * 0.5, s * 0.57, s * 0.41),
                sdf_circle(s * 0.31, s * 0.235, s * 0.115),
                sdf_circle(s * 0.69, s * 0.235, s * 0.115),
                sdf_capsule(s * 0.26, s * 0.88, s * 0.35, s * 0.99, w * 1.05)]
    if name == "globe":
        return [sdf_stroke(sdf_circle(s * 0.5, s * 0.5, s * 0.38), w),
                sdf_stroke(sdf_ellipse(s * 0.5, s * 0.5, s * 0.17, s * 0.38), w * 0.9),
                sdf_capsule(s * 0.13, s * 0.5, s * 0.87, s * 0.5, w * 0.9)]
    if name == "check":
        return [sdf_capsule(s * 0.22, s * 0.52, s * 0.42, s * 0.72, w),
                sdf_capsule(s * 0.42, s * 0.72, s * 0.79, s * 0.29, w)]
    if name == "bang":
        return [sdf_capsule(s * 0.5, s * 0.20, s * 0.5, s * 0.56, w),
                sdf_circle(s * 0.5, s * 0.78, w * 0.62)]
    if name == "info":
        return [sdf_circle(s * 0.5, s * 0.22, w * 0.62),
                sdf_capsule(s * 0.5, s * 0.42, s * 0.5, s * 0.78, w)]
    if name == "cross":
        return [sdf_capsule(s * 0.27, s * 0.27, s * 0.73, s * 0.73, w),
                sdf_capsule(s * 0.73, s * 0.27, s * 0.27, s * 0.73, w)]
    if name == "download":
        return [sdf_capsule(s * 0.5, s * 0.14, s * 0.5, s * 0.60, w),
                sdf_capsule(s * 0.28, s * 0.40, s * 0.5, s * 0.62, w),
                sdf_capsule(s * 0.72, s * 0.40, s * 0.5, s * 0.62, w),
                sdf_capsule(s * 0.16, s * 0.84, s * 0.84, s * 0.84, w)]
    raise KeyError(name)


def icon(name: str, size: int, color: str, bg: str, stroke: float = 0.115) -> tk.PhotoImage:
    """Onbellekli, kenari yumusatilmis ikon."""
    key = ("icon", name, size, color, bg, stroke)
    img = _images.get(key)
    if img is not None:
        return img
    surf = Surface(size, size, hex_rgba(bg))
    rgba = hex_rgba(color)
    for shape in _icon_shapes(name, float(size), max(1.4, size * stroke)):
        if isinstance(shape, tuple) and shape[0] == "mask":
            surf.fill_mask(shape[1], rgba, ss=4)
        else:
            surf.fill(shape, rgba)
    img = tk.PhotoImage(data=surf.png_b64())
    _images[key] = img
    return img


def sparkle_mark(size: int, color: str, bg: str) -> tk.PhotoImage:
    """Zeminsiz parilti isareti (koyu yuzeyler icin)."""
    key = ("sparkle_mark", size, color, bg)
    img = _images.get(key)
    if img is not None:
        return img
    surf = Surface(size, size, hex_rgba(bg))
    rgba = hex_rgba(color)
    surf.fill_mask(_sparkle_mask(size * 0.40, size * 0.40, size * 0.34), rgba, ss=4)
    surf.fill_mask(_sparkle_mask(size * 0.76, size * 0.76, size * 0.17), rgba, ss=4)
    img = tk.PhotoImage(data=surf.png_b64())
    _images[key] = img
    return img


def app_mark(size: int, bg: str) -> tk.PhotoImage:
    """Uygulama isareti: koyu yuvarlak kare + beyaz parilti."""
    key = ("mark", size, bg)
    img = _images.get(key)
    if img is not None:
        return img
    surf = Surface(size, size, hex_rgba(bg))
    surf.fill(sdf_round_rect(0, 0, size, size, size * 0.226), hex_rgba(PRIMARY))
    white = hex_rgba("#FFFFFF")
    surf.fill_mask(_sparkle_mask(size * 0.435, size * 0.415, size * 0.30), white, ss=4)
    surf.fill_mask(_sparkle_mask(size * 0.715, size * 0.700, size * 0.150), white, ss=4)
    img = tk.PhotoImage(data=surf.png_b64())
    _images[key] = img
    return img


# --------------------------------------------------------------------------- #
# Bilesenler
# --------------------------------------------------------------------------- #

class Panel(tk.Canvas):
    """Yuvarlak koseli, icine widget alan zemin. Alt sinifi: Card, Alert."""

    def __init__(self, master, *, fill: str = CARD, border: str | None = BORDER,
                 radius: int = R_CARD, padx: int = 20, pady: int = 16,
                 bg: str | None = None, autoheight: bool = True, bw: int = 1) -> None:
        self._bg = bg or bg_of(master)
        super().__init__(master, bg=self._bg, highlightthickness=0, bd=0,
                         width=px(240), height=px(64))
        self._fill, self._border, self._bw = fill, border, px(bw)
        self._radius = px(radius)
        self._padx, self._pady = px(padx), px(pady)
        self._autoheight = autoheight
        self._min_height = 0
        self.body = tk.Frame(self, bg=fill)
        self._wid = self.create_window(self._padx, self._pady, anchor="nw", window=self.body)
        self.bind("<Configure>", self._on_resize)
        if autoheight:
            self.body.bind("<Configure>", self._on_body)

    def _on_body(self, event) -> None:
        # Icerik yeniden olusturulurken gecici olarak kuculmesin.
        content = max(event.height, self.body.winfo_reqheight())
        wanted = max(content + 2 * self._pady, self._min_height)
        if abs(self.winfo_height() - wanted) > 1:
            self.configure(height=wanted)

    def set_min_height(self, value: int) -> None:
        """Yan yana duran kartlarin ayni yukseklikte kalmasi icin."""
        self._min_height = value
        wanted = max(self.body.winfo_reqheight() + 2 * self._pady, value)
        if abs(self.winfo_height() - wanted) > 1:
            self.configure(height=wanted)

    def _on_resize(self, event) -> None:
        self.itemconfigure(self._wid, width=max(1, event.width - 2 * self._padx))
        if not self._autoheight:
            self.itemconfigure(self._wid, height=max(1, event.height - 2 * self._pady))
        self.delete("surface")
        round_rect(self, 0, 0, event.width, event.height, self._radius,
                   self._fill, self._border, self._bw, self._bg)
        self.tag_lower("surface")


class Card(Panel):
    pass


class Alert(Panel):
    """Baslik + aciklama + ton ikonu olan uyari kutusu."""

    def __init__(self, master, title: str, body: str, tone: str = "info", **kw) -> None:
        color, back, edge = TONES[tone]
        kw.setdefault("padx", 14)
        kw.setdefault("pady", 12)
        super().__init__(master, fill=back, border=edge, radius=10, **kw)
        self._tone = tone
        size = px(15)
        holder = tk.Frame(self.body, bg=back)
        holder.pack(side="left", anchor="n", padx=(0, px(10)), pady=(px(1), 0))
        tk.Label(holder, image=icon(GLYPH_FOR_TONE[tone], size, color, back), bg=back).pack()
        text = tk.Frame(self.body, bg=back)
        text.pack(side="left", fill="both", expand=True)
        self._title = tk.Label(text, text=title, font=fonts["label"], fg=color, bg=back,
                               anchor="w", justify="left")
        self._title.pack(fill="x")
        self._body = tk.Label(text, text=body, font=fonts["small"], fg=MUTED, bg=back,
                              anchor="w", justify="left", wraplength=px(620))
        self._body.pack(fill="x", pady=(px(2), 0))
        text.bind("<Configure>",
                  lambda e: self._body.configure(wraplength=max(px(160), e.width - px(4))))

    def update_text(self, title: str, body: str) -> None:
        self._title.configure(text=title)
        self._body.configure(text=body)


_BUTTON_VARIANTS = {
    "primary": dict(fill=PRIMARY, fg=PRIMARY_FG, border=PRIMARY,
                    hover=PRIMARY_HOVER, hover_border=PRIMARY_HOVER),
    "secondary": dict(fill=SUNKEN, fg=FG, border=SUNKEN, hover=BORDER, hover_border=BORDER),
    "outline": dict(fill=CARD, fg=FG, border=BORDER, hover=SUNKEN, hover_border=BORDER_STRONG),
    "ghost": dict(fill=None, fg=MUTED, border=None, hover=SUNKEN, hover_border=None),
    "danger": dict(fill=DANGER, fg="#FFFFFF", border=DANGER,
                   hover=DANGER_HOVER, hover_border=DANGER_HOVER),
}


class Button(tk.Canvas):
    """Kenari yumusatilmis, hover/press/disabled durumlu dugme."""

    def __init__(self, master, text: str, command=None, *, variant: str = "secondary",
                 icon_name: str | None = None, width: int | None = None,
                 height: int = 34, radius: int = R_BUTTON, pad: int = 15,
                 bg: str | None = None) -> None:
        self._bg = bg or bg_of(master)
        self._spec = _BUTTON_VARIANTS[variant]
        self._text, self._command = text, command
        self._icon_name = icon_name
        self._hover = False
        self._pressed = False
        self._enabled = True
        icon_w = px(15) + px(7) if icon_name else 0
        w = width if width is not None else fonts["button"].measure(text) + 2 * px(pad) + icon_w
        super().__init__(master, bg=self._bg, highlightthickness=0, bd=0,
                         width=w, height=px(height), cursor="hand2")
        self._radius = px(radius)
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def set_enabled(self, value: bool) -> None:
        if self._enabled != value:
            self._enabled = value
            self._hover = self._pressed = False
            self.configure(cursor="hand2" if value else "arrow")
            self._draw()

    def set_text(self, text: str) -> None:
        if self._text != text:
            self._text = text
            self._draw()

    def _on_enter(self, _e=None) -> None:
        if self._enabled:
            self._hover = True
            self._draw()

    def _on_leave(self, _e=None) -> None:
        self._hover = self._pressed = False
        self._draw()

    def _on_press(self, _e=None) -> None:
        if self._enabled:
            self._pressed = True
            self._draw()

    def _on_release(self, event=None) -> None:
        was = self._pressed
        self._pressed = False
        self._draw()
        if not (was and self._enabled and self._command):
            return
        if event is None or (0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height()):
            self._command()

    def _draw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1 or h <= 1:
            return
        spec = self._spec
        if not self._enabled:
            fill = SUNKEN if spec["fill"] else self._bg
            border = BORDER if spec["border"] else None
            fg = SUBTLE
        elif self._hover or self._pressed:
            fill, border, fg = spec["hover"], spec["hover_border"], spec["fg"]
        else:
            fill, border, fg = spec["fill"], spec["border"], spec["fg"]
        if fill is None:
            fill = self._bg
        round_rect(self, 0, 0, w, h, self._radius, fill, border, px(1), self._bg)
        cy = h // 2
        if self._icon_name:
            size = px(15)
            gap = px(7)
            total = size + gap + fonts["button"].measure(self._text)
            x = (w - total) // 2
            self.create_image(x, cy - size // 2, image=icon(self._icon_name, size, fg, fill),
                              anchor="nw")
            self.create_text(x + size + gap, cy + 1, text=self._text, font=fonts["button"],
                             fill=fg, anchor="w")
        else:
            self.create_text(w // 2, cy + 1, text=self._text, font=fonts["button"], fill=fg)


class Badge(tk.Canvas):
    """Kucuk hap seklinde durum etiketi."""

    def __init__(self, master, text: str, tone: str = "muted", bg: str | None = None,
                 height: int = 20) -> None:
        parent_bg = bg or bg_of(master)
        fg, fill, edge = {
            "muted": (MUTED, SUNKEN, SUNKEN),
            "outline": (MUTED, parent_bg, BORDER),
            "ok": (OK, OK_BG, OK_BORDER),
            "warn": (WARN, WARN_BG, WARN_BORDER),
            "danger": (DANGER, DANGER_BG, DANGER_BORDER),
            "solid": (PRIMARY_FG, PRIMARY, PRIMARY),
        }[tone]
        # Not: tkinter.Misc widget yolunu self._w icinde tutar; o ad kullanilamaz.
        self._pill_h = px(height)
        self._pill_w = fonts["tiny"].measure(text) + 2 * px(9)
        self._text, self._fg, self._fill, self._edge = text, fg, fill, edge
        self._bg = parent_bg
        super().__init__(master, bg=parent_bg, highlightthickness=0, bd=0,
                         width=self._pill_w, height=self._pill_h)
        self._draw()

    def set_bg(self, color: str) -> None:
        """Satir uzerine gelindiginde rozetin zemini de degissin."""
        if self._bg != color:
            self._bg = color
            self.configure(bg=color)
            self._draw()

    def _draw(self) -> None:
        self.delete("all")
        round_rect(self, 0, 0, self._pill_w, self._pill_h, self._pill_h // 2,
                   self._fill, self._edge, px(1), self._bg)
        self.create_text(self._pill_w // 2, self._pill_h // 2 + 1, text=self._text,
                         font=fonts["tiny"], fill=self._fg)


class Checkbox(tk.Canvas):
    def __init__(self, master, *, size: int = 18, command=None, bg: str | None = None) -> None:
        self._bg = bg or bg_of(master)
        self._size = px(size)
        self._checked = False
        self._command = command
        super().__init__(master, bg=self._bg, highlightthickness=0, bd=0,
                         width=self._size, height=self._size, cursor="hand2")
        self._draw()
        self.bind("<Button-1>", self._toggle)

    def _toggle(self, _e=None) -> str:
        self.set(not self._checked)
        if self._command:
            self._command(self._checked)
        return "break"

    def set(self, value: bool) -> None:
        if self._checked != value:
            self._checked = value
            self._draw()

    def get(self) -> bool:
        return self._checked

    def set_bg(self, color: str) -> None:
        if self._bg != color:
            self._bg = color
            self.configure(bg=color)
            self._draw()

    def _draw(self) -> None:
        self.delete("all")
        s = self._size
        if self._checked:
            round_rect(self, 0, 0, s, s, px(R_CHECK), PRIMARY, PRIMARY, px(1), self._bg)
            self.create_image(0, 0, anchor="nw",
                              image=icon("check", s, PRIMARY_FG, PRIMARY, stroke=0.135))
        else:
            round_rect(self, 0, 0, s, s, px(R_CHECK), CARD, BORDER_STRONG, px(1), self._bg)


class Meter(tk.Canvas):
    """Ince doluluk cubugu."""

    def __init__(self, master, *, height: int = 6, bg: str | None = None) -> None:
        self._bg = bg or bg_of(master)
        self._value = 0.0
        self._color = PRIMARY
        super().__init__(master, bg=self._bg, highlightthickness=0, bd=0, height=px(height))
        self.bind("<Configure>", lambda e: self._draw())

    def set(self, value: float, color: str | None = None) -> None:
        self._value = max(0.0, min(1.0, value))
        if color:
            self._color = color
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1:
            return
        round_rect(self, 0, 0, w, h, h // 2, SUNKEN, None, 0, self._bg)
        filled = int(w * self._value)
        if filled >= 2:
            round_rect(self, 0, 0, max(filled, h), h, h // 2, self._color, None, 0, self._bg)


class ActivityBar(tk.Canvas):
    """Belirsiz sureli islem gostergesi."""

    def __init__(self, master, *, width: int = 148, height: int = 4, bg: str | None = None) -> None:
        self._bg = bg or bg_of(master)
        super().__init__(master, bg=self._bg, highlightthickness=0, bd=0,
                         width=px(width), height=px(height))
        self._pos = 0.0
        self._running = False
        self._job = None
        self.bind("<Configure>", lambda e: self._draw())

    def start(self) -> None:
        if not self._running:
            self._running = True
            self._tick()

    def stop(self) -> None:
        self._running = False
        if self._job:
            self.after_cancel(self._job)
            self._job = None
        self._draw()

    def _tick(self) -> None:
        if not self._running:
            return
        self._pos = (self._pos + 0.02) % 1.0
        self._draw()
        self._job = self.after(20, self._tick)

    def _draw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1:
            return
        round_rect(self, 0, 0, w, h, h // 2, SUNKEN, None, 0, self._bg)
        if not self._running:
            return
        span = max(px(24), int(w * 0.34))
        travel = w + span
        x0 = int(self._pos * travel) - span
        x1 = min(w, x0 + span)
        x0 = max(0, x0)
        if x1 - x0 > 2:
            round_rect(self, x0, 0, x1, h, h // 2, PRIMARY, None, 0, self._bg)


class Input(tk.Canvas):
    """Metin girisi: yuvarlak kose, odakta belirginlesen kenar."""

    def __init__(self, master, textvariable: tk.StringVar, *, bg: str | None = None,
                 height: int = 36, pad: int = 12) -> None:
        self._bg = bg or bg_of(master)
        self._focused = False
        h = px(height)
        super().__init__(master, bg=self._bg, highlightthickness=0, bd=0,
                         width=px(240), height=h)
        self._pad = px(pad)
        self.entry = tk.Entry(self, textvariable=textvariable, relief="flat", bd=0,
                              bg=CARD, fg=FG, font=fonts["body"], highlightthickness=0,
                              insertbackground=FG, selectbackground=SUNKEN,
                              selectforeground=FG)
        self._wid = self.create_window(self._pad, h // 2, anchor="w", window=self.entry)
        self.bind("<Configure>", lambda e: self._draw())
        self.entry.bind("<FocusIn>", lambda e: self._set_focus(True))
        self.entry.bind("<FocusOut>", lambda e: self._set_focus(False))
        self.bind("<Button-1>", lambda e: self.entry.focus_set())

    def _set_focus(self, value: bool) -> None:
        self._focused = value
        self._draw()

    def _draw(self) -> None:
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1:
            return
        self.delete("surface")
        round_rect(self, 0, 0, w, h, px(R_BUTTON), CARD,
                   SUBTLE if self._focused else BORDER, px(1), self._bg)
        self.tag_lower("surface")
        self.itemconfigure(self._wid, width=max(px(40), w - 2 * self._pad),
                           height=h - px(8))


class CheckRow(tk.Frame):
    """Kutucuk + baslik + aciklama; her yerine tiklanabilir."""

    def __init__(self, master, title: str, description: str = "", *, checked: bool = True,
                 bg: str | None = None, command=None) -> None:
        back = bg or bg_of(master)
        super().__init__(master, bg=back, cursor="hand2")
        self._command = command
        self.check = Checkbox(self, size=17, bg=back, command=lambda _v: self._changed())
        self.check.pack(side="left", anchor="n", padx=(0, px(10)), pady=(px(1), 0))
        texts = tk.Frame(self, bg=back)
        texts.pack(side="left", fill="x", expand=True)
        tk.Label(texts, text=title, font=fonts["body"], fg=FG, bg=back,
                 anchor="w").pack(fill="x")
        if description:
            tk.Label(texts, text=description, font=fonts["small"], fg=MUTED, bg=back,
                     anchor="w", justify="left").pack(fill="x", pady=(px(1), 0))
        self.check.set(checked)
        for widget in (self, texts, *texts.winfo_children()):
            widget.bind("<Button-1>", self._toggle)

    def _toggle(self, _e=None) -> str:
        self.check.set(not self.check.get())
        self._changed()
        return "break"

    def _changed(self) -> None:
        if self._command:
            self._command(self.check.get())

    def get(self) -> bool:
        return self.check.get()


class LineChart(tk.Canvas):
    """Zaman serisi alan grafigi: izgara + dolgu + cizgi + son deger noktasi."""

    def __init__(self, master, *, points: int = 60, height: int = 96, color: str = PRIMARY,
                 tint: str = "#E4E4E7", y_max: float = 100.0, bg: str | None = None,
                 grid: int = 4) -> None:
        self._bg = bg or bg_of(master)
        super().__init__(master, bg=self._bg, highlightthickness=0, bd=0,
                         width=px(220), height=px(height))
        self._points = points
        self._color = color
        self._tint = tint
        self._y_max = y_max
        self._grid = grid
        self._values: list[float] = []
        self.bind("<Configure>", lambda e: self._draw())

    def push(self, value: float | None) -> None:
        if value is None:
            return
        self._values.append(max(0.0, float(value)))
        if len(self._values) > self._points:
            del self._values[:len(self._values) - self._points]
        self._draw()

    def reset(self) -> None:
        self._values.clear()
        self._draw()

    def set_scale(self, y_max: float) -> None:
        if y_max > 0 and abs(self._y_max - y_max) > 1e-6:
            self._y_max = y_max
            self._draw()

    def _draw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1 or h <= 1:
            return
        pad = px(2)
        top, bottom = pad, h - pad

        for i in range(self._grid + 1):
            y = top + (bottom - top) * i / self._grid
            self.create_line(0, y, w, y, fill=BORDER if i else BORDER_STRONG, width=1)

        if len(self._values) < 2:
            return
        step = w / max(1, self._points - 1)
        start = self._points - len(self._values)
        coords: list[float] = []
        for index, value in enumerate(self._values):
            x = (start + index) * step
            ratio = min(1.0, value / self._y_max) if self._y_max else 0.0
            coords.extend((x, bottom - (bottom - top) * ratio))

        area = [coords[0], bottom] + coords + [coords[-2], bottom]
        self.create_polygon(area, fill=self._tint, outline="", width=0)
        self.create_line(coords, fill=self._color, width=px(2), joinstyle="round",
                         capstyle="round")
        self.create_oval(coords[-2] - px(3), coords[-1] - px(3),
                         coords[-2] + px(3), coords[-1] + px(3),
                         fill=self._color, outline=self._bg, width=px(2))


class IconButton(tk.Canvas):
    """Yalnizca ikondan olusan kucuk dugme; uzerine gelince zemini belirir."""

    def __init__(self, master, icon_name: str, command=None, *, box: int = 30,
                 size: int = 17, bg: str | None = None, fg: str = MUTED,
                 hover_fg: str = FG, hover_bg: str = SUNKEN, on_hover=None,
                 radius: int = R_BUTTON) -> None:
        self._bg = bg or bg_of(master)
        super().__init__(master, bg=self._bg, highlightthickness=0, bd=0,
                         width=px(box), height=px(box), cursor="hand2")
        self._icon = icon_name
        self._command = command
        self._fg, self._hover_fg, self._hover_bg = fg, hover_fg, hover_bg
        self._size = px(size)
        self._radius = px(radius)
        self._hover = False
        self._on_hover = on_hover
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<Button-1>", self._click)

    def _set_hover(self, value: bool) -> None:
        self._hover = value
        self._draw()
        if self._on_hover:
            self._on_hover(value)

    def _click(self, _e=None) -> str:
        if self._command:
            self._command()
        return "break"

    def _draw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1:
            return
        fill = self._hover_bg if self._hover else self._bg
        color = self._hover_fg if self._hover else self._fg
        round_rect(self, 0, 0, w, h, self._radius, fill, None, 0, self._bg)
        self.create_image((w - self._size) // 2, (h - self._size) // 2, anchor="nw",
                          image=icon(self._icon, self._size, color, fill))


class LinkBar(tk.Frame):
    """Iletisim baglantilari: ikon satiri + uzerine gelinince degisen aciklama."""

    def __init__(self, master, *, bg: str | None = None, fg: str = MUTED,
                 hover_fg: str = FG, hover_bg: str = SUNKEN, caption_fg: str = SUBTLE,
                 title: str | None = "İletişim", box: int = 30, size: int = 17) -> None:
        back = bg or bg_of(master)
        super().__init__(master, bg=back)
        if title:
            tk.Label(self, text=tr_upper(title), font=fonts["tiny"], fg=caption_fg,
                     bg=back, anchor="w").pack(fill="x", pady=(0, px(6)))
        row = tk.Frame(self, bg=back)
        row.pack(fill="x")
        for index, (glyph, service, handle, url) in enumerate(CONTACT_LINKS):
            button = IconButton(
                row, glyph, lambda u=url: open_url(u), box=box, size=size, bg=back,
                fg=fg, hover_fg=hover_fg, hover_bg=hover_bg,
                on_hover=lambda active, s=service, h=handle: self._caption(active, s, h))
            button.pack(side="left", padx=(0, px(2)) if index < len(CONTACT_LINKS) - 1 else 0)
        self._caption_label = tk.Label(self, text=CONTACT_HANDLE, font=fonts["small"],
                                       fg=caption_fg, bg=back, anchor="w")
        self._caption_label.pack(fill="x", pady=(px(6), 0))

    def _caption(self, active: bool, service: str, handle: str) -> None:
        self._caption_label.configure(text=f"{service} · {handle}" if active
                                      else CONTACT_HANDLE)


class Separator(tk.Frame):
    def __init__(self, master, color: str = BORDER, **kw) -> None:
        super().__init__(master, bg=color, height=1, **kw)


class ScrollArea(tk.Frame):
    """Kaydirilabilir alan + gerektiginde beliren ince kaydirma cubugu."""

    def __init__(self, master, *, bg: str | None = None, padx: int = 0, pady: int = 0) -> None:
        back = bg or bg_of(master)
        super().__init__(master, bg=back)
        # Varsayilan Canvas istegi (7c ~ 265px) yaninda duran sabit yukseklikli
        # bilesenleri ezdigi icin istenen boyut bilerek kucuk tutulur.
        self.canvas = tk.Canvas(self, bg=back, highlightthickness=0, bd=0, width=px(200), height=px(40))
        self.inner = tk.Frame(self.canvas, bg=back)
        self._padx, self._pady = px(padx), px(pady)
        self._wid = self.canvas.create_window(self._padx, self._pady, anchor="nw",
                                              window=self.inner)
        self.bar = ttk.Scrollbar(self, orient="vertical", style="Cf.Vertical.TScrollbar",
                                 command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self._on_scroll)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Configure>", self._on_resize)
        self.inner.bind("<Configure>", self._on_inner)
        self.bind("<Enter>", lambda e: self._wheel(True))
        self.bind("<Leave>", lambda e: self._wheel(False))

    def _wheel(self, on: bool) -> None:
        if on:
            self.canvas.bind_all("<MouseWheel>", self._on_wheel)
        else:
            self.canvas.unbind_all("<MouseWheel>")

    def _on_wheel(self, event) -> None:
        if self.canvas.yview() == (0.0, 1.0):
            return
        self.canvas.yview_scroll(-1 * (event.delta // 120), "units")

    def _on_scroll(self, first: str, last: str) -> None:
        if float(first) <= 0.0 and float(last) >= 1.0:
            self.bar.pack_forget()
        else:
            self.bar.pack(side="right", fill="y", padx=(px(4), 0))
        self.bar.set(first, last)

    def _on_resize(self, event) -> None:
        self.canvas.itemconfigure(self._wid, width=max(1, event.width - 2 * self._padx))

    def _on_inner(self, _event=None) -> None:
        bbox = self.canvas.bbox("all")
        if bbox:
            self.canvas.configure(scrollregion=(0, 0, bbox[2], bbox[3] + self._pady))


def apply_ttk_theme(root: tk.Misc) -> None:
    """Yalnizca kaydirma cubugu icin; geri kalan her sey ozel cizim."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.layout("Cf.Vertical.TScrollbar", [
        ("Vertical.Scrollbar.trough", {
            "children": [("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})],
            "sticky": "ns"})])
    style.configure("Cf.Vertical.TScrollbar", troughcolor=BG, background=BORDER_STRONG,
                    bordercolor=BG, lightcolor=BORDER_STRONG, darkcolor=BORDER_STRONG,
                    relief="flat", width=px(6))
    style.map("Cf.Vertical.TScrollbar", background=[("active", SUBTLE)])


# --------------------------------------------------------------------------- #
# Iletisim kutusu
# --------------------------------------------------------------------------- #

class Dialog(tk.Toplevel):
    """Uygulama diliyle uyumlu onay/bilgi penceresi."""

    def __init__(self, parent: tk.Misc, title: str, message: str, *,
                 detail: str = "", items: tuple[str, ...] = (), tone: str = "info",
                 confirm: str = "Devam et", cancel: str | None = "Vazgeç",
                 confirm_variant: str = "primary", width: int = 460) -> None:
        super().__init__(parent, bg=CARD)
        self.result = False
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        try:
            self.iconphoto(False, app_mark(px(32), CARD))
        except tk.TclError:
            pass

        color, tone_bg, tone_edge = TONES[tone]
        pad = px(24)
        inner_w = px(width) - 2 * pad
        wrap = inner_w - px(46)

        # Yukseklik icerikten gelsin: pack_propagate(False) burada baslik satirini
        # kirpiyordu, cunku istenen yukseklik yerlesimden once 1'dir.
        head = tk.Frame(self, bg=CARD)
        head.pack(fill="x", padx=pad, pady=(pad, 0))

        badge = tk.Canvas(head, bg=CARD, highlightthickness=0, bd=0, width=px(34), height=px(34))
        badge.pack(side="left", anchor="n", padx=(0, px(12)))
        round_rect(badge, 0, 0, px(34), px(34), px(9), tone_bg, tone_edge, px(1), CARD)
        badge.create_image(px(17) - px(8), px(17) - px(8), anchor="nw",
                           image=icon(GLYPH_FOR_TONE[tone], px(16), color, tone_bg))

        texts = tk.Frame(head, bg=CARD)
        texts.pack(side="left", fill="both", expand=True)
        tk.Label(texts, text=title, font=fonts["title"], fg=FG, bg=CARD,
                 anchor="w", justify="left", wraplength=wrap).pack(fill="x")
        tk.Label(texts, text=message, font=fonts["body"], fg=MUTED, bg=CARD,
                 anchor="w", justify="left", wraplength=wrap).pack(fill="x", pady=(px(6), 0))

        if items:
            box = Card(self, fill=SUNKEN, border=BORDER, radius=10, padx=14, pady=11, bg=CARD)
            box.pack(fill="x", padx=pad, pady=(px(16), 0))
            for line in items:
                row = tk.Frame(box.body, bg=SUNKEN)
                row.pack(fill="x", pady=px(1))
                tk.Label(row, text="•", font=fonts["small"], fg=SUBTLE,
                         bg=SUNKEN).pack(side="left", padx=(0, px(8)))
                tk.Label(row, text=line, font=fonts["small"], fg=FG, bg=SUNKEN, anchor="w",
                         justify="left", wraplength=inner_w - px(40)).pack(side="left",
                                                                          fill="x", expand=True)

        if detail:
            tk.Label(self, text=detail, font=fonts["small"], fg=SUBTLE, bg=CARD, anchor="w",
                     justify="left", wraplength=inner_w).pack(fill="x", padx=pad, pady=(px(14), 0))

        Separator(self).pack(fill="x", pady=(px(20), 0))
        actions = tk.Frame(self, bg=CARD)
        actions.pack(fill="x", padx=pad, pady=px(15))
        Button(actions, confirm, self._ok, variant=confirm_variant, bg=CARD).pack(side="right")
        if cancel:
            Button(actions, cancel, self._cancel, variant="outline",
                   bg=CARD).pack(side="right", padx=(0, px(8)))

        self.update_idletasks()
        self._center(parent)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda e: self._cancel())
        self.bind("<Return>", lambda e: self._ok())
        self.grab_set()
        self.focus_force()

    def _center(self, parent: tk.Misc) -> None:
        w = max(self.winfo_reqwidth(), px(460))
        h = self.winfo_reqheight()
        try:
            ox, oy = parent.winfo_rootx(), parent.winfo_rooty()
            pw, ph = parent.winfo_width(), parent.winfo_height()
        except tk.TclError:
            ox = oy = 0
            pw, ph = self.winfo_screenwidth(), self.winfo_screenheight()
        x = max(0, ox + (pw - w) // 2)
        y = max(0, oy + (ph - h) // 3)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _ok(self) -> None:
        self.result = True
        self.destroy()

    def _cancel(self) -> None:
        self.result = False
        self.destroy()


def ask(parent: tk.Misc, title: str, message: str, **kw) -> bool:
    dlg = Dialog(parent, title, message, **kw)
    parent.wait_window(dlg)
    return dlg.result


def inform(parent: tk.Misc, title: str, message: str, **kw) -> None:
    kw.setdefault("confirm", "Tamam")
    kw.setdefault("cancel", None)
    dlg = Dialog(parent, title, message, **kw)
    parent.wait_window(dlg)
