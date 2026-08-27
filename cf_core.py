# -*- coding: utf-8 -*-
"""ClearFast cekirdek mantigi: hedefler, tarama, silme ve sistem bilgisi.

Arayuzden bagimsizdir; tum kullanici metinleri arayuz katmanina birakilmaz,
cunku hedef aciklamalari verinin bir parcasidir.
"""
from __future__ import annotations

import ctypes
import json
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

APP_NAME = "ClearFast"
APP_VERSION = "0.3.2"
APP_PUBLISHER = "ClearFast"

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

# Hedef kartlarinin gruplandigi sira
CATEGORY_ORDER = ("Windows", "Ekran kartı", "Tarayıcı", "Yapay zekâ", "Geliştirme",
                  "Paket önbelleği")


@dataclass(frozen=True)
class CleanupTarget:
    key: str
    title: str
    category: str
    path_factory: Callable[[], Iterable[Path]]
    description: str
    default_selected: bool = True
    risk: str = "Güvenli"
    requires_admin: bool = False


@dataclass(frozen=True)
class ScanRow:
    """Taramada bulunan tek bir klasor."""
    uid: str
    target: CleanupTarget
    path: Path
    size: int


# --------------------------------------------------------------------------- #
# Yol yardimcilari
# --------------------------------------------------------------------------- #

def env_path(name: str, *parts: str) -> Path:
    base = os.environ.get(name)
    if not base:
        # Eksik bir ortam degiskeninde asla calisma klasorune dusme.
        return Path(r"C:\__CLEARFAST_ENV_MISSING_8F31D9E2__", *parts)
    return Path(base, *parts)


def existing_paths(paths: Iterable[Path]) -> list[Path]:
    """Var olan, tekrarsiz yollari sirasini koruyarak dondurur."""
    out: list[Path] = []
    seen: set[str] = set()
    for p in paths:
        try:
            if not p:
                continue
            p = p.expanduser()
            key = str(p.resolve(strict=False)).lower()
            if key not in seen and p.exists():
                seen.add(key)
                out.append(p)
        except OSError:
            continue
    return out


def browser_cache_dirs(user_data: Path) -> list[Path]:
    """Chromium profillerinde yalnizca onbellek klasorleri; profil verisi asla."""
    found: list[Path] = []
    if not user_data.exists():
        return found
    try:
        for child in user_data.iterdir():
            if not child.is_dir():
                continue
            if child.name in ("Default", "Guest Profile") or child.name.startswith("Profile "):
                for cache_name in ("Cache", "Code Cache", "GPUCache"):
                    candidate = child / cache_name
                    if candidate.exists():
                        found.append(candidate)
    except OSError:
        pass
    return existing_paths(found)


# Chromium/Electron tabanli uygulamalarin yeniden olusturulabilir klasor adlari.
# Yalnizca bu adlar eslesir; uygulama kokunun kendisi hicbir zaman hedeflenmez.
CHROMIUM_CACHE_NAMES = frozenset({
    "cache", "code cache", "gpucache", "dawncache", "dawngraphitecache",
    "dawnwebgpucache", "shadercache", "component_crx_cache", "crashpad",
    "logs", "cacheddata", "blob_storage",
})


# Paket yoneticisi onbellekleri ayri (opsiyonel) hedeflerde ele alinir; genel
# tarayici bunlari toplamasin ki kullanici farkinda olmadan yeniden indirmesin.
PACKAGE_DIR_NAMES = frozenset({"pip", "npm", "yarn", "pnpm", "uv", "site-packages"})


def chromium_caches(roots: Iterable[Path], max_depth: int = 5) -> list[Path]:
    """Verilen koklerin altinda yalnizca adi guvenli listede olan klasorleri bulur.

    Eslesen bir klasorun icine inilmez; boylece "Cache/Cache_Data" gibi ic ice
    kayitlar bir kez sayilir.
    """
    found: list[Path] = []
    for root in roots:
        try:
            if not root or not root.is_dir():
                continue
        except OSError:
            continue
        base_depth = len(root.parts)
        for dirpath, dirnames, _files in os.walk(root):
            if len(Path(dirpath).parts) - base_depth >= max_depth:
                dirnames[:] = []
                continue
            parts = {part.lower() for part in Path(dirpath).parts[base_depth:]}
            if parts & PACKAGE_DIR_NAMES:
                continue
            for name in list(dirnames):
                if name.lower() in CHROMIUM_CACHE_NAMES:
                    found.append(Path(dirpath) / name)
                    dirnames.remove(name)  # icine inme
    return existing_paths(found)


