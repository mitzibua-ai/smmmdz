from __future__ import annotations

import hashlib
import math
import re
import struct
from dataclasses import dataclass
from pathlib import Path

# Known cheat builds by SHA256 (survives rename)
KNOWN_CHEAT_SHA256: dict[str, str] = {
    "234ddce9bdb3b9f24bfd828942725a033056881d925023eb9f25b24683b5ab32": (
        "Themida-packed FiveM cheat loader (random-name, ~70MB) — e.g. sz05e.exe"
    ),
}

# Unique byte markers inside specific cheat builds (partial match)
CHEAT_BYTE_MARKERS: list[tuple[bytes, str]] = [
    # Themida + large .data section profile seen in sz05e family
    (b".themida", "Themida packer section (common cheat protection)"),
]

PACKER_SECTIONS = {
    ".themida": "Themida",
    ".vmp0": "VMProtect",
    ".vmp1": "VMProtect",
    "upx0": "UPX",
    "upx1": "UPX",
    ".aspack": "ASPack",
    ".enigma1": "Enigma",
    ".enigma2": "Enigma",
}

# Random rename pattern — must include a digit (sz05e, k4m2p) to avoid conhost.exe etc.
RANDOM_EXE_NAME = re.compile(r"^[a-z0-9]{4,7}\.exe$", re.IGNORECASE)

LEGIT_SHORT_NAMES = {
    "fivem.exe", "gta5.exe", "cmd.exe", "conhost.exe", "csrss.exe",
    "lsass.exe", "smss.exe", "svchost.exe", "winlogon.exe", "dwm.exe",
    "python.exe", "pythonw.exe", "pip.exe", "pip3.exe", "dotenv.exe",
    "idna.exe", "steam.exe", "dxwebsetup.exe", "sihost.exe", "taskhostw.exe",
    "runtimebroker.exe", "searchhost.exe", "ctfmon.exe", "fontdrvhost.exe",
    "dllhost.exe", "audiodg.exe", "spoolsv.exe", "lsm.exe", "wininit.exe",
    "services.exe", "explorer.exe", "searchindexer.exe", "msedge.exe",
}

MAX_PE_SCAN_BYTES = 80 * 1024 * 1024  # 80 MB cap


@dataclass
class PEAnalysis:
    path: Path
    sha256: str
    size: int
    entropy: float
    sections: list[str]
    packers: list[str]
    is_pe: bool
    has_themida: bool
    suspicious_strings: list[str]


def _entropy(data: bytes) -> float:
    if not data:
        return 0.0
    freq = [0] * 256
    for b in data:
        freq[b] += 1
    ent = 0.0
    n = len(data)
    for f in freq:
        if f:
            p = f / n
            ent -= p * math.log2(p)
    return ent


def _parse_sections(data: bytes) -> list[str]:
    if len(data) < 64 or data[:2] != b"MZ":
        return []
    try:
        pe_off = struct.unpack_from("<I", data, 0x3C)[0]
        if data[pe_off : pe_off + 4] != b"PE\x00\x00":
            return []
        num = struct.unpack_from("<H", data, pe_off + 6)[0]
        opt_size = struct.unpack_from("<H", data, pe_off + 20)[0]
        sec_start = pe_off + 24 + opt_size
        names = []
        for i in range(num):
            off = sec_start + i * 40
            if off + 40 > len(data):
                break
            name = data[off : off + 8].split(b"\x00")[0].decode("ascii", errors="replace")
            names.append(name.lower())
        return names
    except struct.error:
        return []


def _extract_interesting_strings(data: bytes, limit: int = 20) -> list[str]:
    patterns = [
        rb"fivem", rb"citizenfx", rb"triggerbot", rb"aimbot", rb"noclip",
        rb"modmenu", rb"eulen", rb"susano", rb"macho", rb"skript",
        rb"loadstring", rb"inject", rb"bypass", rb"cheat", rb"esp",
        rb"godmode", rb"license", rb"hwid", rb"auth\.", rb"\.gg/",
    ]
    found: list[str] = []
    for match in re.finditer(rb"[\x20-\x7e]{6,}", data[:4 * 1024 * 1024]):
        s = match.group().lower()
        if any(p in s for p in patterns):
            text = match.group().decode("ascii", errors="replace")[:100]
            if text not in found:
                found.append(text)
            if len(found) >= limit:
                break
    return found


def analyze_pe(path: Path) -> PEAnalysis | None:
    try:
        size = path.stat().st_size
        if size == 0 or size > MAX_PE_SCAN_BYTES:
            return None
        data = path.read_bytes()
    except (OSError, PermissionError):
        return None

    sha256 = hashlib.sha256(data).hexdigest()
    sections = _parse_sections(data)
    packers = [PACKER_SECTIONS[s] for s in sections if s in PACKER_SECTIONS]
    # Also detect packer names embedded in section list
    for sec in sections:
        for key, name in PACKER_SECTIONS.items():
            if key in sec and name not in packers:
                packers.append(name)

    return PEAnalysis(
        path=path,
        sha256=sha256,
        size=size,
        entropy=round(_entropy(data[: min(len(data), 512 * 1024)]), 3),
        sections=sections,
        packers=packers,
        is_pe=data[:2] == b"MZ",
        has_themida=any(".themida" in s for s in sections),
        suspicious_strings=_extract_interesting_strings(data),
    )


def is_random_cheat_filename(name: str) -> bool:
    lower = name.lower()
    if lower in LEGIT_SHORT_NAMES:
        return False
    if not RANDOM_EXE_NAME.match(lower):
        return False
    # Cheats like sz05e.exe always mix letters + numbers
    if not re.search(r"\d", lower):
        return False
    return True


def is_whitelisted_path(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    whitelist = {
        "program files", "program files (x86)", "windows",
        ".venv", "venv", "scripts", "node_modules",
        "python", "microsoft", "google", "mozilla",
    }
    return bool(parts & whitelist)
