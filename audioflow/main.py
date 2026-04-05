"""
Voxarah — Main Entry Point
Run this file to launch the application.
"""
import sys
import os

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
