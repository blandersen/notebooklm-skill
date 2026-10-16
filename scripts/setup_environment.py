#!/usr/bin/env python3
"""
Environment Setup for NotebookLM Skill
Creates the skill-local .venv and installs requirements.txt into it.
This is the only script that installs packages; run.py never calls it implicitly.
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
import venv
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from run import VENV_DIR, REQUIREMENTS, STAMP, venv_python, requirements_hash

# Standard Google Chrome locations; patchright drives real Chrome via channel="chrome"
CHROME_PATHS = {
    "Darwin": [Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
               Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"],
    "Linux": [Path("/opt/google/chrome/chrome")],
    "Windows": [Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe",
                Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe"],
}


def chrome_installed() -> bool:
    if any(p.exists() for p in CHROME_PATHS.get(platform.system(), [])):
        return True
    return any(shutil.which(n) for n in ("google-chrome", "google-chrome-stable"))


def run(cmd):
    print(f"  $ {' '.join(map(str, cmd))}")
    subprocess.run([str(c) for c in cmd], check=True)


def main():
    parser = argparse.ArgumentParser(description='Set up the NotebookLM skill environment')
    parser.add_argument('--recreate', action='store_true', help='Delete and rebuild .venv')
    parser.add_argument('--check', action='store_true', help='Only report status')
    args = parser.parse_args()

    if args.check:
        print(f"  .venv:   {'present' if venv_python().exists() else 'missing'} ({VENV_DIR})")
        stamp_ok = STAMP.exists() and STAMP.read_text().strip() == requirements_hash()
        print(f"  deps:    {'up to date' if stamp_ok else 'not installed or outdated'}")
        print(f"  Chrome:  {'found' if chrome_installed() else 'not found'}")
        return 0

    if args.recreate and VENV_DIR.exists():
        print(f"🗑️ Removing {VENV_DIR}")
        shutil.rmtree(VENV_DIR)

    if not venv_python().exists():
        print(f"🔧 Creating virtual environment with {sys.executable}")
        venv.create(VENV_DIR, with_pip=True)

    print("📦 Installing requirements into .venv")
    try:
        run([venv_python(), "-m", "pip", "install", "--upgrade", "pip"])
        run([venv_python(), "-m", "pip", "install", "-r", REQUIREMENTS])
    except subprocess.CalledProcessError as e:
        print(f"❌ pip failed: {e}")
        return 1

    if chrome_installed():
        print("✅ Google Chrome found")
    else:
        # On macOS/Linux this downloads Chrome and may prompt for sudo
        print("🌐 Google Chrome not found; installing via patchright")
        try:
            run([venv_python(), "-m", "patchright", "install", "chrome"])
        except subprocess.CalledProcessError:
            print("⚠️ Chrome install failed. Install Google Chrome manually from https://www.google.com/chrome/")
            return 1

    STAMP.write_text(requirements_hash())
    print("\n✅ Environment ready")
    return 0


if __name__ == "__main__":
    sys.exit(main())
