# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_all

block_cipher = None

PROJECT_ROOT = r'C:\python\iFactory 0.4.1'
SRC_PATH = os.path.join(PROJECT_ROOT, 'src')

# Collect dependency-injector
di_datas, di_binaries, di_hiddenimports = collect_all('dependency_injector')

# Hidden imports - ĐÃ SỬA
hidden_imports = [
    # dependency-injector
    'dependency_injector',
    'dependency_injector.errors',
    'dependency_injector.providers',
    'dependency_injector.containers',
    'dependency_injector.wiring',
    
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

# Chỉ thêm nếu package đã cài
try:
    import structlog
    hidden_imports += [
        'structlog',
        'structlog.processors',
        'structlog.stdlib',
        'structlog.contextvars',
    ]
except ImportError:
    print("WARNING: structlog not installed, skipping...")

try:
    import orjson
    hidden_imports += ['orjson']
except ImportError:
    print("WARNING: orjson not installed, skipping...")

# Collect submodules
hidden_imports += collect_submodules('iFactory')
hidden_imports += collect_submodules('sqlalchemy')
hidden_imports += collect_submodules('dependency_injector')
hidden_imports += collect_submodules('pydantic')
hidden_imports += di_hiddenimports

# Data files
datas = [
    (
        os.path.join(SRC_PATH, 'iFactory', 'presentation', 'resources'),
        os.path.join('iFactory', 'presentation', 'resources')
    ),
    (
        os.path.join(PROJECT_ROOT, 'data', 'config'),
        os.path.join('data', 'config')
    ),
    (
        os.path.join(PROJECT_ROOT, 'data', 'storage'),
        os.path.join('data', 'storage')
    ),
    (
        os.path.join(PROJECT_ROOT, '.env'),
        '.'
    ),
]
datas += di_datas

# Binaries
binaries = []
binaries += di_binaries

a = Analysis(
    [os.path.join(SRC_PATH, 'iFactory', '__main__.py')],
    pathex=[SRC_PATH],
    binaries=binaries,
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
    console=False,  # ĐỂ TRUE ĐỂ DEBUG
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