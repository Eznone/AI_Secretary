"""Platform-aware data directory and file-permission helpers.

All platform branching lives here so the rest of the codebase stays clean.
Import APP_DATA_DIR, ensure_data_dir(), and secure_file() from this module
rather than writing any platform checks elsewhere.

Data directory per OS:
  Windows : %LOCALAPPDATA%\\secretary   (e.g. C:\\Users\\you\\AppData\\Local\\secretary)
  macOS   : ~/Library/Application Support/secretary
  Linux   : ~/.local/share/secretary   (XDG Base Directory spec)
"""

import os
import stat
import sys
from pathlib import Path

from platformdirs import user_data_path


def _resolve_data_dir() -> Path:
    # platformdirs handles the OS branching. Using "secretary" for both the
    # app name and author keeps the folder name simple on Windows (no vendor
    # subdirectory like "AI Secretary\secretary").
    return user_data_path("secretary", "secretary")


# Resolved once at import time — callers always get the same stable Path.
APP_DATA_DIR: Path = _resolve_data_dir()


def ensure_data_dir() -> Path:
    """Create the app data directory if it does not exist, then return it."""
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return APP_DATA_DIR


def get_local_timezone() -> str:
    """Return the IANA timezone name for the current system (e.g. 'Europe/Madrid').

    Tries three sources in order, falling back to UTC if none succeed.
    Works on Linux, macOS, and WSL2 (which inherits the Windows timezone).
    """
    # 1. TZ environment variable (highest priority — explicit override)
    tz = os.environ.get("TZ", "").strip()
    if tz:
        return tz

    # 2. /etc/timezone — Debian/Ubuntu/WSL2
    try:
        tz = Path("/etc/timezone").read_text().strip()
        if tz:
            return tz
    except OSError:
        pass

    # 3. /etc/localtime symlink target — RHEL/macOS/Alpine
    #    Resolves to something like /usr/share/zoneinfo/Europe/Madrid
    try:
        target = Path("/etc/localtime").resolve()
        parts = target.parts
        if "zoneinfo" in parts:
            idx = parts.index("zoneinfo")
            tz = "/".join(parts[idx + 1:])
            if tz:
                return tz
    except OSError:
        pass

    return "UTC"


def secure_file(path: Path) -> None:
    """Restrict a file to owner-only read/write (Unix mode 600).

    On Windows this is a deliberate no-op: Path.chmod() does not enforce
    Unix permission bits on NTFS. The primary secret store on Windows is
    the Windows Credential Manager, which handles access control itself.
    """
    if sys.platform != "win32":
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
