# -*- coding: utf-8 -*-
"""Bagimliliksiz raster katmani.

Tk'nin Canvas'i kenar yumusatma yapmaz. Bu modul kucuk PNG'leri saf Python ile
uretir (zlib + struct) ve tk.PhotoImage'a base64 olarak verir. Boylece yuvarlak
kose, rozet ve ikonlar keskin/purüzsüz gorunur. Ayni kod uygulama .ico dosyasini
da uretir.
"""
from __future__ import annotations

import base64
import struct
import zlib
from math import hypot

RGBA = tuple


def hex_rgba(value: str, alpha: float = 1.0) -> RGBA:
    """'#RRGGBB' -> (r, g, b, a)."""
    v = value.lstrip("#")
    return (int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16), max(0.0, min(1.0, alpha)))


# --------------------------------------------------------------------------- #
# Isaretli mesafe fonksiyonlari (SDF). Negatif = sekil icinde.
# --------------------------------------------------------------------------- #

def sdf_round_rect(x0: float, y0: float, x1: float, y1: float, r: float):
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    bx, by = max(0.0, (x1 - x0) / 2.0 - r), max(0.0, (y1 - y0) / 2.0 - r)

    def f(px: float, py: float) -> float:
        qx, qy = abs(px - cx) - bx, abs(py - cy) - by
        return hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0) - r

    return f


def sdf_circle(cx: float, cy: float, rad: float):
    def f(px: float, py: float) -> float:
        return hypot(px - cx, py - cy) - rad

    return f


def sdf_capsule(x0: float, y0: float, x1: float, y1: float, width: float):
    """Yuvarlak uclu cizgi parcasi; Lucide tarzi ikon konturlari icin."""
    dx, dy = x1 - x0, y1 - y0
    denom = dx * dx + dy * dy or 1.0
    half = width / 2.0

    def f(px: float, py: float) -> float:
        t = ((px - x0) * dx + (py - y0) * dy) / denom
        t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
        return hypot(px - (x0 + t * dx), py - (y0 + t * dy)) - half

    return f


def sdf_ellipse(cx: float, cy: float, rx: float, ry: float):
    """Yaklasik elips mesafesi; kenar yumusatma icin yeterli dogrulukta."""
    scale = min(rx, ry)

    def f(px: float, py: float) -> float:
        return (hypot((px - cx) / rx, (py - cy) / ry) - 1.0) * scale

    return f


def polygon_mask(points: list):
    """Cokgen ic/dis testi (isin atma). fill_mask ile kullanilir."""

    def inside(px: float, py: float) -> bool:
        hit = False
        count = len(points)
        j = count - 1
        for i in range(count):
            xi, yi = points[i]
            xj, yj = points[j]
            if (yi > py) != (yj > py):
                if px < (xj - xi) * (py - yi) / (yj - yi) + xi:
                    hit = not hit
            j = i
        return hit

    return inside


def sdf_ring(cx: float, cy: float, rad: float, width: float):
    half = width / 2.0

    def f(px: float, py: float) -> float:
        return abs(hypot(px - cx, py - cy) - rad) - half

    return f


def sdf_intersect(*fns):
    def f(px: float, py: float) -> float:
        return max(fn(px, py) for fn in fns)

    return f


def sdf_half_plane_above(y: float):
    """y degerinin ustunde kalan bolge (kucuk y) icin negatif."""

    def f(_px: float, py: float) -> float:
        return py - y

    return f


def sdf_stroke(sdf, width: float):
    """Dolu bir sekli konturuna cevirir."""
    half = width / 2.0

    def f(px: float, py: float) -> float:
        return abs(sdf(px, py)) - half

    return f


# --------------------------------------------------------------------------- #
# Yuzey
# --------------------------------------------------------------------------- #

