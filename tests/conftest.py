"""Default to headless GUI tests; explicitly select xcb/wayland for WSLg."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
