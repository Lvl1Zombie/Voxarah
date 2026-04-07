"""
Voxarah — Build Script
Produces a standalone Windows .exe via PyInstaller.

    cd audioflow
    python build.py
"""

import os
import subprocess
import sys

APP_NAME = "Voxarah"
MAIN     = "main.py"
ICON     = "assets/icon.ico"

def build():
    base = os.path.dirname(os.path.abspath(__file__))

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        f"--name={APP_NAME}",

        # Source packages + assets
        "--add-data=coaching;coaching",
        "--add-data=core;core",
        "--add-data=ui;ui",
        "--add-data=assets;assets",

        # pyttsx3 needs its driver sub-package collected explicitly
        "--hidden-import=pyttsx3.drivers",
        "--hidden-import=pyttsx3.drivers.sapi5",
        "--collect-submodules=pyttsx3",

        # Windows COM / win32 deps used by pyttsx3 SAPI5 driver
        "--hidden-import=win32com",
        "--hidden-import=win32com.client",
        "--hidden-import=comtypes",
        "--hidden-import=comtypes.client",
        "--collect-submodules=win32com",
        "--collect-submodules=comtypes",
    ]

    # Bundle ffmpeg.exe if present
    ffmpeg = os.path.join(base, "samples", "ffmpeg.exe")
    if os.path.exists(ffmpeg):
        cmd.append("--add-binary=samples/ffmpeg.exe;samples")
        print("  + Bundling samples/ffmpeg.exe")
    else:
        print("  ! samples/ffmpeg.exe not found — MP3/M4A support will be unavailable in the build")

    if os.path.exists(os.path.join(base, ICON)):
        cmd.append(f"--icon={ICON}")

    cmd.append(MAIN)

    print(f"Building {APP_NAME}.exe …")
    result = subprocess.run(cmd, cwd=base)

    if result.returncode == 0:
        print(f"\n  Build complete  ->  dist/{APP_NAME}.exe")
    else:
        print("\n  Build failed — check output above.")

if __name__ == "__main__":
    build()
