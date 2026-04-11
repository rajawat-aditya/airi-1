@echo off
:: ─────────────────────────────────────────────────────────────────────────────
:: build.bat  —  Bundle agent.py into dist\airi-agent\
:: Run from repo root:  agent-server\build.bat
:: ─────────────────────────────────────────────────────────────────────────────

setlocal

set REPO_ROOT=%~dp0..
set AGENT_DIR=%~dp0

:: Use whichever python is active in the current environment
set PYTHON=python

echo [1/3] Installing PyInstaller...
%PYTHON% -m pip install --quiet pyinstaller
if errorlevel 1 (
    echo [FAIL] pip install pyinstaller failed.
    exit /b 1
)

echo [2/3] Running PyInstaller...
%PYTHON% -m PyInstaller --clean --noconfirm "%AGENT_DIR%agent.spec" ^
    --distpath "%REPO_ROOT%\dist" ^
    --workpath "%REPO_ROOT%\build"

if errorlevel 1 (
    echo [FAIL] PyInstaller failed.
    exit /b 1
)

echo [3/3] Copying runtime data files...
:: .mem0_db is created at runtime — just ensure the folder exists in dist
if not exist "%REPO_ROOT%\dist\airi-agent\.mem0_db" (
    mkdir "%REPO_ROOT%\dist\airi-agent\.mem0_db"
)
:: user_stuff folder
if not exist "%REPO_ROOT%\dist\airi-agent\user_stuff" (
    mkdir "%REPO_ROOT%\dist\airi-agent\user_stuff"
)

echo.
echo Done. Bundle is at: dist\airi-agent\airi-agent.exe
endlocal
