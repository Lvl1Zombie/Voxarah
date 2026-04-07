# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['pyttsx3.drivers', 'pyttsx3.drivers.sapi5', 'win32com', 'win32com.client', 'comtypes', 'comtypes.client']
hiddenimports += collect_submodules('pyttsx3')
hiddenimports += collect_submodules('win32com')
hiddenimports += collect_submodules('comtypes')


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[('samples/ffmpeg.exe', 'samples')],
    datas=[('coaching', 'coaching'), ('core', 'core'), ('ui', 'ui')],
    hiddenimports=hiddenimports,
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
    name='Voxarah',
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
    icon=['assets\\icon.ico'],
)
