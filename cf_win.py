# -*- coding: utf-8 -*-
"""Kurulum icin saf Win32 yardimcilari (ctypes).

Bu modul, kurulum isini harici kabuk sureci baslatmadan yapar. Nedeni
yalnizca hiz degil: kabuk uzerinden kisayol olusturmak veya gecikmeli silme
komutu birakmak, zararli yazilimlarda yaygin kaliplar oldugu icin virus
tarayicilarin sezgisel kurallarini tetikler. Ayni isler dogrudan Windows
API'siyle yapildiginda bu kaliplar ortadan kalkar.

Icerik
    known_folder()     SHGetKnownFolderPath ile Masaustu / Baslat menusu
    create_shortcut()  IShellLinkW + IPersistFile ile .lnk olusturma
    running_pids()     EnumProcesses ile ada gore surec arama
"""
from __future__ import annotations

import ctypes
import os
from ctypes import POINTER, byref, c_void_p, wintypes
from pathlib import Path

if os.name == "nt":
    _ole32 = ctypes.oledll.ole32
    _shell32 = ctypes.windll.shell32
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _psapi = ctypes.WinDLL("psapi", use_last_error=True)
else:  # pragma: no cover - yalnizca Windows
    _ole32 = _shell32 = _kernel32 = _psapi = None


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD), ("Data4", ctypes.c_byte * 8)]

    def __init__(self, text: str) -> None:
        super().__init__()
        _ole32.CLSIDFromString(text, byref(self))


# --------------------------------------------------------------------------- #
# Bilinen klasorler
# --------------------------------------------------------------------------- #
FOLDERID_Desktop = "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}"
FOLDERID_Programs = "{A77F5D77-2E2B-44C3-A6A2-ABA601054A51}"


def known_folder(folder_id: str) -> Path | None:
    """SHGetKnownFolderPath: OneDrive yonlendirmesini de dogru cozer."""
    if os.name != "nt":
        return None
    pointer = c_void_p()
    try:
        _shell32.SHGetKnownFolderPath(byref(GUID(folder_id)), 0, None, byref(pointer))
    except OSError:
        return None
    try:
        value = ctypes.wstring_at(pointer)
    finally:
        ctypes.windll.ole32.CoTaskMemFree(pointer)
    return Path(value) if value else None


# --------------------------------------------------------------------------- #
# Kisayol olusturma (IShellLinkW)
# --------------------------------------------------------------------------- #
CLSID_ShellLink = "{00021401-0000-0000-C000-000000000046}"
IID_IShellLinkW = "{000214F9-0000-0000-C000-000000000046}"
IID_IPersistFile = "{0000010B-0000-0000-C000-000000000046}"

CLSCTX_INPROC_SERVER = 1
COINIT_APARTMENTTHREADED = 0x2

# IShellLinkW arayuzundeki yontem siralari (IUnknown'in 3 yontemi sonrasi).
_SL_SET_DESCRIPTION = 7
_SL_SET_WORKING_DIR = 9
_SL_SET_ARGUMENTS = 11
_SL_SET_ICON_LOCATION = 17
_SL_SET_PATH = 20
# IPersistFile::Save
_PF_SAVE = 6
_IUNKNOWN_QUERY_INTERFACE = 0
_IUNKNOWN_RELEASE = 2


def _method(interface: c_void_p, index: int, argtypes: tuple, restype=ctypes.HRESULT):
    """COM sanal tablosundaki yontemi cagrilabilir hale getirir.

    Argüman tipleri acikca verilir; byref() nesnelerinden tip cikarilamaz.
    """
    vtable = ctypes.cast(interface, POINTER(POINTER(c_void_p))).contents
    prototype = ctypes.WINFUNCTYPE(restype, c_void_p, *argtypes)
    return prototype(vtable[index])


def _call(interface: c_void_p, index: int, argtypes: tuple, *args) -> int:
    return _method(interface, index, argtypes)(interface, *args)


def _release(interface: c_void_p) -> None:
    _method(interface, _IUNKNOWN_RELEASE, (), restype=ctypes.c_ulong)(interface)


def create_shortcut(link: Path, target: Path, *, description: str = "",
                    arguments: str = "", working_dir: Path | None = None,
                    icon: Path | None = None, icon_index: int = 0) -> bool:
    """Windows kabuk API'siyle .lnk olusturur. Basarili ise True doner."""
    if os.name != "nt":
        return False
    link.parent.mkdir(parents=True, exist_ok=True)

    try:
        _ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
    except OSError:
        pass  # zaten baslatilmis olabilir

    shell_link = c_void_p()
    try:
        _ole32.CoCreateInstance(byref(GUID(CLSID_ShellLink)), None, CLSCTX_INPROC_SERVER,
                                byref(GUID(IID_IShellLinkW)), byref(shell_link))
    except OSError:
        return False

    text = (ctypes.c_wchar_p,)
    try:
        _call(shell_link, _SL_SET_PATH, text, str(target))
        if working_dir:
            _call(shell_link, _SL_SET_WORKING_DIR, text, str(working_dir))
        if description:
            _call(shell_link, _SL_SET_DESCRIPTION, text, description)
        if arguments:
            _call(shell_link, _SL_SET_ARGUMENTS, text, arguments)
        if icon:
            _call(shell_link, _SL_SET_ICON_LOCATION, (ctypes.c_wchar_p, ctypes.c_int),
                  str(icon), icon_index)

        persist = c_void_p()
        _call(shell_link, _IUNKNOWN_QUERY_INTERFACE, (POINTER(GUID), POINTER(c_void_p)),
              byref(GUID(IID_IPersistFile)), byref(persist))
        try:
            _call(persist, _PF_SAVE, (ctypes.c_wchar_p, ctypes.c_int), str(link), 1)
        finally:
            _release(persist)
    except OSError:
        return False
    finally:
        _release(shell_link)

    return link.exists()


# --------------------------------------------------------------------------- #
# Surec arama
# --------------------------------------------------------------------------- #
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def running_pids(exe_name: str, exclude_pid: int | None = None) -> list[int]:
    """Verilen dosya adiyla calisan sureclerin kimlikleri."""
    if os.name != "nt":
        return []
    count = 1024
    while True:
        array = (wintypes.DWORD * count)()
        needed = wintypes.DWORD()
        if not _psapi.EnumProcesses(byref(array), ctypes.sizeof(array), byref(needed)):
            return []
        if needed.value < ctypes.sizeof(array):
            pids = array[:needed.value // ctypes.sizeof(wintypes.DWORD)]
            break
        count *= 2

    wanted = exe_name.lower()
    found: list[int] = []
    for pid in pids:
        if not pid or pid == exclude_pid:
            continue
        handle = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            continue
        try:
            size = wintypes.DWORD(260)
            buf = ctypes.create_unicode_buffer(size.value)
            if _kernel32.QueryFullProcessImageNameW(handle, 0, buf, byref(size)):
                if os.path.basename(buf.value).lower() == wanted:
                    found.append(pid)
        finally:
            _kernel32.CloseHandle(handle)
    return found
