"""Push website to GitHub and sync Supabase database + API."""
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
    print(" GitHub  = website + exe (GitHub Pages)")
    print(" Supabase = database + API")
    print()
    return subprocess.call([sys.executable, str(ROOT / "scripts" / "push_supabase.py")])


if __name__ == "__main__":
    sys.exit(main())