def package_roots(pattern: str) -> list[Path]:
    """LOCALAPPDATA/Packages altindaki MSIX uygulama klasorleri."""
    base = env_path("LOCALAPPDATA", "Packages")
    if not base.exists():
        return []
    try:
        return [p for p in base.glob(pattern) if p.is_dir()]
    except OSError:
        return []


def firefox_cache_dirs() -> list[Path]:
    base = env_path("LOCALAPPDATA", "Mozilla", "Firefox", "Profiles")
    if not base.exists():
        return []
    try:
        return existing_paths(base.glob("*/cache2"))
    except OSError:
        return []


# --------------------------------------------------------------------------- #
# Temizlik hedefleri
# --------------------------------------------------------------------------- #

def targets() -> list[CleanupTarget]:
    local = env_path("LOCALAPPDATA")
    roaming = env_path("APPDATA")
    user = Path.home()

    return [
        CleanupTarget(
            "user_temp", "Kullanıcı geçici dosyaları", "Windows",
            lambda: existing_paths([env_path("TEMP"), local / "Temp"]),
            "Kurulumların ve uygulamaların bıraktığı geçici dosyalar. "
            "Açık uygulamaların kilitlediği dosyalar atlanır.",
        ),
        CleanupTarget(
            "win_temp", "Windows Temp", "Windows",
            lambda: existing_paths([env_path("WINDIR", "Temp")]),
            "Windows ve servislerin geçici dosyaları. Bir kısmı için yönetici yetkisi gerekir.",
            requires_admin=True,
        ),
        CleanupTarget(
            "crash", "Çökme dökümleri", "Windows",
            lambda: existing_paths([local / "CrashDumps"]),
            "Çöken uygulamaların hata analizi için bıraktığı .dmp dosyaları.",
        ),
        CleanupTarget(
            "d3d", "DirectX shader önbelleği", "Ekran kartı",
            lambda: existing_paths([local / "D3DSCache"]),
            "Oyun ve uygulamalar tarafından kullanım sırasında yeniden oluşturulur.",
        ),
        CleanupTarget(
            "nvidia_dx", "NVIDIA DirectX önbelleği", "Ekran kartı",
            lambda: existing_paths([local / "NVIDIA" / "DXCache"]),
            "NVIDIA sürücüsünün derlenmiş shader önbelleği. Yeniden oluşturulabilir.",
        ),
        CleanupTarget(
            "nvidia_gl", "NVIDIA OpenGL önbelleği", "Ekran kartı",
            lambda: existing_paths([local / "NVIDIA" / "GLCache"]),
            "NVIDIA OpenGL shader önbelleği. Yeniden oluşturulabilir.",
        ),
        CleanupTarget(
            "cuda_jit", "NVIDIA CUDA JIT önbelleği", "Ekran kartı",
            lambda: existing_paths([roaming / "NVIDIA" / "ComputeCache"]),
            "CUDA çekirdeklerinin anında derlenmiş kopyaları. Yapay zekâ ve hesaplama "
            "yükleri çalışırken yeniden oluşturulur.",
        ),
        CleanupTarget(
            "chrome", "Chrome önbelleği", "Tarayıcı",
            lambda: browser_cache_dirs(local / "Google" / "Chrome" / "User Data"),
            "Yalnızca web, kod ve GPU önbelleği. Şifreler, yer imleri ve profil verisi hedeflenmez.",
        ),
        CleanupTarget(
            "edge", "Edge önbelleği", "Tarayıcı",
            lambda: browser_cache_dirs(local / "Microsoft" / "Edge" / "User Data"),
            "Yalnızca web, kod ve GPU önbelleği. Profil verisi hedeflenmez.",
        ),
        CleanupTarget(
            "brave", "Brave önbelleği", "Tarayıcı",
            lambda: browser_cache_dirs(local / "BraveSoftware" / "Brave-Browser" / "User Data"),
            "Yalnızca web, kod ve GPU önbelleği. Profil verisi hedeflenmez.",
        ),
        CleanupTarget(
            "firefox", "Firefox önbelleği", "Tarayıcı",
            firefox_cache_dirs,
            "Firefox profillerindeki cache2 önbelleği. Yer imleri ve şifreler hedeflenmez.",
        ),
        CleanupTarget(
            "vscode", "VS Code önbelleği", "Geliştirme",
            lambda: existing_paths([
                roaming / "Code" / "Cache",
                roaming / "Code" / "CachedData",
                roaming / "Code" / "Code Cache",
                roaming / "Code" / "GPUCache",
                roaming / "Code" / "logs",
            ]),
            "Editör önbelleği ve günlükleri. Projeler, ayarlar ve eklentiler hedeflenmez.",
        ),
        CleanupTarget(
            "cursor", "Cursor önbelleği", "Yapay zekâ",
            lambda: chromium_caches([roaming / "Cursor", local / "Cursor"]),
            "Cursor'ın önbellek, gömülü tarayıcı ve çökme günlüğü klasörleri. "
            "Workspace, sohbet geçmişi ve kullanıcı ayarları hedeflenmez.",
        ),
        CleanupTarget(
            "claude", "Claude Desktop önbelleği", "Yapay zekâ",
            lambda: chromium_caches([roaming / "Claude", local / "Claude", local / "Claude-3p"]
                                    + package_roots("Claude_*")),
            "Claude Desktop'ın önbellek ve günlük klasörleri. Sohbet geçmişi ve oturum "
            "bilgisi hedeflenmez.",
        ),
        CleanupTarget(
            "claude_code", "Claude Code önbelleği", "Yapay zekâ",
            lambda: existing_paths([local / "claude-cli-nodejs" / "Cache",
                                    user / ".claude" / "cache"])
            + chromium_caches([roaming / "Claude Code"]),
            "Claude Code komut satırı aracının indirme önbelleği. Projeleriniz, sohbet "
            "geçmişiniz ve ayarlarınız hedeflenmez.",
        ),
        CleanupTarget(
            "codex", "OpenAI Codex önbelleği", "Yapay zekâ",
            lambda: chromium_caches(package_roots("OpenAI.Codex_*") + [roaming / "Codex"]),
            "Codex uygulamasının web, GPU ve günlük önbelleği. Oturum ve ayarlar hedeflenmez.",
        ),
        CleanupTarget(
            "antigravity", "Antigravity / Gemini önbelleği", "Yapay zekâ",
            lambda: chromium_caches([user / ".gemini" / "antigravity-browser-profile",
                                     roaming / "Antigravity", local / "Antigravity"]),
            "Gemini Antigravity'nin gömülü tarayıcı önbelleği. Oturum, ayar ve proje "
            "verisi hedeflenmez.",
        ),
        CleanupTarget(
            "trae", "Trae önbelleği", "Yapay zekâ",
            lambda: chromium_caches([roaming / "TRAE SOLO", roaming / "Trae", local / "Trae"]),
            "Trae editörünün önbellek, derlenmiş veri ve günlük klasörleri.",
        ),
        CleanupTarget(
            "windsurf", "Windsurf / Codeium önbelleği", "Yapay zekâ",
            lambda: chromium_caches([roaming / "Windsurf", local / "Windsurf",
                                     user / ".codeium"]),
            "Windsurf ve Codeium dil sunucusunun önbellek ve günlükleri.",
        ),
        CleanupTarget(
            "lmstudio", "LM Studio önbelleği", "Yapay zekâ",
            lambda: chromium_caches([roaming / "LM Studio", local / "LM-Studio"]),
            "LM Studio arayüz önbelleği. İndirdiğiniz modeller hedeflenmez.",
        ),
        CleanupTarget(
            "ai_logs", "Yapay zekâ araçlarının günlükleri", "Yapay zekâ",
            lambda: chromium_caches([user / ".copilot", user / ".cline", user / ".continue",
                                     user / ".aider", local / "warp", local / "Ollama",
                                     local / "github-copilot-sdk"]),
            "Copilot, Cline, Continue, Warp ve Ollama gibi araçların günlük ve önbellek "
            "klasörleri. Yapılandırma dosyaları ve modeller hedeflenmez.",
        ),
        CleanupTarget(
            "ai_compile", "Model derleme önbellekleri", "Yapay zekâ",
            lambda: existing_paths([local / "torch_extensions", user / ".triton" / "cache",
                                    user / ".cache" / "torch_extensions",
                                    local / "Temp" / "gradio"]),
            "PyTorch ve Triton'un derlenmiş çekirdek önbelleği. İlk çalıştırmada yeniden "
            "derlenir; modeller ve ağırlıklar hedeflenmez.",
        ),
        CleanupTarget(
            "plugin_cache", "Eklenti indirme önbelleği", "Yapay zekâ",
            lambda: existing_paths([user / ".claude" / "plugins" / "cache",
                                    user / ".cursor" / "plugins" / "cache"]),
            "Claude Code ve Cursor eklentilerinin indirilmiş kopyaları. Silinirse "
            "eklentiler ilk kullanımda yeniden indirilir.",
            default_selected=False,
            risk="Opsiyonel",
        ),
        CleanupTarget(
            "pip", "pip paket önbelleği", "Paket önbelleği",
            lambda: existing_paths([local / "pip" / "Cache", user / ".cache" / "pip"]
                                   + [pkg / "LocalCache" / "Local" / "pip" / "cache"
                                      for pkg in package_roots("*")]),
            "İndirilmiş Python paketleri. Silinirse paketler gerektiğinde yeniden indirilir.",
            default_selected=False,
            risk="Opsiyonel",
        ),
        CleanupTarget(
            "npm", "npm paket önbelleği", "Paket önbelleği",
            lambda: existing_paths([local / "npm-cache" / "_cacache", user / ".npm" / "_cacache"]),
            "npm indirme önbelleği. node_modules ve projeler silinmez; paketler yeniden indirilir.",
            default_selected=False,
            risk="Opsiyonel",
        ),
        CleanupTarget(
            "uv", "uv paket önbelleği", "Paket önbelleği",
            lambda: existing_paths([local / "uv" / "cache", user / ".cache" / "uv"]),
            "uv'nin indirme ve derleme önbelleği. Sanal ortamlar hedeflenmez.",
            default_selected=False,
            risk="Opsiyonel",
        ),
        CleanupTarget(
            "pnpm", "pnpm deposu", "Paket önbelleği",
            lambda: existing_paths([local / "pnpm-cache", user / ".pnpm-store"]),
            "pnpm içerik adresli deposu. Silinirse bağımlılıklar yeniden indirilir.",
            default_selected=False,
            risk="Opsiyonel",
        ),
        CleanupTarget(
            "yarn", "Yarn önbelleği", "Paket önbelleği",
            lambda: existing_paths([local / "Yarn" / "Cache", local / "Yarn" / "Berry" / "cache"]),
            "Yarn indirme önbelleği. Paketler gerektiğinde yeniden indirilir.",
            default_selected=False,
            risk="Opsiyonel",
        ),
    ]


