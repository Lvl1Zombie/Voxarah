"""
Voxarah — Auto-update via GitHub Releases
Checks the latest GitHub release for a newer version and installs it.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import urllib.error

GITHUB_REPO        = "Lvl1Zombie/Voxarah"
GITHUB_API_URL     = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases"


class UpdateError(Exception):
    pass


def parse_version(version: str):
    # Strip leading 'v' (e.g. "v2.1" -> "2.1")
    version = version.lstrip("v").lstrip("V")
    parts = []
    for part in version.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(part)
    return tuple(parts)


def version_newer(current: str, remote: str) -> bool:
    return parse_version(remote) > parse_version(current)


class Updater:
    def __init__(self, current_version: str, manifest_url: str = None, app_name: str = "Voxarah"):
        self.current_version = current_version
        self.app_name = app_name

    def fetch_manifest(self, timeout: int = 12) -> dict:
        """Fetch the latest GitHub release and return a normalised manifest dict."""
        try:
            req = urllib.request.Request(
                GITHUB_API_URL,
                headers={
                    "User-Agent": f"Voxarah/{self.current_version}",
                    "Accept":     "application/vnd.github+json",
                }
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read().decode("utf-8")
            release = json.loads(data)
        except urllib.error.URLError as e:
            raise UpdateError(f"Could not reach GitHub: {e}")
        except Exception as e:
            raise UpdateError(f"Invalid response from GitHub: {e}")

        tag     = release.get("tag_name", "")
        version = tag.lstrip("vV") or release.get("name", "")
        notes   = release.get("body", "")

        # Find the .exe asset
        exe_url = None
        for asset in release.get("assets", []):
            if asset.get("name", "").lower().endswith(".exe"):
                exe_url = asset.get("browser_download_url")
                break

        return {
            "version": version,
            "url":     exe_url,
            "notes":   notes,
            "tag":     tag,
        }

    def check_for_update(self) -> dict:
        manifest = self.fetch_manifest()
        version  = manifest.get("version")
        if not version:
            raise UpdateError("Could not determine release version from GitHub.")
        return {
            "available": version_newer(self.current_version, version),
            "version":   version,
            "notes":     manifest.get("notes", ""),
            "url":       manifest.get("url"),
            "tag":       manifest.get("tag", ""),
        }

    def download_update(self, url: str) -> str:
        if not url:
            raise UpdateError("No download URL found in this release. Check the GitHub releases page.")
        fd, path = tempfile.mkstemp(suffix=".exe")
        os.close(fd)
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": f"Voxarah/{self.current_version}"}
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                with open(path, "wb") as out:
                    shutil.copyfileobj(resp, out)
            return path
        except Exception as e:
            if os.path.exists(path):
                os.remove(path)
            raise UpdateError(f"Download failed: {e}")

    def install_update(self, downloaded_exe: str):
        current_exe = self.current_executable_path()
        if not current_exe or not os.path.exists(current_exe):
            raise UpdateError("Current executable path is invalid.")

        target_dir = os.path.dirname(current_exe)
        new_exe    = os.path.join(target_dir, f"{self.app_name}.new.exe")
        shutil.move(downloaded_exe, new_exe)

        batch_path = os.path.join(tempfile.gettempdir(), f"{self.app_name}_update.bat")
        with open(batch_path, "w", encoding="utf-8") as bat:
            bat.write(self._update_batch_contents(current_exe, new_exe))

        subprocess.Popen(["cmd", "/c", "start", "", batch_path], shell=False)

    def current_executable_path(self) -> str:
        return sys.executable if getattr(sys, "frozen", False) else None

    def _update_batch_contents(self, target_exe: str, new_exe: str) -> str:
        target_exe = target_exe.replace("/", "\\")
        new_exe    = new_exe.replace("/", "\\")
        base       = os.path.basename(target_exe)
        return f"""@echo off
:wait
 tasklist /fi "imagename eq {base}" | find /i "{base}" >nul
 if not errorlevel 1 (
     timeout /t 1 /nobreak >nul
     goto wait
 )
 if exist "{target_exe}" del /f /q "{target_exe}"
 move /y "{new_exe}" "{target_exe}"
 start "" "{target_exe}"
 del /f /q "%~f0"
"""
