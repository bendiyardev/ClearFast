# Değişiklik günlüğü / Changelog

Bu proje [Semantic Versioning](https://semver.org/lang/tr/) kullanır.
This project adheres to [Semantic Versioning](https://semver.org/).

---

## [0.3.2] — 2026-08-27

Windows kurulum ve kaldırma akışını sadeleştiren, doğrudan Windows API kullanımını artıran bakım sürümü.
*Maintenance release that simplifies the Windows install/uninstall flow and moves more operations to direct Windows APIs.*

### Değişti / Changed

**TR**
- Kaldırma akışı daha öngörülebilir hale getirildi; silinebilen dosyalar doğrudan işleniyor, kilitli dosyalar için süreç kimliği izleniyor.
- Kısayol oluşturma doğrudan Windows kabuk arayüzüne (`IShellLinkW` + `IPersistFile`) taşındı.
- Özel klasör çözümleme ve süreç denetimi doğrudan Windows API çağrılarına taşındı:
  `SHGetKnownFolderPath` ve `EnumProcesses`.
- Kurulum akışındaki gereksiz kabuk çağrıları kaldırıldı.

**EN**
- Uninstall flow was made more predictable; removable files are handled directly and locked files are finalized by tracking the process ID.
- Shortcut creation moved to the native Windows shell interface (`IShellLinkW` + `IPersistFile`).
- Known-folder lookup and process checks moved to direct Windows API calls:
  `SHGetKnownFolderPath` and `EnumProcesses`.
- Unnecessary shell calls were removed from the installer flow.

### Eklendi / Added
- `cf_win.py` — saf Win32/COM yardımcıları (ctypes ile, bağımlılıksız).
  *Pure Win32/COM helpers via ctypes, no dependencies.*
- `tools/selftest.py` — 66 denetimlik bütünlük testi: çizim katmanı, temizlik hedefleri, silme davranışı, ölçümler, Windows arayüzü, kurulum/kaldırma turu ve arayüz sayfaları.
  *A 66-check integrity test covering the application stack.*

---

## [0.3.1] — 2026-08-27

Paketleme ve dağıtım akışını daha sade ve doğrulanabilir hale getiren bakım sürümü.
*A maintenance release focused on simpler, more verifiable packaging and distribution.*

### Değişti / Changed

**TR**
- Tek dosya yerine tek klasör dağıtımına geçildi; çalışma zamanı dosyaları açık bir klasör yapısında tutuluyor.
- Kurulum ayrı bir ikili yerine aynı uygulamanın kurulum kipi olarak çalışıyor (`ClearFast.exe --setup`).
- `ClearFast.spec` içinde `upx=False` açıkça belirtildi.
- Dağıtım boyutu 38 MB'den 30 MB'ye düştü.
- Derleme tek betiğe indirildi: `Build.bat`.

**EN**
- Distribution moved from a single-file package to a one-folder layout with the runtime kept in a visible directory structure.
- Setup now runs as a mode of the same executable (`ClearFast.exe --setup`) instead of a separate binary.
- `upx=False` is stated explicitly in `ClearFast.spec`.
- Distribution size was reduced from 38 MB to 30 MB.
- Build flow was reduced to a single script: `Build.bat`.

### Eklendi / Added
- `docs/ANTIVIRUS.md` — paket doğrulama, bütünlük kontrolü ve kod imzalama notları.
  *Package verification, integrity checks and code-signing notes.*
- Kurulum, program klasörünün kendisine kurulmaya çalışılmasını engelliyor.
  *The installer refuses to install a folder onto itself.*

### Düzeltildi / Fixed
- Kurulum kipi, çalışan uygulama denetiminde kendi sürecini de sayıyordu.
  *Setup mode counted its own process when checking whether the app was running.*

---

## [0.3.0] — 2026-08-27

### Eklendi / Added

**TR**
- **Performans sayfası:** saniyede yenilenen işlemci, bellek ve ekran kartı grafikleri; sistemi en çok yoran uygulamaların işlemci/bellek kullanımına göre sıralı, işlemleri ada göre gruplayan listesi.
- **Donanım sağlığı sayfası:** bellek modülleri (yuva, kapasite, tip, hız, model), ekran kartı sıcaklık / video bellek / fan / güç ölçümleri, disk aşınma-sıcaklık-hata sayaçları, Windows Bellek Tanılama kısayolu.
- **Tam sistem künyesi:** bilgisayar, anakart, BIOS + tarihi, işlemci çekirdek ve iş parçacığı sayısı, bellek modülü özeti, Windows yapı numarası, açık kalma süresi.
- **13 yeni yapay zekâ önbellek kaynağı:** Claude Desktop (Store sürümü dahil), Claude Code, OpenAI Codex, Cursor, Trae, Antigravity (Gemini), Windsurf / Codeium, LM Studio, Copilot / Cline / Continue / Warp / Ollama günlükleri, PyTorch ve Triton derleme önbellekleri, NVIDIA CUDA JIT önbelleği.
- **Opsiyonel paket önbellekleri:** uv, pnpm, Yarn ve eklenti indirme önbellekleri (varsayılan olarak seçili değil).
- **Kurulum programı:** tek dosyalık, yönetici yetkisi istemeyen kurucu; kısayollar, sistem kaydı ve kaldırma aracı dahil.
- **İletişim bağlantıları:** sol menünün altında ve kurulum ekranında.

**EN**
- **Performance page** with per-second CPU, memory and GPU charts plus a top-consumers list that groups processes by name.
- **Hardware health page** with memory modules, GPU temperature / VRAM / fan / power, and disk wear-temperature-error counters.
- **Full system specification** on the System page.
- **13 new AI cache sources** (Claude Desktop, Claude Code, OpenAI Codex, Cursor, Trae, Antigravity, Windsurf, LM Studio, agent logs, PyTorch/Triton compile caches, NVIDIA CUDA JIT).
- **Optional package caches:** uv, pnpm, Yarn, plugin download caches.
- **Installer** — single file, no administrator rights required.
- **Contact links** in the sidebar and installer.

### Değişti / Changed
- Arayüz baştan yazıldı: shadcn/ui token yaklaşımını Tk üzerine taşıyan bir tasarım sistemi, kenarı yumuşatılmış yuvarlak köşeler, DPI farkındalığı.
  *UI rewritten on a new design system with anti-aliased corners and DPI awareness.*
- Temizleyici listesi hedef bazında gruplandı: 147 klasör → 21 okunur satır.
  *Cleaner list now groups folders by source.*
- Arka plan işleri kuyruk tabanlı hale getirildi.
  *Background work moved to a result queue.*
- Boyutlar Türkçe ondalık ayracıyla gösteriliyor.
  *Turkish decimal separator.*

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
  *First release: temp and cache cleaner with system information.*
