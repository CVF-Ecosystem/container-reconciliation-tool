# -*- mode: python ; coding: utf-8 -*-
# File: app_gui.spec
# PyInstaller spec file for Container Reconciliation Tool V5.7
# Build command: pyinstaller app_gui.spec --clean
# Single EXE output: dist/ContainerReconciliation_V5.7.exe

import sys
from pathlib import Path

block_cipher = None

# Project paths
PROJECT_DIR = Path(SPECPATH)
DATA_DIR = PROJECT_DIR / 'data'
LOCALES_DIR = PROJECT_DIR / 'locales'
CONFIG_FILES = [
    ('config.py', '.'),
    ('config_mappings.json', '.'),
    ('email_config.json', '.'),
]

# Data files to include
datas = [
    # Configuration files
    (str(PROJECT_DIR / 'config_mappings.json'), '.'),
    (str(PROJECT_DIR / 'email_config.json'), '.'),
    
    # Locales for multi-language support
    (str(LOCALES_DIR), 'locales'),
]

# Hidden imports that PyInstaller might miss
hiddenimports = [
    'pandas',
    'openpyxl',
    'xlsxwriter',
    'ttkbootstrap',
    'tkcalendar',
    'babel.numbers',
    'babel.dates',
    'pkg_resources.py2_warn',
    'encodings',
    # Core modules
    'core',
    'core.reconciliation_engine',
    'core.batch_processor',
    'core.duplicate_checker',
    'core.inventory_checker',
    'core.advanced_checker',
    'core.delta_checker',
    # Data modules
    'data',
    'data.data_loader',
    'data.data_transformer',
    'data.data_validator',
    # Report modules
    'reports',
    'reports.report_generator',
    'reports.email_sender',
    'reports.email_template_exporter',
    'reports.movement_summary',
    'reports.operator_analyzer',
    # Utils modules
    'utils',
    'utils.exceptions',
    'utils.validators',
    'utils.cache_utils',
    'utils.retry_utils',
    'utils.audit_trail',
    'utils.profiler',
    'utils.history_db',
    'utils.health_check',
    'utils.gui_translator',
    'utils.translation',
    'utils.file_comparator',
    # GUI modules
    'gui',
    'gui.dialogs',
    'gui.batch_dialog',
    'gui.compare_dialog',
    'gui.settings_dialog',
    'gui.appearance_dialog',
    'gui.export_dialog',
]

# Exclude unnecessary modules to reduce size
excludes = [
    'matplotlib',
    'scipy',
    'numpy.testing',
    'pytest',
    'streamlit',  # Web dashboard separate deployment
    'plotly',
    'fastapi',
    'uvicorn',
]

a = Analysis(
    ['app_gui.py'],
    pathex=[str(PROJECT_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ContainerReconciliation_V5.7',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window (GUI app)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here if available: 'assets/icon.ico'
    version=None,  # Remove version file requirement
)

# Alternative: Create folder distribution instead of single EXE
# Uncomment below for folder distribution (faster startup, easier debugging)
'''
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ContainerReconciliation_V5.7',
)
'''
