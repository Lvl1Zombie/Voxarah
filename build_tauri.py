#!/usr/bin/env python3
"""
build_tauri.py — Voxarah desktop build script
==============================================
Orchestrates the full build pipeline:

  1. PyInstaller  — packages the FastAPI backend into a single .exe
  2. prepare-frontend — copies HTML/CSS/JS into tauri-app/frontend/
  3. Tauri build  — compiles the Rust shell + bundles everything into an .msi

Usage (from repo root):
    python build_tauri.py

Requirements:
    pip install pyinstaller
    rustup (Rust toolchain) — https://rustup.rs
    npm install  (inside tauri-app/)  — @tauri-apps/cli

Environment:
    Rust bin dir must be on PATH.  If rustup installed Rust but didn't modify
    PATH, run:  source "$HOME/.cargo/env"  (or restart terminal).
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT       = Path(__file__).parent
AUDIOFLOW  = ROOT / "audioflow"
TAURI_APP  = ROOT / "tauri-app"
BINARIES   = TAURI_APP / "src-tauri" / "binaries"

# Tauri bundles the sidecar under the MSVC triple name (CLI default on Windows).
# The Rust build script also checks the GNU triple name.  Copy under both.
_TRIPLES = [
    "x86_64-pc-windows-msvc",
    "x86_64-pc-windows-gnu",
]


def run(cmd, cwd=None, env=None):
    """Run a command and stream output. Raises on non-zero exit."""
    merged_env = {**os.environ, **(env or {})}
    # Ensure Cargo bin and Node/npm are on PATH
    extra_paths = [
        str(Path.home() / ".cargo" / "bin"),
        r"C:\Program Files\nodejs",
    ]
    for p in extra_paths:
        if p not in merged_env.get("PATH", ""):
            merged_env["PATH"] = p + os.pathsep + merged_env.get("PATH", "")
    print(f"\n>  {' '.join(str(c) for c in cmd)}")
    r = subprocess.run(cmd, cwd=cwd or ROOT, env=merged_env, shell=True)
    if r.returncode != 0:
        sys.exit(f"Command failed with exit code {r.returncode}")


def step_build_backend():
    print("\n-- Step 1: Build Python backend (PyInstaller) --")
    run(
        [sys.executable, "-m", "PyInstaller", "--clean", "backend.spec"],
        cwd=AUDIOFLOW,
    )
    src = AUDIOFLOW / "dist" / "voxarah-backend.exe"
    if not src.exists():
        sys.exit(f"PyInstaller output not found: {src}")
    BINARIES.mkdir(parents=True, exist_ok=True)
    for triple in _TRIPLES:
        dst = BINARIES / f"voxarah-backend-{triple}.exe"
        shutil.copy2(src, dst)
        print(f"   Copied to {dst}")


def step_install_npm():
    print("\n-- Step 2: Install npm dependencies --")
    run(["npm", "install"], cwd=TAURI_APP)


def step_tauri_build():
    print("\n-- Step 3: Tauri build (MSI) --")
    run(["npm", "run", "build"], cwd=TAURI_APP)


def main():
    print("=" * 60)
    print("  Voxarah - Desktop Build")
    print("=" * 60)

    step_build_backend()
    step_install_npm()
    step_tauri_build()

    msi_glob = list((TAURI_APP / "src-tauri" / "target" / "release" / "bundle" / "msi").glob("*.msi"))
    if msi_glob:
        print(f"\n[OK]  Installer ready: {msi_glob[0]}")
    else:
        print("\n[OK]  Build complete (check tauri-app/src-tauri/target/release/bundle/)")


if __name__ == "__main__":
    main()
