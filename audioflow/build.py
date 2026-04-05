"""
Voxarah — Build Script
Run this to produce the Windows .exe:
    python build.py
Requires: pip install pyinstaller
"""

import os
import subprocess
import sys

APP_NAME = "Voxarah"
MAIN     = "main.py"
ICON     = "assets/icon.ico"   # optional — create or remove this line

def build():
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        f"--name={APP_NAME}",
        "--add-data=coaching;coaching",
        "--add-data=core;core",
        "--add-data=ui;ui",
    ]

    # Add icon if it exists
    if os.path.exists(ICON):
        cmd += [f"--icon={ICON}"]

    cmd.append(MAIN)

    print("Building Voxarah .exe …")
    print(" ".join(cmd))
    result = subprocess.run(cmd, cwd=os.path.dirname(os.path.abspath(__file__)))

    if result.returncode == 0:
        print("\n✅ Build complete!")
        print(f"   Output: dist/{APP_NAME}.exe")
    else:
        print("\n❌ Build failed. Check output above.")

if __name__ == "__main__":
    build()
