"""
Voxarah — Main Entry Point
Run this file to launch the application.
"""
import sys
import os

# Tell Windows this process handles DPI itself — prevents bitmap upscaling
# that makes every pixel look blurry on high-DPI / scaled displays.
if sys.platform == "win32":
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)   # Per-Monitor v1 (Win 8.1+)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()    # System-DPI fallback (Win Vista+)
        except Exception:
            pass

# Ensure local imports work when frozen as .exe
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, BASE_DIR)

from ui.app import AudioFlowApp

if __name__ == "__main__":
    app = AudioFlowApp()
    app.mainloop()
