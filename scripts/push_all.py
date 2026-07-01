"""Push website to GitHub and API+bot to Railway."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    print()
    print(" dotx - Push Everything")
    print(" ======================")
    print()
    print(" GitHub  = website (pages)")
    print(" Railway = API data + Discord bot")
    print()

    github = subprocess.call([sys.executable, str(ROOT / "scripts" / "push_github.py")])
    if github != 0:
        return github

    print()
    railway = subprocess.call([sys.executable, str(ROOT / "scripts" / "push_railway.py")])
    return railway


if __name__ == "__main__":
    sys.exit(main())