class Surface:
    """Basit RGBA tampon. Kucuk boyutlar icin tasarlandi (ikon/kose parcasi)."""

    __slots__ = ("w", "h", "buf")

    def __init__(self, w: int, h: int, bg: RGBA | None = None) -> None:
        self.w, self.h = int(w), int(h)
        if bg is None:
            self.buf = bytearray(self.w * self.h * 4)
        else:
            r, g, b, a = bg
            self.buf = bytearray(bytes((r, g, b, int(round(a * 255)))) * (self.w * self.h))

    def _blend(self, idx: int, r: int, g: int, b: int, sa: float) -> None:
        buf = self.buf
        da = buf[idx + 3] / 255.0
        out_a = sa + da * (1.0 - sa)
        if out_a <= 0.0:
            buf[idx] = buf[idx + 1] = buf[idx + 2] = buf[idx + 3] = 0
            return
        inv = da * (1.0 - sa)
        buf[idx] = int(round((r * sa + buf[idx] * inv) / out_a))
        buf[idx + 1] = int(round((g * sa + buf[idx + 1] * inv) / out_a))
        buf[idx + 2] = int(round((b * sa + buf[idx + 2] * inv) / out_a))
        buf[idx + 3] = int(round(out_a * 255))

    def fill(self, sdf, color: RGBA) -> "Surface":
        """SDF ile tanimli sekli, kenar yumusatarak boyar."""
        r, g, b, a = color
        w = self.w
        for y in range(self.h):
            py = y + 0.5
            base = y * w * 4
            for x in range(w):
                d = sdf(x + 0.5, py)
                if d >= 0.5:
                    continue
                cov = 1.0 if d <= -0.5 else (0.5 - d)
                sa = cov * a
                if sa > 0.0:
                    self._blend(base + x * 4, r, g, b, sa)
        return self

    def fill_mask(self, inside, color: RGBA, ss: int = 4) -> "Surface":
        """Analitik mesafesi olmayan sekiller icin ust ornekleme."""
        r, g, b, a = color
        w = self.w
        step = 1.0 / ss
        offs = [(i + 0.5) * step for i in range(ss)]
        total = float(ss * ss)
        for y in range(self.h):
            base = y * w * 4
            for x in range(w):
                hits = 0
                for oy in offs:
                    py = y + oy
                    for ox in offs:
                        if inside(x + ox, py):
                            hits += 1
                if not hits:
                    continue
                sa = (hits / total) * a
                self._blend(base + x * 4, r, g, b, sa)
        return self

    def png_bytes(self) -> bytes:
        stride = self.w * 4
        raw = bytearray()
        for y in range(self.h):
            raw.append(0)
            raw += self.buf[y * stride:(y + 1) * stride]

        def chunk(tag: bytes, data: bytes) -> bytes:
            return (struct.pack(">I", len(data)) + tag + data
                    + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

        return (b"\x89PNG\r\n\x1a\n"
                + chunk(b"IHDR", struct.pack(">IIBBBBB", self.w, self.h, 8, 6, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
                + chunk(b"IEND", b""))

    def png_b64(self) -> bytes:
        return base64.b64encode(self.png_bytes())

    def bmp_ico_entry(self) -> bytes:
        """ICO icin 32bpp alt-ust ters BMP (BITMAPINFOHEADER + XOR + AND)."""
        header = struct.pack("<IiiHHIIiiII", 40, self.w, self.h * 2, 1, 32, 0,
                             self.w * self.h * 4, 0, 0, 0, 0)
        xor = bytearray()
        stride = self.w * 4
        for y in range(self.h - 1, -1, -1):
            row = self.buf[y * stride:(y + 1) * stride]
            for x in range(0, stride, 4):
                xor += bytes((row[x + 2], row[x + 1], row[x], row[x + 3]))
        mask_stride = ((self.w + 31) // 32) * 4
        return bytes(header) + bytes(xor) + bytes(mask_stride * self.h)


def write_ico(path: str, surfaces: list[Surface]) -> None:
    entries = [s.bmp_ico_entry() for s in surfaces]
    offset = 6 + 16 * len(entries)
    head = struct.pack("<HHH", 0, 1, len(entries))
    dirs = b""
    for surf, data in zip(surfaces, entries):
        dim = 0 if surf.w >= 256 else surf.w
        dirs += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    with open(path, "wb") as fh:
        fh.write(head + dirs + b"".join(entries))
