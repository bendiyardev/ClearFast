# -*- mode: python ; coding: utf-8 -*-
"""ClearFast - tek klasorlu (onedir) derleme.

NEDEN ONEFILE DEGIL
    --onefile ile uretilen EXE, her calistirildiginda kendini %TEMP%\\_MEIxxxxx
    altina acip oradan calisir. Bu, paketleyici zararli yazilimlarin birebir
    davranisi oldugu icin bazi virus tarayicilar dosyayi statik olarak
    "Trojan/Generic" veya "Dropper" diye isaretler. Tek klasor dagitiminda
    boyle bir kendini-acma islemi yoktur.

NEDEN UPX KAPALI
    UPX ile sikistirma, paketleme heuristiklerini dogrudan tetikler ve
    yanlis pozitifleri artirir. Boyut kazanci bu maliyete degmez.

CIKTI
    dist/ClearFast/ClearFast.exe   uygulama
    dist/ClearFast/_internal/...   Python calisma zamani ve varliklar

    Kurulum ve kaldirma ayri bir ikili degildir; ayni EXE'nin kipleridir:
    ClearFast.exe --setup / --uninstall
"""

a = Analysis(
    ["ClearFast.py"],
    pathex=[],
    binaries=[],
    datas=[("assets/ClearFast.ico", "assets")],
    # Kurulum kipi yalnizca calisma aninda ice aktarilir; acikca bildiriyoruz.
    hiddenimports=["ClearFastSetup"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["unittest", "pydoc", "doctest", "email", "http", "xml", "pdb"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ClearFast",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/ClearFast.ico",
    version="installer/version_app.txt",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ClearFast",
)
