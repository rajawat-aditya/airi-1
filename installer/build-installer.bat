@echo off
setlocal
echo ============================================
echo  Airi Installer Builder (Inno Setup)
echo ============================================
echo.

:: Find Inno Setup compiler
set ISCC=
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
if exist "C:\Program Files\Inno Setup 6\ISCC.exe"       set ISCC=C:\Program Files\Inno Setup 6\ISCC.exe

if "%ISCC%"=="" (
    echo ERROR: Inno Setup 6 not found.
    echo Download from: https://jrsoftware.org/isdl.php
    pause & exit /b 1
)

:: Verify build output exists
if not exist "%~dp0..\build\win-unpacked\Airi.exe" (
    echo ERROR: build\win-unpacked\Airi.exe not found.
    echo Run electron-builder first: npm run build:electron
    pause & exit /b 1
)

echo Building installer...
echo.
"%ISCC%" "%~dp0airi-installer.iss"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================
    echo  Done: build\Airi-Setup-0.1.0.exe
    echo.
    echo  Microsoft Store silent install command:
    echo    Airi-Setup-0.1.0.exe /VERYSILENT /SUPPRESSMSGBOXES
    echo  Silent uninstall:
    echo    "%%ProgramFiles%%\Airi\Uninstall.exe" /VERYSILENT /SUPPRESSMSGBOXES
    echo ============================================
) else (
    echo.
    echo Build failed. Check output above.
)

pause
