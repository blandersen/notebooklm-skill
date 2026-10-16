#!/usr/bin/env python3
"""
Universal runner for NotebookLM skill scripts
Runs a skill script with the skill's own .venv interpreter.
Never installs anything: if the venv is missing or out of date it says so and exits 3,
so the caller can ask the user before running setup_environment.py.
"""

import hashlib
import os
import sys
import subprocess
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
VENV_DIR = SKILL_DIR / ".venv"
REQUIREMENTS = SKILL_DIR / "requirements.txt"
# Written by setup_environment.py after a successful install
STAMP = VENV_DIR / ".requirements.sha256"

SCRIPTS = {
    "ask_question.py": "Query a notebook",
    "notebook_manager.py": "Manage notebook library",
    "auth_manager.py": "Handle authentication",
    "cleanup_manager.py": "Clean up skill data",
    "setup_environment.py": "Create/update the skill .venv (installs packages)",
}

EXIT_ENV = 3


def venv_python() -> Path:
    if os.name == 'nt':
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def requirements_hash() -> str:
    """Hash of the requirement lines only, so editing comments does not invalidate the venv"""
    lines = [l.split("#")[0].strip() for l in REQUIREMENTS.read_text().splitlines()]
    return hashlib.sha256("\n".join(l for l in lines if l).encode()).hexdigest()


def env_problem() -> str:
    """Return a description of what is wrong with the venv, or '' if usable"""
    python = venv_python()
    if not python.exists():
        return "the skill virtual environment (.venv) does not exist"
    # The venv's base interpreter (e.g. a conda env) may have been removed or upgraded
    probe = subprocess.run([str(python), "-c", "import patchright"], capture_output=True)
    if probe.returncode != 0:
        return "the .venv is broken or missing patchright"
    if not STAMP.exists() or STAMP.read_text().strip() != requirements_hash():
        return "requirements.txt changed since the .venv was built"
    return ""


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 run.py <script_name> [args...]\n\nAvailable scripts:")
        for name, desc in SCRIPTS.items():
            print(f"  {name:22} {desc}")
        sys.exit(1)

    script_name = sys.argv[1].removeprefix("scripts/")
    if not script_name.endswith('.py'):
        script_name += '.py'
    script_args = sys.argv[2:]

    script_path = SKILL_DIR / "scripts" / script_name
    if not script_path.exists():
        print(f"❌ Script not found: {script_name}")
        print(f"   Looked for: {script_path}")
        sys.exit(1)

    # Setup runs on the system interpreter since it is what builds the venv
    if script_name == "setup_environment.py":
        python = Path(sys.executable)
    else:
        problem = env_problem()
        if problem:
            print(f"⚠️ Environment not ready: {problem}.")
            print("   Setup creates .venv inside the skill directory and pip-installs requirements.txt there")
            print("   (no conda environment is touched). Ask the user before running:")
            print(f"   python3 {SKILL_DIR / 'scripts' / 'run.py'} setup_environment.py")
            sys.exit(EXIT_ENV)
        python = venv_python()

    try:
        result = subprocess.run([str(python), str(script_path)] + script_args)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
        sys.exit(130)


if __name__ == "__main__":
    main()
