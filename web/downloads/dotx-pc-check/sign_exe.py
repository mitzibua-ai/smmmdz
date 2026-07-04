"""Sign Windows executables with Authenticode (removes SmartScreen after reputation builds)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def find_signtool() -> str | None:
    found = shutil.which("signtool")
    if found:
        return found
    kits = Path(r"C:\Program Files (x86)\Windows Kits\10\bin")
    if not kits.is_dir():
        return None
    for ver_dir in sorted(kits.iterdir(), reverse=True):
        candidate = ver_dir / "x64" / "signtool.exe"
        if candidate.is_file():
            return str(candidate)
    return None


def sign_exe(exe_path: Path) -> bool:
    """Sign exe if CODE_SIGN_PFX (+ password) or thumbprint cert is configured."""
    exe_path = Path(exe_path)
    if not exe_path.is_file():
        return False

    pfx = os.environ.get("CODE_SIGN_PFX", "").strip()
    password = os.environ.get("CODE_SIGN_PASSWORD", "")
    thumbprint = os.environ.get("CODE_SIGN_THUMBPRINT", "").strip()
    timestamp = os.environ.get(
        "CODE_SIGN_TIMESTAMP",
        "http://timestamp.digicert.com",
    ).strip()

    signtool = find_signtool()
    if not signtool:
        print("signtool not found — install Windows SDK or skip signing.")
        return False

    cmd: list[str] = [signtool, "sign", "/fd", "SHA256", "/td", "SHA256", "/tr", timestamp]

    if thumbprint:
        cmd.extend(["/sha1", thumbprint, "/sm"])
    elif pfx and Path(pfx).is_file():
        cmd.extend(["/f", pfx])
        if password:
            cmd.extend(["/p", password])
    else:
        return False

    cmd.append(str(exe_path))
    print("Signing", exe_path.name, "...")
    subprocess.check_call(cmd)
    print("Signed:", exe_path)
    return True


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python sign_exe.py path\\to\\dotx-pc-check.exe")
        return 1
    try:
        ok = sign_exe(Path(sys.argv[1]))
    except subprocess.CalledProcessError as exc:
        print("Signing failed:", exc)
        return exc.returncode or 1
    if not ok:
        print(
            "No signing certificate configured.\n"
            "Set CODE_SIGN_PFX + CODE_SIGN_PASSWORD, or CODE_SIGN_THUMBPRINT.\n"
            "Buy an Authenticode cert (DigiCert, Sectigo, SSL.com) to remove SmartScreen."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
