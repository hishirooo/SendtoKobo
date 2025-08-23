# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['SendtoKobo.py'],
    pathex=[],
    binaries=[('kepubify-windows-64bit.exe', '.')],
    datas=[('icons', 'icons')],
    hiddenimports=['PyQt6.QtSvgWidgets'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SendToKobo',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icons\\file_1119057.ico'],
)
