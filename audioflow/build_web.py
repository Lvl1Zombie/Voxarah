"""
Voxarah — Web Backend Build Script
Produces a standalone voxarah-backend.exe via PyInstaller for the Tauri sidecar.

    cd audioflow
    python build_web.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

NAME   = "voxarah-backend"
MAIN   = "web_main.py"
BASE   = Path(__file__).parent

def build():
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--noconsole",
        f"--name={NAME}",

        # Source packages
        "--add-data=coaching;coaching",
        "--add-data=core;core",
        "--add-data=templates;templates",
        "--add-data=static;static",

        # FastAPI / uvicorn hidden imports
        "--hidden-import=uvicorn.logging",
        "--hidden-import=uvicorn.loops",
        "--hidden-import=uvicorn.loops.auto",
        "--hidden-import=uvicorn.protocols",
        "--hidden-import=uvicorn.protocols.http",
        "--hidden-import=uvicorn.protocols.http.auto",
        "--hidden-import=uvicorn.protocols.websockets",
        "--hidden-import=uvicorn.protocols.websockets.auto",
        "--hidden-import=uvicorn.lifespan",
        "--hidden-import=uvicorn.lifespan.on",

        # Recording
        "--hidden-import=sounddevice",
        "--collect-submodules=sounddevice",

        # AI coach deps
        "--hidden-import=pyttsx3.drivers",
        "--hidden-import=pyttsx3.drivers.sapi5",
        "--collect-submodules=pyttsx3",
        "--hidden-import=win32com",
        "--hidden-import=win32com.client",
        "--hidden-import=comtypes",
        "--hidden-import=comtypes.client",
        "--collect-submodules=win32com",
        "--collect-submodules=comtypes",
    ]

    # Bundle ffmpeg if present
    ffmpeg = BASE / "samples" / "ffmpeg.exe"
    if ffmpeg.exists():
        cmd.append(f"--add-binary=samples/ffmpeg.exe;samples")
        print("  + Bundling samples/ffmpeg.exe")
    else:
        print("  ! samples/ffmpeg.exe not found — MP3/M4A support unavailable")

    cmd.append(MAIN)

    print(f"Building {NAME}.exe …")
    result = subprocess.run(cmd, cwd=BASE)

    if result.returncode != 0:
        print("\n  Build FAILED — check output above.")
        sys.exit(1)

    out = BASE / "dist" / f"{NAME}.exe"
    print(f"\n  Build complete -> {out}")

    # Copy into Tauri binaries folder
    tauri_bins = BASE.parent / "tauri-app" / "src-tauri" / "binaries"
    if tauri_bins.exists():
        for target in [
            "voxarah-backend-x86_64-pc-windows-msvc.exe",
            "voxarah-backend-x86_64-pc-windows-gnu.exe",
        ]:
            dest = tauri_bins / target
            shutil.copy2(out, dest)
            print(f"  Copied -> {dest}")
    else:
        print(f"  ! Tauri binaries folder not found: {tauri_bins}")

if __name__ == "__main__":
    build()
