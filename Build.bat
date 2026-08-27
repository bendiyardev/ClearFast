@echo off
setlocal
cd /d "%~dp0"
title ClearFast - Derle

call :findpy
if not defined PY goto :nopython

echo.
echo === ClearFast derleniyor ===
echo.
echo [1/3] Uygulama simgesi uretiliyor...
%PY% tools\make_icon.py
if errorlevel 1 goto :error

echo [2/3] PyInstaller denetleniyor...
%PY% -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
    echo       PyInstaller kuruluyor...
    %PY% -m pip install --upgrade pyinstaller
    if errorlevel 1 goto :error
)

echo [3/3] Tek klasorlu surum derleniyor...
%PY% -m PyInstaller --noconfirm --clean ClearFast.spec
if errorlevel 1 goto :error

echo.
echo Hazir: dist\ClearFast\ClearFast.exe
echo.
echo   ClearFast.exe              uygulamayi acar
echo   ClearFast.exe --setup      bu bilgisayara kurar
echo   ClearFast.exe --uninstall  kaldirir
echo.
echo Dagitim ZIP'i icin: %PY% tools\make_release.py
echo.
pause
exit /b 0

:findpy
where py >nul 2>nul
if %errorlevel%==0 (
    set "PY=py -3"
    exit /b 0
)
where python >nul 2>nul
if %errorlevel%==0 (
    set "PY=python"
    exit /b 0
)
exit /b 1

:nopython
echo.
echo Python 3 bulunamadi. https://www.python.org/downloads/ adresinden kurun
echo ve kurulum sirasinda "Add python.exe to PATH" secenegini isaretleyin.
echo.
pause
exit /b 1

:error
echo.
echo Islem sirasinda hata olustu. Yukaridaki mesaji kontrol edin.
echo.
pause
exit /b 1