# Bilerek otomatik temizlige alinmayan buyuk veri depolari.
WATCH_PATHS: list[tuple[str, Callable[[], Path], str]] = [
    ("Hugging Face model deposu", lambda: Path.home() / ".cache" / "huggingface" / "hub",
     "Çöp değildir. Silinirse modellerin tamamı yeniden indirilir."),
    ("Ollama modelleri", lambda: Path.home() / ".ollama" / "models",
     "Çöp değildir. Silinirse yerel modelleriniz kaybolur."),
    ("LM Studio modelleri", lambda: Path.home() / ".lmstudio" / "models",
     "İndirilmiş dil modelleri. Yeniden indirilmesi saatler sürebilir."),
    ("PyTorch model önbelleği", lambda: Path.home() / ".cache" / "torch",
     "Önceden eğitilmiş ağırlıklar. Silinirse tekrar indirilir."),
    ("Claude Code verisi", lambda: Path.home() / ".claude",
     "Projeler, sohbet geçmişi ve ayarlar burada tutulur; asla temizlenmez."),
    ("Gemini / Antigravity verisi", lambda: Path.home() / ".gemini",
     "Oturum ve proje verisi. Yalnızca içindeki tarayıcı önbelleği temizlenebilir."),
    ("OpenAI Codex verisi", lambda: env_path("LOCALAPPDATA", "OpenAI"),
     "Codex uygulama dosyaları ve oturum verisi; otomatik temizlenmez."),
    ("VS Code eklentileri", lambda: Path.home() / ".vscode" / "extensions",
     "Kurulu eklentileri tutar; otomatik temizlenmez."),
    ("Cursor kullanıcı verisi", lambda: env_path("APPDATA", "Cursor", "User"),
     "Ayarlar ve workspace verisi içerir; otomatik temizlenmez."),
]


