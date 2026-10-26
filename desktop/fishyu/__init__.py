import sys

OS_NAME = "Windows" if sys.platform == "win32" else ("Linux" if sys.platform.startswith("linux") else "Desktop")
APP_NAME = f"Fishyu Translate for {OS_NAME}"
try:
    from ._version import VERSION
except Exception:
    VERSION = "1.0.0-dev"
