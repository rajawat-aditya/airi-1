# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for agent.py
Build: pyinstaller agent.spec  (run from repo root with venv active)
Output: dist/airi-agent/
"""

import os
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

block_cipher = None

# ── Collect data/binaries for heavy packages ──────────────────────────────────
datas   = []
binaries = []
hiddenimports = []

for pkg in [
    "qwen_agent",
    "mem0",
    "qdrant_client",
    "faster_whisper",
    "ctranslate2",
    "tokenizers",
    "transformers",
    "huggingface_hub",
    "tiktoken",
    "soundfile",
    "uvicorn",
    "fastapi",
    "starlette",
    "anyio",
    "httpx",
    "httpcore",
    "pydantic",
    "pydantic_core",
]:
    d, b, h = collect_all(pkg)
    datas    += d
    binaries += b
    hiddenimports += h

# ── Agent-server data files ───────────────────────────────────────────────────
agent_dir = os.path.abspath("agent-server")

datas += [
    (os.path.join(agent_dir, "settings.json"),       "."          ),
    (os.path.join(agent_dir, "installed_apps.json"), "."          ),
    (os.path.join(agent_dir, "flaui.py"),            "."          ),
    (os.path.join(agent_dir, "win.py"),              "."          ),
    # Skill markdown files
    (os.path.join(agent_dir, "ChromeNavigator.md"),  "."          ),
    (os.path.join(agent_dir, "FileManager.md"),      "."          ),
    (os.path.join(agent_dir, "WindowsAutomator.md"), "."          ),
]

# ── FlaUI native DLLs ─────────────────────────────────────────────────────────
flaui_deps = os.path.abspath("deps/flaui")
datas += [(flaui_deps, "deps/flaui")]

# ── Extra hidden imports ──────────────────────────────────────────────────────
hiddenimports += [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.main",
    "fastapi.routing",
    "starlette.routing",
    "starlette.middleware.cors",
    "multipart",
    "python_multipart",
    "clr",          # pythonnet
    "clr_loader",
    "pythonnet",
    "win32api",
    "win32con",
    "win32gui",
    "pynput",
    "pyperclip",
    "pyautogui",
    "PIL",
    "soundfile",
    "numpy",
    "scipy",
]

a = Analysis(
    [os.path.join(agent_dir, "agent.py")],
    pathex=[agent_dir],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "notebook", "jupyter", "IPython", "test", "tests"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="airi-agent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX breaks pythonnet/native DLLs
    console=True,       # keep console — it's a server process
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="airi-agent",
)
