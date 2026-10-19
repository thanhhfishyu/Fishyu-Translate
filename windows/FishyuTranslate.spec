# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs

datas = [("assets", "assets")]
binaries = []
hiddenimports = ["PySide6.QtSvg", "PySide6.QtNetwork"]
for pkg in ("rapidocr", "ctranslate2"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h
binaries += collect_dynamic_libs("onnxruntime")
binaries += collect_dynamic_libs("sentencepiece")

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "torch", "transformers", "PySide6.QtWebEngineCore",
              "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore", "PySide6.QtQuick", "PySide6.QtQml",
              "PySide6.QtMultimedia", "PySide6.QtPdf", "pytest"],
    noarchive=False,
)
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
    icon="assets/app_icon.ico",
    version="version_info.txt",
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="FishyuTranslate")
