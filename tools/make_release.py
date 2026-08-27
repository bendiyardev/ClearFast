# -*- coding: utf-8 -*-
"""Dagitima hazir ZIP paketini olusturur.

Icerik, dist/ClearFast klasorunun tamamidir. Paket tek dosyaya (--onefile)
gomulmez; boylece calisma aninda kendini %TEMP% altina acan bir ikili
olusmaz ve virus tarayicilarin yanlis pozitifleri buyuk olcude ortadan
kalkar. Ayrintili aciklama icin docs/ANTIVIRUS.md dosyasina bakin.

Kullanim:  py -3 tools/make_release.py [hedef_klasor]
           Hedef verilmezse masaustune yazar.
"""
from __future__ import annotations

import hashlib
import os
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cf_core import APP_NAME, APP_VERSION  # noqa: E402
from cf_ui import CONTACT_LINKS  # noqa: E402

BUILD_DIR = ROOT / "dist" / APP_NAME
README = ROOT / "README.txt"
SETUP_BAT = ROOT / "Kurulum.bat"
ANTIVIRUS = ROOT / "docs" / "ANTIVIRUS.md"

QUICK_START = """\
{app} {version} — Hızlı başlangıç
===================================

BU KLASÖRÜ TAMAMEN ÇIKARIN
  ZIP'in içinden yalnızca ClearFast.exe'yi çıkarmayın; program çalışmak için
  yanındaki _internal klasörüne ihtiyaç duyar. Klasörün tamamını çıkarın.

KURMADAN ÇALIŞTIRMAK İÇİN
  ClearFast.exe dosyasına çift tıklayın. Hiçbir şey kurmaz, kayıt defterine
  yazmaz; USB bellekten de çalışır.

BU BİLGİSAYARA KURMAK İÇİN
  Kurulum.bat dosyasına çift tıklayın.
  (Aynısı: ClearFast.exe --setup)
  Yönetici yetkisi istemez. Başlat menüsü ve masaüstü kısayolu oluşturur,
  Windows "Uygulamalar" listesine kaydeder.

KALDIRMAK İÇİN
  Ayarlar › Uygulamalar › ClearFast › Kaldır
  veya kurulum klasöründe:  ClearFast.exe --uninstall

WINDOWS UYARISI ÇIKARSA
  Dosyalar dijital sertifika ile imzalı olmadığı için SmartScreen
  "Bilinmeyen yayımcı" uyarısı gösterebilir.
  "Ek bilgi" › "Yine de çalıştır" ile devam edebilirsiniz.
  Virüs tarayıcı uyarıları hakkında: ANTIVIRUS.md

İLK AÇILIŞTA NE OLUR
  Uygulama sistem bilgilerini okur ve temizlenebilir klasörleri tarar.
  Hiçbir şey otomatik silinmez; her silme işlemi için onayınız istenir.

Ayrıntılar için README.txt dosyasına bakın.

İLETİŞİM
{contact}
Bu bağlantılar uygulamanın sol menüsünde ve kurulum ekranında da gömülüdür.
"""


def windows_text(text: str) -> bytes:
    """CRLF satir sonu + UTF-8 BOM: Not Defteri Turkce karakterleri dogru gosterir."""
    return "\r\n".join(text.splitlines()).encode("utf-8-sig")


def human(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}".replace(".", ",")
        value /= 1024
    return f"{size} B"


def main() -> None:
    if not (BUILD_DIR / f"{APP_NAME}.exe").exists():
        print(f"Derlenmis klasor bulunamadi: {BUILD_DIR}")
        print("Once Build.bat calistirin.")
        raise SystemExit(1)

    if len(sys.argv) > 1:
        out_dir = Path(sys.argv[1])
    else:
        out_dir = Path(os.environ.get("USERPROFILE", Path.home())) / "Desktop"
        if not out_dir.is_dir():
            out_dir = Path.home()
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{APP_NAME}-{APP_VERSION}-Windows.zip"

    contact = "\n".join(f"  {service:10} {handle:14} {url}"
                        for _glyph, service, handle, url in CONTACT_LINKS)
    files = 0

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.writestr(f"{APP_NAME}/KURULUM.txt",
                    windows_text(QUICK_START.format(app=APP_NAME, version=APP_VERSION,
                                                    contact=contact)))
        for source, name in ((README, "README.txt"), (ANTIVIRUS, "ANTIVIRUS.md")):
            if source.exists():
                zf.writestr(f"{APP_NAME}/{name}",
                            windows_text(source.read_text(encoding="utf-8")))
        if SETUP_BAT.exists():
            zf.write(SETUP_BAT, f"{APP_NAME}/Kurulum.bat")

        for item in sorted(BUILD_DIR.rglob("*")):
            if item.is_file():
                zf.write(item, f"{APP_NAME}/{item.relative_to(BUILD_DIR)}")
                files += 1

    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    print(f"Hazir: {out}")
    print(f"Boyut: {human(out.stat().st_size)}  ({files} dosya)")
    print(f"SHA-256: {digest}")

    sums = out_dir / "SHA256SUMS.txt"
    sums.write_text(
        "\r\n".join([
            f"# {APP_NAME} {APP_VERSION} - SHA-256",
            "#",
            "# Dogrulama / Verify (PowerShell):",
            f"#   Get-FileHash .\\{out.name} -Algorithm SHA256",
            "#",
            f"{digest}  {out.name}",
        ]) + "\r\n", encoding="utf-8")
    print(f"Sağlama: {sums}")


if __name__ == "__main__":
    main()
