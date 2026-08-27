# -*- coding: utf-8 -*-
"""Canli performans ve donanim sagligi olcumleri.

Islemci ve surec kullanimi Windows API'sinden (ctypes) okunur; her saniye
PowerShell baslatmak pahali oldugu icin bu yol tercih edilmistir. Ekran karti,
bellek modulleri ve disk guvenilirlik sayaclari icin CIM/nvidia-smi kullanilir.
"""
from __future__ import annotations

import ctypes
import json
import os
import shutil
import subprocess
import time
from ctypes import wintypes

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

if os.name == "nt":
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _psapi = ctypes.WinDLL("psapi", use_last_error=True)
else:  # pragma: no cover - yalnizca Windows
    _kernel32 = _psapi = None


def _filetime_to_int(ft: wintypes.FILETIME) -> int:
    return (ft.dwHighDateTime << 32) | ft.dwLowDateTime


# --------------------------------------------------------------------------- #
# Islemci
# --------------------------------------------------------------------------- #

class CpuMonitor:
    """GetSystemTimes farklarindan sistem geneli islemci kullanimi."""

    def __init__(self) -> None:
        self._prev: tuple[int, int, int] | None = None
        self.cores = os.cpu_count() or 1

    def _read(self) -> tuple[int, int, int] | None:
        if os.name != "nt":
            return None
        idle, kernel, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
        if not _kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel),
                                        ctypes.byref(user)):
            return None
        return (_filetime_to_int(idle), _filetime_to_int(kernel), _filetime_to_int(user))

    def sample(self) -> float | None:
        """Iki cagri arasindaki kullanim yuzdesi. Ilk cagri None doner."""
        current = self._read()
        if current is None:
            return None
        previous, self._prev = self._prev, current
        if previous is None:
            return None
        idle_delta = current[0] - previous[0]
        # kernel zamani bosta gecen zamani da icerir.
        total_delta = (current[1] - previous[1]) + (current[2] - previous[2])
        if total_delta <= 0:
            return None
        return max(0.0, min(100.0, (1.0 - idle_delta / total_delta) * 100.0))


# --------------------------------------------------------------------------- #
# Surecler
# --------------------------------------------------------------------------- #

class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


class ProcessMonitor:
    """Surecleri isme gore gruplayip islemci/bellek kullanimini siralar."""

    def __init__(self) -> None:
        self._prev: dict[int, int] = {}
        self._stamp: float | None = None
        self.cores = os.cpu_count() or 1

    @staticmethod
    def _pids() -> list[int]:
        count = 1024
        while True:
            array = (wintypes.DWORD * count)()
            needed = wintypes.DWORD()
            if not _psapi.EnumProcesses(ctypes.byref(array), ctypes.sizeof(array),
                                        ctypes.byref(needed)):
                return []
            if needed.value < ctypes.sizeof(array):
                return [pid for pid in array[:needed.value // ctypes.sizeof(wintypes.DWORD)] if pid]
            count *= 2

    @staticmethod
    def _name(handle) -> str:
        size = wintypes.DWORD(260)
        buf = ctypes.create_unicode_buffer(size.value)
        if _kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value)
        return ""

    def sample(self) -> list[dict]:
        """[{name, count, cpu, ram}] - islemci yuzdesine gore azalan."""
        if os.name != "nt":
            return []
        now = time.monotonic()
        elapsed = (now - self._stamp) if self._stamp else 0.0
        self._stamp = now

        current: dict[int, int] = {}
        grouped: dict[str, dict] = {}

        for pid in self._pids():
            handle = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                continue
            try:
                creation, exit_t = wintypes.FILETIME(), wintypes.FILETIME()
                kernel, user = wintypes.FILETIME(), wintypes.FILETIME()
                if not _kernel32.GetProcessTimes(handle, ctypes.byref(creation),
                                                 ctypes.byref(exit_t), ctypes.byref(kernel),
                                                 ctypes.byref(user)):
                    continue
                busy = _filetime_to_int(kernel) + _filetime_to_int(user)
                current[pid] = busy

                counters = PROCESS_MEMORY_COUNTERS()
                counters.cb = ctypes.sizeof(counters)
                ram = 0
                if _psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                    ram = int(counters.WorkingSetSize)

                name = self._name(handle)
                if not name:
                    continue
            finally:
                _kernel32.CloseHandle(handle)

            cpu = 0.0
            previous = self._prev.get(pid)
            if previous is not None and elapsed > 0:
                # FILETIME birimi 100 ns'dir.
                cpu = ((busy - previous) / 1e7) / (elapsed * self.cores) * 100.0

            entry = grouped.setdefault(name, {"name": name, "count": 0, "cpu": 0.0, "ram": 0})
            entry["count"] += 1
            entry["cpu"] += max(0.0, cpu)
            entry["ram"] += ram

        self._prev = current
        rows = list(grouped.values())
        for row in rows:
            row["cpu"] = min(100.0, row["cpu"])
        rows.sort(key=lambda r: (-r["cpu"], -r["ram"]))
        return rows


# --------------------------------------------------------------------------- #
# PowerShell yardimcilari
# --------------------------------------------------------------------------- #

def run_ps(script: str, timeout: int = 12) -> str:
    if os.name != "nt":
        return ""
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=timeout,
            creationflags=CREATE_NO_WINDOW, encoding="utf-8", errors="replace")
        return result.stdout.strip()
    except Exception:
        return ""


