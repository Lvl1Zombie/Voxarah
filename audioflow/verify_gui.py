"""
Voxarah — GUI Verification Script
Launches the app by PID, waits for render, screenshots it, saves crops.
Run from audioflow/:  python verify_gui.py
"""

import subprocess, sys, time, ctypes, ctypes.wintypes, os

SCREENSHOT_PATH  = os.path.join(os.path.dirname(__file__), "verify_screenshot.png")
STATUSBAR_PATH   = os.path.join(os.path.dirname(__file__), "verify_statusbar.png")
WAIT_SECONDS     = 6


def _find_window_by_pid(pid):
    GetWindowText         = ctypes.windll.user32.GetWindowTextW
    GetWindowTextLen      = ctypes.windll.user32.GetWindowTextLengthW
    IsWindowVisible       = ctypes.windll.user32.IsWindowVisible
    GetWindowThreadProcessId = ctypes.windll.user32.GetWindowThreadProcessId

    found = []

    def enum_cb(hwnd, _):
        if not IsWindowVisible(hwnd):
            return True
        p = ctypes.wintypes.DWORD()
        GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value != pid:
            return True
        l = GetWindowTextLen(hwnd)
        if not l:
            return True
        buf = ctypes.create_unicode_buffer(l + 1)
        GetWindowText(hwnd, buf, l + 1)
        if "Voxarah" in buf.value:
            found.append(hwnd)
            return False
        return True

    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    ctypes.windll.user32.EnumWindows(CB(enum_cb), 0)
    return found[0] if found else None


def _capture_hwnd(hwnd):
    import win32gui, win32ui
    from PIL import Image

    rect = ctypes.wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w = rect.right  - rect.left
    h = rect.bottom - rect.top

    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc  = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    bmp     = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(mfc_dc, w, h)
    save_dc.SelectObject(bmp)
    ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2)

    bi  = bmp.GetInfo()
    bs  = bmp.GetBitmapBits(True)
    img = Image.frombuffer("RGB", (bi["bmWidth"], bi["bmHeight"]),
                           bs, "raw", "BGRX", 0, 1)

    win32gui.DeleteObject(bmp.GetHandle())
    save_dc.DeleteDC()
    mfc_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwnd_dc)
    return img, w, h


def main():
    print("Launching Voxarah...")
    proc = subprocess.Popen([sys.executable, "-B", "main.py"],
                            cwd=os.path.dirname(__file__))
    print(f"PID: {proc.pid} — waiting {WAIT_SECONDS}s for render...")
    time.sleep(WAIT_SECONDS)

    hwnd = _find_window_by_pid(proc.pid)
    if not hwnd:
        print("ERROR: Voxarah window not found for this PID")
        proc.terminate()
        return

    ctypes.windll.user32.ShowWindow(hwnd, 9)       # SW_RESTORE
    ctypes.windll.user32.BringWindowToTop(hwnd)
    time.sleep(0.8)

    img, w, h = _capture_hwnd(hwnd)
    img.save(SCREENSHOT_PATH)
    print(f"Full screenshot: {SCREENSHOT_PATH}  ({w}x{h})")

    # Status bar crop (bottom 50px, 2x zoom)
    bar = img.crop((0, h - 50, w, h)).resize((w * 2, 100))
    bar.save(STATUSBAR_PATH)
    print(f"Status bar crop: {STATUSBAR_PATH}")

    print("Closing Voxarah...")
    proc.terminate()
    proc.wait(timeout=5)
    print("Done.")


if __name__ == "__main__":
    main()
