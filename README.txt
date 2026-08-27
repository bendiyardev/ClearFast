ClearFast 0.3.0
===============

Windows için tek pencerede toplanmış bakım aracı: sistem künyesi, canlı
performans grafikleri, donanım sağlığı ve yalnızca sizin onayınızla çalışan bir
temizleyici. Harici Python paketi gerektirmez.


KURULUM VE ÇALIŞTIRMA
---------------------
ZIP arşivini klasörüyle birlikte çıkarın. ClearFast.exe, yanındaki _internal
klasörü olmadan çalışmaz.

1) Kurarak (önerilen)
   Kurulum.bat  (aynısı: ClearFast.exe --setup)
   Yönetici yetkisi istemez. Uygulamayı %LOCALAPPDATA%\Programs\ClearFast
   klasörüne kurar, Başlat menüsü ve masaüstü kısayolunu oluşturur, Windows
   "Uygulamalar" listesine kaydeder.
   Kaldırmak için: Ayarlar > Uygulamalar > ClearFast > Kaldır
   veya kurulum klasöründe: ClearFast.exe --uninstall

2) Taşınabilir
   Doğrudan ClearFast.exe dosyasını çalıştırın. Hiçbir şey kurmaz, kayıt
   defterine yazmaz, USB'den de çalışır.

3) Doğrudan kaynaktan
   Python 3 kuruluysa ClearFast.bat dosyasına çift tıklayın.

Derleme:  Build.bat  ->  dist\ClearFast\
Python 3.10+ yeterlidir; gereken tek paket PyInstaller'dır ve betik eksikse
kendisi kurar.

Kurulum ve kaldırma ayrı bir program değildir; aynı EXE'nin kipleridir.
Bu, içinde başka bir EXE taşıyan bir kurucu olmadığı anlamına gelir ve
virüs tarayıcı yanlış pozitiflerini büyük ölçüde engeller. Ayrıntı:
ANTIVIRUS.md


SAYFALAR
--------
Sistem            Bilgisayar, anakart, BIOS, işlemci (çekirdek / iş parçacığı /
                  frekans), bellek modülü özeti, ekran kartı ve sürücüsü,
                  Windows yapısı, açık kalma süresi; sürücü doluluk çubukları ve
                  fiziksel disk sağlık durumu.
Performans        Saniyede yenilenen işlemci, bellek ve ekran kartı grafikleri;
                  sistemi en çok yoran uygulamaların işlemci ve bellek
                  kullanımına göre sıralı listesi (işlemleri ada göre gruplar).
Donanım sağlığı   Bellek modülleri (yuva, kapasite, tip, hız, model), ekran kartı
                  sıcaklık / video bellek / fan / güç ölçümleri, disk aşınma,
                  sıcaklık ve hata sayaçları. Windows Bellek Tanılama kısayolu.
Temizleyici       Kategorilere ayrılmış tarama sonuçları, satır bazında seçim,
                  bağlama duyarlı uyarılar ve silme öncesi ayrıntılı onay.
Korunanlar        Büyük ama silinmemesi gereken model/veri klasörleri.
İşlem günlüğü     Oturumdaki tüm tarama ve temizlik işlemleri.

Ölçümler: işlemci ve süreç kullanımı Windows API'sinden (GetSystemTimes,
EnumProcesses) okunur; ekran kartı ölçümleri nvidia-smi'den gelir; bellek
modülleri ve disk sayaçları CIM üzerinden alınır. Disk aşınma sayaçları için
yönetici yetkisi gerekir, yoksa arayüz bunu belirtir.


VARSAYILAN OLARAK TEMİZLENENLER
-------------------------------
Windows       Kullanıcı Temp, Windows Temp, çökme dökümleri
Ekran kartı   DirectX shader, NVIDIA DX/OpenGL, NVIDIA CUDA JIT önbelleği
Tarayıcı      Chrome / Edge / Brave / Firefox önbelleği (profil verisi değil)
Yapay zekâ    Claude Desktop, Claude Code, OpenAI Codex, Cursor, Trae,
              Antigravity (Gemini), Windsurf / Codeium, LM Studio;
              Copilot, Cline, Continue, Warp ve Ollama günlükleri;
              PyTorch / Triton derleme önbellekleri
