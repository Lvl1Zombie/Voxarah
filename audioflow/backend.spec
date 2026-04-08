# PyInstaller spec — builds audioflow/web_main.py into a single .exe
# Output: dist/voxarah-backend.exe  (renamed & copied to tauri-app by build_tauri.py)
#
# Build: pyinstaller backend.spec  (run from audioflow/)

import sys
from pathlib import Path

block_cipher = None
HERE = Path(SPECPATH)

a = Analysis(
    [str(HERE / 'web_main.py')],
    pathex=[str(HERE)],
    binaries=[],
    datas=[
        (str(HERE / 'static'),   'static'),
        (str(HERE / 'templates'), 'templates'),
        (str(HERE / 'coaching'),  'coaching'),
        (str(HERE / 'core'),      'core'),
    ],
    hiddenimports=[
        # uvicorn internals
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.loops.asyncio',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.protocols.websockets.websockets_impl',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        # starlette / fastapi internals
        'starlette.routing',
        'starlette.middleware',
        'starlette.middleware.cors',
        'starlette.staticfiles',
        # numpy / scipy / librosa
        'numpy',
        'scipy.signal',
        'librosa',
        'librosa.core',
        'soundfile',
        'audioread',
        'sklearn.utils._cython_blas',
        'sklearn.neighbors._partition_nodes',
        # requests / urllib for feedback webhook
        'urllib.request',
        'http.client',
        # pyttsx3 (TTS for AI coach)
        'pyttsx3',
        'pyttsx3.drivers',
        'pyttsx3.drivers.sapi5',
        # sounddevice (recorder)
        'sounddevice',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'PyQt5', 'wx', 'matplotlib'],
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
    name='voxarah-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,           # Tauri captures stderr; needed for crash diagnostics
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