# --------------------------------------------------------------------------- #
# Bicimlendirme
# --------------------------------------------------------------------------- #

def human_bytes(value: int) -> str:
    """Turkce ondalik ayraci ile boyut metni."""
    size = float(max(0, value))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            text = f"{size:.0f}" if unit in ("B", "KB") else f"{size:.2f}".replace(".", ",")
            return f"{text} {unit}"
        size /= 1024
    return f"{value} B"


# --------------------------------------------------------------------------- #
# Dosya sistemi islemleri
# --------------------------------------------------------------------------- #

def dir_size(path: Path) -> int:
    total = 0
    try:
        if path.is_file() or path.is_symlink():
            return path.stat().st_size
    except OSError:
        return 0

    stack = [path]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if entry.is_symlink():
                            total += entry.stat(follow_symlinks=False).st_size
                        elif entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                        else:
                            total += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
        except OSError:
            continue
    return total


def delete_contents(path: Path) -> tuple[int, int, list[str]]:
    """Klasorun icerigini siler, klasorun kendisini birakir.

    Doner: (silinen oge sayisi, kazanilan bayt, hata metinleri)
    """
    deleted = 0
    reclaimed = 0
    errors: list[str] = []
    if not path.exists():
        return deleted, reclaimed, errors

    try:
        children = list(path.iterdir()) if path.is_dir() else [path]
    except OSError as exc:
        return 0, 0, [f"{path}: {exc}"]

    for child in children:
        try:
            size = dir_size(child)
            if child.is_symlink() or child.is_file():
                child.unlink(missing_ok=True)
            elif child.is_dir():
                shutil.rmtree(child, ignore_errors=False)
            deleted += 1
            reclaimed += size
        except OSError as exc:
            # Kilitli dosya veya erisim reddi: atla, devam et.
            errors.append(f"{child}: {exc}")
    return deleted, reclaimed, errors