Geliştirme    VS Code önbellek ve günlükleri

Yapay zekâ uygulamaları için ClearFast, uygulama klasörünün tamamını değil,
yalnızca adı bilinen ve yeniden oluşturulabilir olan klasörleri hedefler
(Cache, Code Cache, GPUCache, ShaderCache, logs, Crashpad ...). Uygulamanın
kök klasörü, oturum bilgisi ve sohbet geçmişi hiçbir koşulda hedeflenmez.


OPSİYONEL, VARSAYILAN OLARAK SEÇİLİ DEĞİL
-----------------------------------------
pip, npm, uv, pnpm, Yarn paket önbellekleri ve eklenti indirme önbellekleri
(Claude Code / Cursor). Seçildiklerinde arayüzde sarı bir uyarı belirir: veri
kaybı olmaz, yalnızca ilgili paketler bir sonraki kurulumda yeniden indirilir.


BİLEREK ASLA SİLİNMEYENLER
--------------------------
"Korunanlar" sekmesinde yalnızca boyutları raporlanır:
Hugging Face model deposu, Ollama modelleri, LM Studio modelleri, PyTorch model
önbelleği, Claude Code verisi (.claude), Gemini / Antigravity verisi, OpenAI
Codex verisi, VS Code eklentileri, Cursor kullanıcı verisi.
Ayrıca hiçbir zaman hedeflenmeyenler: proje klasörleri, Belgeler / Masaüstü /
İndirilenler, tarayıcı şifreleri, profilleri ve yer imleri, sohbet geçmişleri.


NOTLAR
------
- Kilitli veya erişilemeyen dosyalar sessizce atlanır, işlem durmaz.
- Windows Temp'in tamamı için yönetici yetkisi gerekir; yetki yoksa arayüz
  bunu bir uyarı kutusuyla önceden bildirir.
- Silinen dosyalar Geri Dönüşüm Kutusu'na gitmez.
- Fiziksel disk sağlığı Windows'un Get-PhysicalDisk bilgisidir; ayrıntılı SMART
  değerleri "Donanım sağlığı" sayfasındaki aşınma sayaçlarından okunur.
- Önbellek temizliğinden sonra ilgili uygulamanın ilk açılışı biraz yavaşlar.
- Temizleyici'de bir satıra çift tıklamak o klasörü Gezgin'de açar.


İLETİŞİM
--------
  Telegram   @dyrdev        https://t.me/dyrdev
  X          @diyrdev       https://x.com/diyrdev
  GitHub     bendiyardev    https://github.com/bendiyardev
  R10.net    dyrdev         https://www.r10.net/profil/226267-dyrdev.html

Bu bağlantılar uygulamanın sol menüsünün en altında ve kurulum ekranının sol
panelinde ikonlarıyla birlikte gömülüdür; tıklayınca tarayıcıda açılır.


DOSYA YAPISI
------------
  ClearFast.py           Uygulama penceresi ve sayfalar
  cf_core.py             Temizlik hedefleri, tarama, silme, sistem bilgisi
  cf_metrics.py          Canlı performans ve donanım sağlığı ölçümleri
  cf_ui.py               Tasarım sistemi (renk, tipografi, bileşenler)
  cf_raster.py           Kenar yumuşatmalı PNG/ICO üretimi (saf stdlib)
  ClearFastSetup.py      Kurulum ve kaldırma programı
  tools\make_icon.py     assets\ClearFast.ico üretir
  tools\_smoke.py        Arayüzü açıp hata var mı diye bakan hızlı sınama
  tools\_shot.py         Pencere ekran görüntüsü alan geliştirme aracı
  ClearFast.spec         PyInstaller yapılandırması (uygulama)
  ClearFastSetup.spec    PyInstaller yapılandırması (kurulum)
  installer\             Sürüm kaynak dosyaları
