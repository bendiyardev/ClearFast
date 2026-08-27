# Değişiklik günlüğü / Changelog

Bu proje [Semantic Versioning](https://semver.org/lang/tr/) kullanır.
This project adheres to [Semantic Versioning](https://semver.org/).

---

## [0.3.2] — 2026-08-27

Kurulumdaki zararlı yazılım benzeri komut kalıplarını kaldıran sürüm.
*Removes malware-like command patterns from the installer.*

### Değişti / Changed

**TR**
- **Kendini silme kalıbı kaldırıldı.** Kaldırma işlemi
  `cmd /c ping 127.0.0.1 -n 3 >nul & rmdir /s /q` komutunu bırakıyordu; bu,
  zararlı yazılımların kendini silme tekniğinin ders kitabı örneğidir ve imza
  veritabanlarında doğrudan kuralı vardır. Artık silinebilen her şey anında
  siliniyor, kilitli kalan dosyalar için süreç kimliği izleniyor (uyku hilesi
  yok).
- **Kısayollar artık kabuk üzerinden oluşturulmuyor.** `WScript.Shell` +
  `CreateShortcut`, kalıcılık tekniği olarak bilinir. Yerine doğrudan Windows
  kabuk arayüzü (`IShellLinkW` + `IPersistFile`) kullanılıyor.
- **Özel klasörler ve süreç araması da API'ye taşındı.**
  `[Environment]::GetFolderPath` → `SHGetKnownFolderPath`,
  `Get-Process` → `EnumProcesses`.
- Sonuç: **kurulum artık hiç PowerShell çalıştırmıyor**; tek kalan kullanım,
  kaldırma sonrası kilitli dosyaları temizleyen bekleme komutu.

**EN**
- **Self-delete pattern removed.** Uninstall used to leave behind
  `cmd /c ping 127.0.0.1 -n 3 >nul & rmdir /s /q` — the textbook malware
  self-deletion technique, with dedicated signature rules. Everything
  deletable is now removed immediately and the process ID is watched for the
  locked remainder (no sleep trick).
- **Shortcuts are no longer created through a shell.** `WScript.Shell` +
  `CreateShortcut` is a known persistence technique; replaced with the Windows
  shell interface directly (`IShellLinkW` + `IPersistFile`).
- **Known folders and process lookup moved to the API too:**
  `SHGetKnownFolderPath` and `EnumProcesses`.
- Result: **the installer no longer spawns PowerShell at all**; the only
  remaining use is the wait-and-clean step after uninstall.

### Eklendi / Added
- `cf_win.py` — saf Win32/COM yardımcıları (ctypes ile, bağımlılıksız).
  *Pure Win32/COM helpers via ctypes, no dependencies.*
- `tools/selftest.py` — 66 denetimlik bütünlük testi: çizim katmanı, temizlik
  hedeflerinin güvenlik değişmezleri, silme davranışı, ölçümler, Windows
  arayüzü, kurulum/kaldırma turu ve altı arayüz sayfası.
  *A 66-check integrity test covering every layer.*

---

## [0.3.1] — 2026-08-27

Virüs tarayıcı yanlış pozitiflerini gideren paketleme sürümü.
*A packaging release that removes antivirus false positives.*

### Değişti / Changed

**TR**
- **Tek dosya yerine tek klasör dağıtımı.** `--onefile` ile üretilen EXE her
  açılışta kendini `%TEMP%\_MEIxxxxx` altına açıyordu; bu, paketleyici
  zararlıların davranışı olduğu için Kaspersky ve Bkav gibi motorlarda statik
  yanlış pozitife yol açıyordu. Artık `dist\ClearFast\` klasörü dağıtılıyor.
- **Kurulum programı ayrı bir ikili olmaktan çıktı.** Eskiden
  `ClearFastSetup.exe`, `ClearFast.exe`'yi kendi içinde taşıyıp diske
  yazıyordu — "dropper" teriminin tam tanımı. Artık kurulum, aynı EXE'nin bir
  kipi (`ClearFast.exe --setup`) ve bulunduğu klasörü hedefe kopyalıyor.
- `ClearFast.spec` içinde `upx=False` açıkça belirtildi.
- Dağıtım boyutu 38 MB'den 30 MB'ye düştü (tek çalışma zamanı paylaşılıyor).
- Derleme tek betiğe indi: `Build.bat`.

**EN**
- **One-folder distribution instead of one file.** The `--onefile` build
  unpacked itself into `%TEMP%\_MEIxxxxx` on every launch — the behaviour of
  packed malware, which caused static false positives. Now `dist\ClearFast\`
  is shipped.
- **The installer is no longer a separate binary.** It used to carry
  `ClearFast.exe` inside itself and write it to disk, which is the definition
  of a dropper. Setup is now a mode of the same executable
  (`ClearFast.exe --setup`) that copies its own folder to the target.
- `upx=False` stated explicitly in `ClearFast.spec`.
- Distribution size down from 38 MB to 30 MB (a single shared runtime).
- Building reduced to one script: `Build.bat`.

### Eklendi / Added
- `docs/ANTIVIRUS.md` — yanlış pozitiflerin nedeni, dosyanın nasıl
  doğrulanacağı, üreticilere nasıl bildirileceği ve kod imzalama seçenekleri.
  *Why false positives happen, how to verify the file, how to report them,
  and the code-signing options.*
- Kurulum, program klasörünün kendisine kurulmaya çalışılmasını engelliyor.
  *The installer refuses to install a folder onto itself.*

### Düzeltildi / Fixed
- Kurulum kipi, çalışan uygulama denetiminde kendi sürecini de sayıyordu.
  *Setup mode counted its own process when checking whether the app was
  running.*

---

## [0.3.0] — 2026-08-27

### Eklendi / Added

**TR**
- **Performans sayfası:** saniyede yenilenen işlemci, bellek ve ekran kartı
  grafikleri; sistemi en çok yoran uygulamaların işlemci/bellek kullanımına
  göre sıralı, işlemleri ada göre gruplayan listesi.
- **Donanım sağlığı sayfası:** bellek modülleri (yuva, kapasite, tip, hız,
  model), ekran kartı sıcaklık / video bellek / fan / güç ölçümleri, disk
  aşınma-sıcaklık-hata sayaçları, Windows Bellek Tanılama kısayolu.
- **Tam sistem künyesi:** bilgisayar, anakart, BIOS + tarihi, işlemci çekirdek
  ve iş parçacığı sayısı, bellek modülü özeti, Windows yapı numarası, açık
  kalma süresi.
- **13 yeni yapay zekâ önbellek kaynağı:** Claude Desktop (Store sürümü dahil),
  Claude Code, OpenAI Codex, Cursor, Trae, Antigravity (Gemini), Windsurf /
  Codeium, LM Studio, Copilot / Cline / Continue / Warp / Ollama günlükleri,
  PyTorch ve Triton derleme önbellekleri, NVIDIA CUDA JIT önbelleği.
- **Opsiyonel paket önbellekleri:** uv, pnpm, Yarn ve eklenti indirme
  önbellekleri (varsayılan olarak seçili değil).
- **Kurulum programı:** tek dosyalık, yönetici yetkisi istemeyen kurucu;
  kısayollar, sistem kaydı ve kaldırma aracı dahil.
- **İletişim bağlantıları:** sol menünün altında ve kurulum ekranında.

**EN**
- **Performance page** with per-second CPU, memory and GPU charts plus a
  top-consumers list that groups processes by name.
- **Hardware health page** with memory modules, GPU temperature / VRAM / fan /
  power, and disk wear-temperature-error counters.
- **Full system specification** on the System page.
- **13 new AI cache sources** (Claude Desktop, Claude Code, OpenAI Codex,
  Cursor, Trae, Antigravity, Windsurf, LM Studio, agent logs, PyTorch/Triton
  compile caches, NVIDIA CUDA JIT).
- **Optional package caches:** uv, pnpm, Yarn, plugin download caches.
- **Installer** — single file, no administrator rights required.
- **Contact links** in the sidebar and installer.

### Değişti / Changed
- Arayüz baştan yazıldı: shadcn/ui token yaklaşımını Tk üzerine taşıyan bir
  tasarım sistemi, kenarı yumuşatılmış yuvarlak köşeler, DPI farkındalığı.
  *UI rewritten on a new design system with anti-aliased corners and DPI
  awareness.*
- Temizleyici listesi hedef bazında gruplandı: 147 klasör → 21 okunur satır.
  *Cleaner list now groups folders by source.*
- Arka plan işleri kuyruk tabanlı hale getirildi (iş parçacığından `after()`
  çağrısı kaldırıldı). *Background work moved to a result queue.*
- Boyutlar Türkçe ondalık ayracıyla gösteriliyor. *Turkish decimal separator.*

### Düzeltildi / Fixed
- Yan yana kartların başlıkları yeniden çizimde siliniyordu.
- Türkçe büyük harf dönüşümü (`SISTEM DISKI` → `SİSTEM DİSKİ`).
- Onay penceresinin başlık satırı kırpılıyordu.
- Satır üzerine gelindiğinde rozetin zemini beyaz kalıyordu.
- Gizli sayfadayken uyarı kutularının görünürlük takibi.
- Kullanılmayan `queue` nesneleri ve `sys` içe aktarımı kaldırıldı.

---

## [0.2.0] — 2026-08-27

- Arayüz yeniden tasarlandı, kurulum programı eklendi.
  *Redesigned interface, installer added.*

---

## [0.1.0] — 2026-08-27

- İlk sürüm: geçici dosya / önbellek temizleyici ve sistem bilgisi ekranı.
  *First release: temp and cache cleaner with a system information screen.*