def ps_json(script: str, timeout: int = 12) -> list[dict]:
    raw = run_ps(script, timeout)
    if not raw:
        return []
    try:
        obj = json.loads(raw)
    except ValueError:
        return []
    if isinstance(obj, dict):
        return [obj]
    return [item for item in obj if isinstance(item, dict)]


# --------------------------------------------------------------------------- #
# Ekran karti
# --------------------------------------------------------------------------- #

_NVIDIA_SMI: str | None | bool = False  # False = henuz aranmadi


def nvidia_smi_path() -> str | None:
    global _NVIDIA_SMI
    if _NVIDIA_SMI is not False:
        return _NVIDIA_SMI  # type: ignore[return-value]
    found = shutil.which("nvidia-smi")
    if not found:
        candidate = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                                 "NVIDIA Corporation", "NVSMI", "nvidia-smi.exe")
        found = candidate if os.path.exists(candidate) else None
    _NVIDIA_SMI = found
    return found


NVIDIA_FIELDS = ("name", "driver_version", "utilization.gpu", "utilization.memory",
                 "memory.used", "memory.total", "temperature.gpu", "fan.speed", "power.draw")


def gpu_status() -> list[dict]:
    """nvidia-smi varsa canli GPU olcumleri; yoksa bos liste."""
    exe = nvidia_smi_path()
    if not exe:
        return []
    try:
        result = subprocess.run(
            [exe, "--query-gpu=" + ",".join(NVIDIA_FIELDS),
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=6,
            creationflags=CREATE_NO_WINDOW, encoding="utf-8", errors="replace")
    except Exception:
        return []
    rows = []
    for line in result.stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != len(NVIDIA_FIELDS):
            continue

        def number(value: str) -> float | None:
            try:
                return float(value)
            except ValueError:
                return None

        rows.append({
            "name": parts[0],
            "driver": parts[1],
            "load": number(parts[2]),
            "memory_load": number(parts[3]),
            "memory_used": number(parts[4]),
            "memory_total": number(parts[5]),
            "temperature": number(parts[6]),
            "fan": number(parts[7]),
            "power": number(parts[8]),
        })
    return rows


# --------------------------------------------------------------------------- #
# Bellek modulleri, disk guvenilirligi, tam kunye
# --------------------------------------------------------------------------- #

FORM_FACTORS = {8: "DIMM", 12: "SODIMM", 0: "Bilinmiyor"}
MEMORY_TYPES = {20: "DDR", 21: "DDR2", 24: "DDR3", 26: "DDR4", 34: "DDR5", 0: ""}


def memory_modules() -> list[dict]:
    rows = ps_json(
        "Get-CimInstance Win32_PhysicalMemory | Select-Object BankLabel,DeviceLocator,"
        "Capacity,Speed,ConfiguredClockSpeed,Manufacturer,PartNumber,FormFactor,SMBIOSMemoryType"
        " | ConvertTo-Json -Compress")
    out = []
    for item in rows:
        out.append({
            "slot": (item.get("DeviceLocator") or item.get("BankLabel") or "Yuva"),
            "bank": item.get("BankLabel") or "",
            "capacity": int(item.get("Capacity") or 0),
            "speed": int(item.get("Speed") or 0),
            "configured": int(item.get("ConfiguredClockSpeed") or 0),
            "vendor": (item.get("Manufacturer") or "").strip(),
            "part": (item.get("PartNumber") or "").strip(),
            "form": FORM_FACTORS.get(int(item.get("FormFactor") or 0), ""),
            "type": MEMORY_TYPES.get(int(item.get("SMBIOSMemoryType") or 0), ""),
        })
    return out


def storage_reliability() -> tuple[list[dict], str | None]:
    """Disk asinma/sicaklik sayaclari. Yonetici degilse (rows, hata) doner."""
    script = ("Get-PhysicalDisk | ForEach-Object { $d = $_; "
              "$c = $d | Get-StorageReliabilityCounter -ErrorAction SilentlyContinue; "
              "if ($c) { [pscustomobject]@{ Name = $d.FriendlyName; "
              "Temperature = $c.Temperature; Wear = $c.Wear; PowerOnHours = $c.PowerOnHours; "
              "ReadErrors = $c.ReadErrorsTotal; WriteErrors = $c.WriteErrorsTotal; "
              "StartStop = $c.StartStopCycleCount } } } | ConvertTo-Json -Compress")
    rows = ps_json(script, timeout=20)
    if not rows:
        return [], "Bu sayaçlar yönetici yetkisi gerektirir."
    out = []
    for item in rows:
        out.append({
            "name": item.get("Name") or "Disk",
            "temperature": item.get("Temperature"),
            "wear": item.get("Wear"),
            "hours": item.get("PowerOnHours"),
            "read_errors": item.get("ReadErrors"),
            "write_errors": item.get("WriteErrors"),
        })
    return out, None


SPEC_SCRIPT = r"""
$os = Get-CimInstance Win32_OperatingSystem
$cs = Get-CimInstance Win32_ComputerSystem
$bb = Get-CimInstance Win32_BaseBoard
$bi = Get-CimInstance Win32_BIOS
$cp = Get-CimInstance Win32_Processor | Select-Object -First 1
[pscustomobject]@{
  os_caption   = $os.Caption
  os_version   = $os.Version
  os_build     = $os.BuildNumber
  os_arch      = $os.OSArchitecture
  os_install   = $(if ($os.InstallDate) { $os.InstallDate.ToString('dd.MM.yyyy') } else { '' })
  boot_time    = $(if ($os.LastBootUpTime) { $os.LastBootUpTime.ToString('dd.MM.yyyy HH:mm') } else { '' })
  uptime_hours = $(if ($os.LastBootUpTime) { [math]::Round(((Get-Date) - $os.LastBootUpTime).TotalHours, 1) } else { 0 })
  model        = "$($cs.Manufacturer) $($cs.Model)".Trim()
  system_type  = $cs.SystemType
  board        = "$($bb.Manufacturer) $($bb.Product)".Trim()
  bios         = "$($bi.Manufacturer) $($bi.SMBIOSBIOSVersion)".Trim()
  bios_date    = $(if ($bi.ReleaseDate) { $bi.ReleaseDate.ToString('dd.MM.yyyy') } else { '' })
  cpu_name     = $cp.Name
  cpu_cores    = $cp.NumberOfCores
  cpu_threads  = $cp.NumberOfLogicalProcessors
  cpu_mhz      = $cp.MaxClockSpeed
  cpu_socket   = $cp.SocketDesignation
} | ConvertTo-Json -Compress
"""


def full_specs() -> dict:
    rows = ps_json(SPEC_SCRIPT, timeout=20)
    return rows[0] if rows else {}
