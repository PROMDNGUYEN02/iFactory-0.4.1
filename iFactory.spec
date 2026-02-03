# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Đường dẫn project
PROJECT_ROOT = r'C:\python\iFactory 0.4.1'
SRC_PATH = os.path.join(PROJECT_ROOT, 'src')

# Hidden imports
hidden_imports = [
    # SQLAlchemy
    'sqlalchemy.dialects.mssql',
    'sqlalchemy.dialects.mssql.pyodbc',
    'sqlalchemy.dialects.sqlite',
    'sqlalchemy.dialects.sqlite.aiosqlite',
    'sqlalchemy.sql.default_comparator',
    'sqlalchemy.ext.asyncio',
    'sqlalchemy.orm',
    'sqlalchemy.pool',
    
    # Database drivers
    'pyodbc',
    'aioodbc',
    'aiosqlite',
    
    # Async
    'asyncio',
    'qasync',
    
    # Pydantic
    'pydantic',
    'pydantic.fields',
    'pydantic_settings',
    
    # PySide6
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtSvg',
    'PySide6.QtSvgWidgets',
]

# Collect all submodules
hidden_imports += collect_submodules('iFactory')
hidden_imports += collect_submodules('sqlalchemy')

# Data files
datas = [
    # Resources
    (
        os.path.join(SRC_PATH, 'iFactory', 'presentation', 'resources'),
        os.path.join('iFactory', 'presentation', 'resources')
    ),
    # Config
    (
        os.path.join(PROJECT_ROOT, 'data', 'config'),
        os.path.join('data', 'config')
    ),
    # Storage (SQLite)
    (
        os.path.join(PROJECT_ROOT, 'data', 'storage'),
        os.path.join('data', 'storage')
    ),
    # .env file
    (
        os.path.join(PROJECT_ROOT, '.env'),
        '.'
    ),
]

a = Analysis(
    [os.path.join(SRC_PATH, 'iFactory', '__main__.py')],
    pathex=[SRC_PATH],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'test', 'tests'],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, cipher=block_cipher)

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
    icon=[os.path.join(SRC_PATH, 'iFactory', 'presentation', 'resources', 'icon', 'icon.ico')],
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