def scan_targets(defs: list[CleanupTarget]) -> list[ScanRow]:
    """Tum hedefleri tarayip bulunan klasorleri boyutlariyla dondurur."""
    rows: list[ScanRow] = []
    for target in defs:
        try:
            paths = list(target.path_factory())
        except OSError:
            continue
        for index, path in enumerate(paths):
            rows.append(ScanRow(f"{target.key}:{index}", target, path, dir_size(path)))
    return rows


def common_root(paths: list[Path]) -> str:
    """Birden cok klasorun ortak ust dizini; liste ozetlerinde kullanilir."""
    if not paths:
        return ""
    if len(paths) == 1:
        return str(paths[0])
    try:
        return os.path.commonpath([str(p) for p in paths])
    except ValueError:
        return str(paths[0].parent)


@dataclass(frozen=True)
class ScanGroup:
    """Ayni hedefe ait tum klasorlerin ozeti; listede tek satir olarak gorunur."""
    target: CleanupTarget
    rows: list[ScanRow]

    @property
    def key(self) -> str:
        return self.target.key

    @property
    def size(self) -> int:
        return sum(row.size for row in self.rows)

    @property
    def paths(self) -> list[Path]:
        return [row.path for row in self.rows]

    @property
    def location(self) -> str:
        return common_root(self.paths)


def group_rows(rows: list[ScanRow]) -> list[ScanGroup]:
    """Tarama sonucunu hedef bazinda toplar; kategori ve boyuta gore siralar."""
    buckets: dict[str, list[ScanRow]] = {}
    order: list[str] = []
    for row in rows:
        if row.target.key not in buckets:
            buckets[row.target.key] = []
            order.append(row.target.key)
        buckets[row.target.key].append(row)
    groups = [ScanGroup(buckets[key][0].target, buckets[key]) for key in order]
    rank = {name: i for i, name in enumerate(CATEGORY_ORDER)}
    groups.sort(key=lambda g: (rank.get(g.target.category, 99), -g.size, g.target.title))
    return groups


