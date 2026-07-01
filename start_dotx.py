"""Run dotx Discord bot + API (data store) on Railway — website is on GitHub Pages."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
PROCS: list[subprocess.Popen] = []


def _shutdown(*_args) -> None:
    for proc in PROCS:
        if proc.poll() is None:
            proc.terminate()
    deadline = time.time() + 8
    for proc in PROCS:
        if proc.poll() is None and time.time() < deadline:
            try:
                proc.wait(timeout=max(0, deadline - time.time()))
            except subprocess.TimeoutExpired:
                proc.kill()
    sys.exit(0)


def main() -> None:
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    env = os.environ.copy()
    env.setdefault("HOST", "0.0.0.0")
    env.setdefault("DATA_DIR", "/data")
    env.setdefault("DATA_PATH", "/data/store.json")
    env.setdefault("API_ONLY", "1")

    print("[dotx] Starting API (serve.py, data + downloads)...", flush=True)
    web = subprocess.Popen(
        [sys.executable, "serve.py"],
        cwd=str(WEB),
        env=env,
    )
    PROCS.append(web)

    print("[dotx] Starting Discord bot...", flush=True)
    bot = subprocess.Popen(
        [sys.executable, "-m", "discord_bot.bot"],
        cwd=str(ROOT),
        env=env,
    )
    PROCS.append(bot)

    while True:
        for proc in PROCS:
            code = proc.poll()
            if code is not None:
                print(f"[dotx] Process exited with code {code}. Shutting down.", flush=True)
                _shutdown()
        time.sleep(2)


if __name__ == "__main__":
    main()
