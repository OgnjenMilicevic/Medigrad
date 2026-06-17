# -*- mode: python ; coding: utf-8 -*-
"""
Datagrad.spec — cross-platform PyInstaller build spec.

Works on Windows, Linux, and macOS. The same spec is used by the GitHub
Actions workflow on every platform; PyInstaller picks the right binary format
automatically (.exe on Windows, a Unix executable on Linux, and — because
BUILD_MACOS_APP below triggers a BUNDLE — a .app on macOS).

Build locally:
    pyinstaller Datagrad.spec --noconfirm

Output:
    Windows / Linux : dist/Datagrad/            (one-folder app)
    macOS           : dist/Datagrad.app         (clickable app bundle)
"""

import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

IS_MAC = sys.platform == "darwin"

block_cipher = None

# --- Data files (UI + content shipped alongside the code) ------------------
datas = [
    ("index.html", "."),
    ("style.css", "."),
    ("js", "js"),
    ("help_content", "help_content"),
    ("assets", "assets"),
    ("examples", "examples"),
    ("vendor", "vendor"),
    ("mfub", "mfub"),
]

# --- Hidden imports + bundled data for tricky packages ---------------------
hiddenimports = []
hiddenimports += collect_submodules("scipy")
hiddenimports += collect_submodules("pandas")
hiddenimports += collect_submodules("plotly")
hiddenimports += collect_submodules("webview")     # pywebview
hiddenimports += ["waitress", "openpyxl", "markdown", "pyreadstat"]

for pkg in ("scipy", "pandas", "plotly", "pyreadstat", "numpy"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    datas += pkg_datas
    hiddenimports += pkg_hidden

datas += collect_data_files("plotly")

a = Analysis(
    ["desktop_main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "statsmodels", "sklearn", "scikit_learn", "pingouin", "lightgbm",
        "miceforest", "semopy", "factor_analyzer", "matplotlib", "seaborn",
        "celery", "redis", "rq", "boto3", "botocore", "tkinter", "pytest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Icon: use a .ico on Windows, a .icns on macOS, if present.
import os
icon = None
if sys.platform == "win32" and os.path.exists("datagrad.ico"):
    icon = "datagrad.ico"
elif IS_MAC and os.path.exists("datagrad.icns"):
    icon = "datagrad.icns"

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Datagrad",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,            # UPX off: avoids antivirus false-positives + Mac codesign issues
    console=False,        # no terminal window
    icon=icon,
)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False, upx=False, upx_exclude=[], name="Datagrad",
)

if IS_MAC:
    app = BUNDLE(
        coll,
        name="Datagrad.app",
        icon=icon,
        bundle_identifier="rs.ac.bg.med.datagrad",
        info_plist={
            "CFBundleName": "Datagrad MFUB",
            "CFBundleDisplayName": "Datagrad MFUB Desktop",
            "CFBundleShortVersionString": "1.0",
            "CFBundleVersion": "1.0",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
        },
    )
