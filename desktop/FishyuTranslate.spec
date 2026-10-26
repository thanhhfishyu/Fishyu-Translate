# -*- mode: python ; coding: utf-8 -*-
import os
import shutil
import sys
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs, collect_submodules

IS_WIN = sys.platform == "win32"

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
LICENSES = [os.path.join(ROOT, "LICENSE"), os.path.join(ROOT, "THIRD_PARTY_NOTICES.md")]
datas = [("assets", "assets")] + [(f, "licenses") for f in LICENSES]
binaries = []
hiddenimports = ["PySide6.QtSvg", "PySide6.QtNetwork"]
for pkg in ("rapidocr", "ctranslate2"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h
binaries += collect_dynamic_libs("onnxruntime")
binaries += collect_dynamic_libs("sentencepiece")
if not IS_WIN:
    hiddenimports += collect_submodules("Xlib") + collect_submodules("jeepney")

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "torch", "transformers", "PySide6.QtWebEngineCore",
              "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore", "PySide6.QtQuick", "PySide6.QtQml",
              "PySide6.QtMultimedia", "PySide6.QtPdf", "pytest", "rapidocr.inference_engine.torch",
              "rapidocr.inference_engine.paddle", "rapidocr.inference_engine.openvino",
              "rapidocr.inference_engine.tensorrt", "rapidocr.inference_engine.mnn"],
    noarchive=False,
)
if not IS_WIN:
    _drop = ("libqgtk3", "libgtk-3", "libgdk-3", "libatk-", "libatk-bridge", "libcairo-gobject", "libgdk_pixbuf",
             "libpangocairo", "libpangoft2", "libpango-", "libepoxy", "libatspi")
    a.binaries = [b for b in a.binaries if not any(x in b[0] for x in _drop)]

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FishyuTranslate",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon="assets/app_icon.ico" if IS_WIN else None,
    version="version_info.txt" if IS_WIN else None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="FishyuTranslate")
for f in LICENSES:
    name = "LICENSE.txt" if f.endswith("LICENSE") else os.path.basename(f)
    shutil.copy(f, os.path.join(DISTPATH, "FishyuTranslate", name))
