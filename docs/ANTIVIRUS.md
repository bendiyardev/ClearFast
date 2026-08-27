# Virüs tarayıcı uyarıları · Antivirus warnings

[Türkçe](#türkçe) · [English](#english)

---

## Türkçe

### Kısa cevap

ClearFast'te zararlı kod **yoktur**. Kaynak kodun tamamı bu depodadır ve
derleme çıktısını kendiniz üretebilirsiniz. Bazı virüs tarayıcıların verdiği
uyarılar, Python ile yazılmış ve PyInstaller ile paketlenmiş programlarda
görülen **yanlış pozitiflerdir**.

### Neden oluyor?

Bir tarayıcı bir dosyayı üç şeye bakarak değerlendirir: nasıl paketlendiği,
ne yaptığı ve kim tarafından imzalandığı. ClearFast üçünde de dezavantajlıydı;
0.3.1 sürümünde ilk ikisi düzeltildi.

| Tetikleyici | Neden şüpheli görünür | Durum |
|---|---|---|
| `--onefile` paketleme | Program her açılışta kendini `%TEMP%\_MEIxxxxx` altına açıp oradan çalışır. Paketleyici zararlıların birebir davranışıdır. | **Kaldırıldı** — 0.3.1'den itibaren tek klasör (onedir) dağıtımı |
| Gömülü EXE taşıma | Kurulum programı, uygulama EXE'sini kendi içinde taşıyıp diske yazıyordu. "Dropper" teriminin tam tanımı budur. | **Kaldırıldı** — kurulum artık gömülü ikili taşımaz, bulunduğu klasörü kopyalar |
| UPX sıkıştırma | Paketleme sezgiselini doğrudan tetikler. | Hiç kullanılmadı; `ClearFast.spec` içinde açıkça `upx=False` |
| Kod imzası yok | İmzasız dosyaların itibar puanı sıfırdır, sezgisel skorları ağırlaşır. | Sürüyor — aşağıya bakın |
| Davranış | Dosya siler, süreç listesi okur, PowerShell çalıştırır, kayıt defterine yazar. Hepsi programın işidir ama sezgisel tarayıcıya şüpheli görünür. | Değişemez — programın işlevi budur |

### 0.3.1'de ne değişti?

```
  ESKI (0.3.0)                          YENI (0.3.1)
  ─────────────────────────────         ─────────────────────────────
  ClearFast.exe                         ClearFast\
    └─ icinde gizli Python runtime         ├─ ClearFast.exe   (2,6 MB)
       calisirken %TEMP%'e acilir          └─ _internal\      (acikta duran
                                              runtime, gizlenmez)
  ClearFastSetup.exe
    └─ icinde ClearFast.exe (payload)    Kurulum ayri bir ikili degil:
       calisirken diske yazilir            ClearFast.exe --setup
                                           klasoru oldugu gibi kopyalar
```

Artık ortada ne kendini açan bir arşiv ne de içinden EXE çıkan bir program
var. Bu iki kalıp, uyarıların ana kaynağıydı.

### Yine de uyarı alırsanız

**1. Dosyayı doğrulayın.** Sürüm sayfasındaki `SHA256SUMS.txt` dosyasındaki
değerle karşılaştırın:

```powershell
Get-FileHash .\ClearFast-0.3.1-Windows.zip -Algorithm SHA256
```

**2. Kendiniz derleyin.** Bize güvenmenize gerek yok:

```bat
git clone https://github.com/bendiyardev/ClearFast
cd ClearFast
Build.bat
```

Çıkan `dist\ClearFast\ClearFast.exe` ile yayınlananın davranışı aynıdır.
(Bayt bayt aynı olmaz: PyInstaller çıktısı yeniden üretilebilir değildir —
zaman damgaları ve yol bilgileri değişir.)

**3. Yanlış pozitif bildirin.** Bu, sorunu kalıcı çözen tek yoldur ve
ücretsizdir. Genellikle 1–5 iş günü içinde imza güncellenir.

| Tarayıcı | Bildirim kanalı |
|---|---|
| Microsoft Defender | https://www.microsoft.com/wdsi/filesubmission |
| Kaspersky | https://opentip.kaspersky.com — sonra "Yanlış pozitif bildir" |
| K7 Computing | https://support.k7computing.com — destek talebi + dosya |
| Bkav | https://www.bkav.com/support — veya `support@bkav.com.vn` |
| Zillya | https://zillya.com — destek formu veya `virus@zillya.com` |

> Bildirim adresleri zaman zaman değişebilir; çalışmıyorsa üreticinin
> sitesinde "false positive" / "submit a sample" araması yapın.

### Kalıcı çözüm: kod imzalama

Yanlış pozitifleri gerçekten bitiren şey, dosyanın bir sertifika ile
imzalanması ve zamanla itibar kazanmasıdır. Seçenekler:

| Yöntem | Yıllık maliyet | Etki |
|---|---|---|
| **Azure Trusted Signing** | ~120 USD (aylık ~10 USD) | En ucuk meşru yol; kimlik doğrulaması ister |
| **OV kod imzalama sertifikası** | ~200–400 USD | İtibar zamanla birikir |
| **EV kod imzalama sertifikası** | ~300–600 USD | SmartScreen'de anında itibar |
| Kendinden imzalı sertifika | ücretsiz | **Fayda sağlamaz** — tarayıcılar bilinmeyen CA'ya güvenmez |

Kendinden imzalı sertifikanın işe yaramadığını özellikle belirtmek gerekir;
internette sıkça önerilir ama virüs tarayıcılar açısından imzasız dosyadan
farkı yoktur.

### Programın gerçekte ne yaptığı

Şüpheli görünen her davranışın kaynak koddaki karşılığı:

| Davranış | Nerede | Ne için |
|---|---|---|
| Dosya silme | `cf_core.delete_contents()` | Yalnızca onayladığınız önbellek klasörlerinin içeriği |
| Süreç listesi okuma | `cf_metrics.ProcessMonitor` | Performans sayfasındaki "en çok yoran uygulamalar" |
| PowerShell çalıştırma | `cf_core.run_ps`, `cf_metrics.run_ps` | Donanım bilgisi için CIM sorguları (`-NoProfile -NonInteractive`) |
| Kayıt defterine yazma | `ClearFastSetup.write_registry()` | Yalnızca `HKCU\...\Uninstall\ClearFast` — kaldırma kaydı |
| Kısayol oluşturma | `ClearFastSetup.make_shortcut()` | Başlat menüsü ve masaüstü kısayolu |
| Klasör kopyalama | `ClearFastSetup.install()` | Kurulum: programın klasörünü hedefe kopyalar |

Ağ bağlantısı **yoktur**: program hiçbir yere veri göndermez, güncelleme
sorgusu yapmaz, telemetri toplamaz. `webbrowser.open` yalnızca siz iletişim
bağlantısına tıkladığınızda çalışır.

---

## English

### Short answer

ClearFast contains **no malicious code**. The complete source is in this
repository and you can reproduce the build yourself. Warnings from some
antivirus engines are **false positives** typical of Python programs packaged
with PyInstaller.

### Why does it happen?

An engine judges a file by how it is packaged, what it does, and who signed
it. ClearFast was at a disadvantage on all three; 0.3.1 fixes the first two.

| Trigger | Why it looks suspicious | Status |
|---|---|---|
| `--onefile` packaging | The program unpacks itself into `%TEMP%\_MEIxxxxx` on every launch and runs from there — exactly what packed malware does. | **Removed** — one-folder (onedir) distribution since 0.3.1 |
| Embedded EXE payload | The installer carried the application EXE inside itself and wrote it to disk. That is the definition of a dropper. | **Removed** — setup carries no embedded binary; it copies its own folder |
| UPX compression | Directly triggers packer heuristics. | Never used; explicitly `upx=False` in `ClearFast.spec` |
| No code signature | Unsigned files have zero reputation, which raises heuristic scores. | Still true — see below |
| Behaviour | Deletes files, reads the process list, runs PowerShell, writes to the registry. All of it is the program's job, but heuristics see red flags. | Cannot change — this is what the tool does |

### What changed in 0.3.1

```
  OLD (0.3.0)                           NEW (0.3.1)
  ─────────────────────────────         ─────────────────────────────
  ClearFast.exe                         ClearFast\
    └─ hidden Python runtime inside        ├─ ClearFast.exe   (2.6 MB)
       unpacks to %TEMP% at runtime        └─ _internal\      (runtime in
                                              plain sight)
  ClearFastSetup.exe
    └─ ClearFast.exe inside (payload)    Setup is not a separate binary:
       written to disk at runtime          ClearFast.exe --setup
                                           copies the folder as it is
```

There is no self-extracting archive and no program that produces an EXE from
inside itself. Those two patterns were the main source of the warnings.

### If you still get a warning

**1. Verify the file** against `SHA256SUMS.txt` on the release page:

```powershell
Get-FileHash .\ClearFast-0.3.1-Windows.zip -Algorithm SHA256
```

**2. Build it yourself** — you do not have to trust us:

```bat
git clone https://github.com/bendiyardev/ClearFast
cd ClearFast
Build.bat
```

The resulting `dist\ClearFast\ClearFast.exe` behaves identically to the
published one. (It will not be byte-identical: PyInstaller output is not
reproducible — timestamps and paths differ.)

**3. Report the false positive.** This is the only permanent fix, it is free,
and signatures are usually updated within 1–5 business days.

| Engine | Submission channel |
|---|---|
| Microsoft Defender | https://www.microsoft.com/wdsi/filesubmission |
| Kaspersky | https://opentip.kaspersky.com — then "Report false positive" |
| K7 Computing | https://support.k7computing.com — support ticket with the file |
| Bkav | https://www.bkav.com/support — or `support@bkav.com.vn` |
| Zillya | https://zillya.com — support form or `virus@zillya.com` |

> Submission addresses change occasionally; if a link is dead, search the
> vendor's site for "false positive" or "submit a sample".

### The permanent fix: code signing

What actually ends false positives is signing the binary with a certificate
and accumulating reputation over time.

| Option | Yearly cost | Effect |
|---|---|---|
| **Azure Trusted Signing** | ~120 USD (~10/month) | Cheapest legitimate route; requires identity verification |
| **OV code-signing certificate** | ~200–400 USD | Reputation accrues over time |
| **EV code-signing certificate** | ~300–600 USD | Immediate SmartScreen reputation |
| Self-signed certificate | free | **No benefit** — engines do not trust an unknown CA |

Self-signed certificates are frequently suggested online but are worthless
here: to an antivirus engine the file is still effectively unsigned.

### What the program actually does

Every behaviour that looks suspicious, mapped to the source:

| Behaviour | Where | Purpose |
|---|---|---|
| Deleting files | `cf_core.delete_contents()` | Only the contents of cache folders you confirmed |
| Reading the process list | `cf_metrics.ProcessMonitor` | The "top consumers" list on the Performance page |
| Running PowerShell | `cf_core.run_ps`, `cf_metrics.run_ps` | CIM queries for hardware information (`-NoProfile -NonInteractive`) |
| Writing the registry | `ClearFastSetup.write_registry()` | Only `HKCU\...\Uninstall\ClearFast` — the uninstall entry |
| Creating shortcuts | `ClearFastSetup.make_shortcut()` | Start Menu and Desktop shortcuts |
| Copying a folder | `ClearFastSetup.install()` | Installation: copies the program folder to the target |

There is **no network access**: the program sends nothing anywhere, checks for
no updates and collects no telemetry. `webbrowser.open` runs only when you
click a contact link yourself.
