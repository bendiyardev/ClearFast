@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    start "" pyw -3 ClearFast.py
    exit /b
)
where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw ClearFast.py
    exit /b
)
echo.
echo ClearFast'i calistirmak icin Python 3 bulunamadi.
echo Python kurduktan sonra bu dosyaya tekrar cift tiklayin.
echo Alternatif olarak Build_Portable_EXE.bat ile tek dosyalik surumu uretebilirsiniz.
echo.
pause
