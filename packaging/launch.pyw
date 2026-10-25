"""Installed launcher: use the application's private Git runtime."""

import os
from pathlib import Path

from marketmaker.app import main

os.environ["PATH"] = str(Path(__file__).parent / "tools" / "git" / "cmd") + os.pathsep + os.environ["PATH"]
main()
