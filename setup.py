#!/usr/bin/env python3
"""
Setup script for the Contact Form Crawler.
Installs Python dependencies and Playwright browsers.
"""

import subprocess
import sys
from typing import List


def run(cmd: List[str], description: str) -> bool:
    """Run a command; return True on success, False on failure."""
    print(f"\n>>> {description}")
    print(f"    {' '.join(cmd)}\n")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"\n[FAILED] {description} (exit code {result.returncode})")
        return False
    print(f"\n[OK] {description}")
    return True


def main() -> int:
    print("=" * 60)
    print("Contact Form Crawler — Setup")
    print("=" * 60)

    steps_ok = True

    # 1. Install Python dependencies
    if not run(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
        "Installing Python dependencies (pip install -r requirements.txt)",
    ):
        steps_ok = False

    # 2. Install Playwright Chromium
    if not run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        "Installing Playwright Chromium browser",
    ):
        steps_ok = False

    # 3. Optional: Ollama model (only if --ollama passed)
    if "--ollama" in sys.argv:
        if not run(
            ["ollama", "pull", "llama3.2"],
            "Pulling Ollama model llama3.2 (requires Ollama installed)",
        ):
            steps_ok = False
    else:
        print("\n>>> Skipping Ollama model pull (use --ollama to run: ollama pull llama3.2)")

    print("\n" + "=" * 60)
    if steps_ok:
        print("Setup complete. Run: python crawler.py")
        print("=" * 60)
        return 0
    else:
        print("Setup had failures. Fix the errors above, then run: python crawler.py")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
