@echo off
REM Forward all args to the Python wrapper using the Python launcher.
REM py.exe is the Windows Python Launcher and handles spaces in paths correctly.
py "C:\Coding Projects\Voxarah\tauri-app\src-tauri\rust-ld.py" %*
