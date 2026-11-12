"""One-shot window metadata probe; uses an empty temporary database, never user data."""

import argparse
import ctypes
import json
import platform
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import PySide6
from PySide6.QtCore import qVersion
from PySide6.QtWidgets import QApplication

from cyberforge.application.accounts import AccountService
from cyberforge.persistence.database import Database
from cyberforge.ui.shell import MainWindow
from cyberforge.ui.theme import apply_theme


def native_minimum(window: MainWindow) -> list[int] | None:
    """Query Windows tracking limits; raw physical pixels, not a mouse test."""
    if sys.platform != "win32" or QApplication.platformName() != "windows":
        return None
    from ctypes import wintypes

    class MinMaxInfo(ctypes.Structure):
        _fields_ = [
            (name, wintypes.POINT)
            for name in (
                "reserved",
                "max_size",
                "max_position",
                "min_track",
                "max_track",
            )
        ]

    send = ctypes.WinDLL("user32", use_last_error=True).SendMessageW
    send.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    send.restype = ctypes.c_ssize_t
    info = MinMaxInfo()
    send(int(window.winId()), 0x0024, 0, ctypes.addressof(info))
    return [info.min_track.x, info.min_track.y]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    app = QApplication([sys.argv[0]])
    apply_theme(app)
    with TemporaryDirectory(prefix="cyberforge-window-") as temporary:
        database = Database(Path(temporary) / "probe.sqlite3")
        try:
            database.upgrade()
            window = MainWindow(AccountService(database))
            try:
                window.show()
                app.processEvents()
                report = {
                    "python": platform.python_version(),
                    "interpreter": sys.executable,
                    "platform": sys.platform,
                    "pyside": PySide6.__version__,
                    "qt": qVersion(),
                    "backend": app.platformName(),
                    "available_geometry": window.screen().availableGeometry().getRect(),
                    "device_pixel_ratio": window.devicePixelRatioF(),
                    "minimum_size": window.minimumSize().toTuple(),
                    "minimum_size_hint": window.minimumSizeHint().toTuple(),
                    "initial_geometry": window.geometry().getRect(),
                    "initial_frame": window.frameGeometry().getRect(),
                    "windows_min_track_physical": native_minimum(window),
                }
                window.resize(1, 1)
                app.processEvents()
                report["programmatic_shrink_size"] = window.size().toTuple()
                report["programmatic_minimum_enforced"] = (
                    window.width() >= window.minimumWidth()
                    and window.height() >= window.minimumHeight()
                )
            finally:
                window.close()
                app.processEvents()
        finally:
            database.close()
    serialized = json.dumps(report, ensure_ascii=True, indent=2)
    print(serialized)
    if args.output:
        # Never overwrite an existing report or another owner's file.
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(serialized + "\n")
    return 0 if report["programmatic_minimum_enforced"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