def scan_watch() -> list[tuple[str, Path, int, str]]:
    rows = []
    for title, factory, note in WATCH_PATHS:
        try:
            path = factory()
            if path and path.exists():
                rows.append((title, path, dir_size(path), note))
        except OSError:
            continue
    return rows


def reveal(path: Path) -> None:
    """Klasoru Gezgin'de acar."""
    try:
        os.startfile(str(path))  # noqa: S606 - Windows'a ozgu, kullanicinin istegiyle
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# Sistem bilgisi
# --------------------------------------------------------------------------- #

def is_admin() -> bool:
    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def run_ps(script: str, timeout: int = 10) -> str:
    if os.name != "nt":
        return ""
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=timeout,
            creationflags=CREATE_NO_WINDOW, encoding="utf-8", errors="replace",
        )
        return result.stdout.strip()
    except Exception:
        return ""


def memory_info() -> tuple[int, int]:
    """(toplam, kullanilabilir) fiziksel bellek."""
    if os.name != "nt":
        return 0, 0

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MEMORYSTATUSEX()
    status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return int(status.ullTotalPhys), int(status.ullAvailPhys)
    return 0, 0


def _ps_json(script: str) -> list[dict]:
    raw = run_ps(script)
    if not raw:
        return []
    try:
        obj = json.loads(raw)
    except ValueError:
        return []
    if isinstance(obj, dict):
        return [obj]
    return [item for item in obj if isinstance(item, dict)]


def system_snapshot() -> dict:
    total_ram, avail_ram = memory_info()
    cpu = (run_ps("(Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name)")
           or os.environ.get("PROCESSOR_IDENTIFIER", "Bilinmiyor"))
    os_caption = run_ps("(Get-CimInstance Win32_OperatingSystem | Select-Object -ExpandProperty Caption)")

    gpus = []
    for item in _ps_json("Get-CimInstance Win32_VideoController "
                         "| Select-Object Name,AdapterRAM,DriverVersion | ConvertTo-Json -Compress"):
        gpus.append({
            "name": item.get("Name") or "Bilinmeyen ekran kartı",
            "ram": int(item.get("AdapterRAM") or 0),
            "driver": item.get("DriverVersion") or "",
        })

    disks = []
    for item in _ps_json("Get-PhysicalDisk | Select-Object FriendlyName,MediaType,HealthStatus,"
                         "OperationalStatus,Size | ConvertTo-Json -Compress"):
        disks.append({
            "name": item.get("FriendlyName") or "Disk",
            "media": item.get("MediaType") or "Belirtilmemiş",
            "health": item.get("HealthStatus") or "Bilinmiyor",
            "operational": item.get("OperationalStatus") or "Bilinmiyor",
            "size": int(item.get("Size") or 0),
        })

    drives = []
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        root = Path(f"{letter}:\\")
        try:
            if root.exists():
                usage = shutil.disk_usage(root)
                drives.append({"root": f"{letter}:", "total": usage.total,
                               "used": usage.used, "free": usage.free})
        except OSError:
            continue

    windows = f"{os_caption} {platform.version()}".strip() if os_caption else \
        f"{platform.system()} {platform.release()} {platform.version()}"

    return {
        "windows": windows,
        "cpu": cpu.strip(),
        "ram_total": total_ram,
        "ram_available": avail_ram,
        "gpus": gpus,
        "disks": disks,
        "drives": drives,
        "admin": is_admin(),
        "system_drive": os.environ.get("SystemDrive", "C:"),
    }


HEALTH_TONE = {
    "Healthy": "ok",
    "Warning": "warn",
    "Unhealthy": "danger",
}


def health_label(value: str) -> tuple[str, str]:
    """Get-PhysicalDisk HealthStatus -> (Turkce etiket, ton)."""
    mapping = {
        "Healthy": ("Sağlıklı", "ok"),
        "Warning": ("Uyarı", "warn"),
        "Unhealthy": ("Sorunlu", "danger"),
        "Unknown": ("Bilinmiyor", "muted"),
    }
    return mapping.get(value, (value or "Bilinmiyor", "muted"))
