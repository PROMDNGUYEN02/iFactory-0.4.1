# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src\\iFactory\\__main__.py'],
    pathex=['C:\\python\\iFactory 0.4.1\\src'],
    binaries=[],
    datas=[('C:\\python\\iFactory 0.4.1\\data', 'data'), ('C:\\python\\iFactory 0.4.1\\logs', 'logs'), ('C:\\python\\iFactory 0.4.1\\src\\iFactory\\presentation\\resources', 'iFactory\\presentation\\resources')],
    hiddenimports=["aiosqlite"],
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
    [],
    exclude_binaries=True,
    name='iFactory',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:\\python\\iFactory 0.4.1\\src\\iFactory\\presentation\\resources\\icon\\icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='iFactory',
)
