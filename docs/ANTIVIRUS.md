# Güvenlik ve doğrulama notları · Security & verification notes

[Türkçe](#türkçe) · [English](#english)

---

## Türkçe

ClearFast açık kaynaklıdır; yayınlanan paketin kaynak kodu bu depoda bulunur ve `Build.bat` ile yerel olarak yeniden derlenebilir.

### Paketleme yaklaşımı

0.3.1 ve 0.3.2 sürümlerinde Windows dağıtım ve kurulum akışı sadeleştirildi:

- Tek dosya paket yerine tek klasör dağıtımı kullanılır.
- Kurulum ayrı bir ikili yerine `ClearFast.exe --setup` kipi üzerinden çalışır.
- Kısayollar doğrudan Windows kabuk arayüzüyle oluşturulur.
- Özel klasör çözümleme `SHGetKnownFolderPath` ile yapılır.
- Süreç denetimi `EnumProcesses` ile yapılır.
- Kaldırma akışı süreç kimliği takibiyle tamamlanır.
- `ClearFast.spec` içinde `upx=False` açıkça belirtilmiştir.

Bu değişikliklerin amacı kurulum davranışını daha sade, izlenebilir ve standart Windows API'leriyle uyumlu hale getirmektir.

### Dosyayı doğrulama

Sürüm sayfasındaki `SHA256SUMS.txt` ile indirilen paketin özetini karşılaştırabilirsiniz:

```powershell
Get-FileHash .\ClearFast-0.3.2-Windows.zip -Algorithm SHA256
```

### Kaynaktan derleme

```bat
git clone https://github.com/bendiyardev/ClearFast
cd ClearFast
Build.bat
py -3 tools\selftest.py
```

`tools/selftest.py` uygulamanın temel katmanlarını, temizlik hedeflerini, kurulum/kaldırma akışını ve arayüz bileşenlerini doğrulayan bütünlük denetimlerini çalıştırır.

### Kod imzalama

Yayınlanan `ClearFast.exe` şu anda ticari bir kod imzalama sertifikasıyla imzalanmamıştır. Bu nedenle Windows SmartScreen bazı sistemlerde "Bilinmeyen yayımcı" uyarısı gösterebilir.

Bu durum uygulamanın kaynak kodunu, SHA-256 özetini veya yerel derleme sonucunu doğrulamanıza engel değildir.

### Veri ve ağ davranışı

ClearFast:

- yalnızca kullanıcı tarafından onaylanan yeniden oluşturulabilir önbellek ve geçici dosya hedeflerini temizler,
- uygulama kök klasörlerini ve kullanıcı verisi olarak sınıflandırılan alanları korur,
- telemetri toplamaz,
- arka planda güncelleme sorgusu yapmaz,
- kullanıcı etkileşimi olmadan harici bir servise veri göndermez.

Kaynak kod üzerinden ilgili davranışları doğrudan inceleyebilirsiniz.

---

## English

ClearFast is open source. The source for the published package is available in this repository and can be rebuilt locally with `Build.bat`.

### Packaging approach

Versions 0.3.1 and 0.3.2 simplified the Windows distribution and installer flow:

- A one-folder distribution is used instead of a single-file package.
- Setup runs through `ClearFast.exe --setup` instead of a separate installer binary.
- Shortcuts are created through the native Windows shell interface.
- Known folders are resolved with `SHGetKnownFolderPath`.
- Process checks use `EnumProcesses`.
- Uninstall completion uses process-ID tracking.
- `upx=False` is explicitly configured in `ClearFast.spec`.

The goal is a simpler, easier-to-audit installer flow built around standard Windows APIs.

### Verify the package

Compare the downloaded archive against `SHA256SUMS.txt` from the release page:

```powershell
Get-FileHash .\ClearFast-0.3.2-Windows.zip -Algorithm SHA256
```

### Build from source

```bat
git clone https://github.com/bendiyardev/ClearFast
cd ClearFast
Build.bat
py -3 tools\selftest.py
```

`tools/selftest.py` runs integrity checks across the application layers, cleanup targets, install/uninstall flow and UI components.

### Code signing

The published `ClearFast.exe` is not currently signed with a commercial code-signing certificate. Windows SmartScreen may therefore show an "Unknown publisher" warning on some systems.

You can independently verify the source, SHA-256 checksum and local build output.

### Data and network behaviour

ClearFast:

- cleans only user-approved, reproducible cache and temporary-file targets,
- protects application roots and locations classified as user data,
- collects no telemetry,
- performs no background update checks,
- sends no data to external services without explicit user interaction.

The complete implementation can be reviewed directly in the source code.
