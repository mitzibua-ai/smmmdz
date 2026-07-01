"""Deploy dotx website + bot together — use push_all.py instead."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    sys.exit(subprocess.call([sys.executable, str(ROOT / "scripts" / "push_all.py")]))
