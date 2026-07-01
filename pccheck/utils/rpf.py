from __future__ import annotations

import struct
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

RPF7_MAGIC = 0x52504637
RPF7_MAGIC_BYTES = struct.pack("<I", RPF7_MAGIC)  # on disk: b'7FPR'
DIR_OFFSET_MARKER = 0x7FFFFF

ENCRYPTION_NAMES = {
    0: "None",
    0x4E45504F: "OPEN",
    0x0FFFFFF9: "AES",
    0x0FEFFFFF: "NG",
    0x50584643: "CFXP",
}

# Only these inside an RPF = gameplay cheat (not cosmetic mods)
CHEAT_INTERNAL_FILES = {
    "weapons.meta": "Weapon stat modifications (damage, recoil, unlimited ammo)",
    "weaponanimations.meta": "Weapon animation modifications",
    "weaponcomponents.meta": "Weapon component modifications",
    "handling.meta": "Vehicle handling modifications (speed/grip cheats)",
    "loadouts.meta": "Loadout / weapon spawn modifications",
    "pedaccuracy.meta": "Ped accuracy modifications",
    "combatbehavior.meta": "Combat behavior modifications",
    "weaponarchetypes.meta": "Custom weapon stat definitions",
    "shop_weapon.meta": "Weapon shop modifications",
}

# Normal files in legitimate addon RPFs (cars, maps, skins, MLOs)
LEGITIMATE_FILES = {
    "assembly.xml", "content.xml", "setup2.xml", "setup.xml",
    "credits.txt", "readme.txt", "changelog.txt",
}

LEGITIMATE_EXTENSIONS = (
    ".yft", ".ydr", ".ytd", ".ymap", ".ytyp", ".ymt", ".ydd",
    ".ybn", ".ycd", ".awc", ".gxt2", ".rel", ".cut", ".meta",  # .meta alone not cheat - check basename
)

# Cosmetic-only meta (not flagged alone)
COSMETIC_META = {
    "carcols.meta", "carvariations.meta", "gtxd.meta", "vehicles.meta",
    "caraddoncontent.meta", "dlctext.meta", "peds.meta",
}

SUSPICIOUS_RPF_NAMES = (
    "cheat", "hack", "aimbot", "godmode", "norecoil", "rapidfire",
    "unlimited", "trainer", "modmenu", "inject",
)

RPF_STRING_PATTERNS = (
    b"modmenu", b"aimbot", b"triggerbot", b"godmode", b"norecoil",
    b"unlimitedammo", b"rapidfire", b"noclip",
    b"eulen", b"susano", b"machocheats",
)

MAX_RPF_READ = 500 * 1024 * 1024  # allow large archives; we only read header + nested chunks
MAX_FULL_READ = 80 * 1024 * 1024   # read entire file only if smaller than this
MAX_NESTED_DEPTH = 4


class RpfVerdict(str, Enum):
    CLEAN = "clean"
    CHEAT = "cheat"
    UNREADABLE = "unreadable"


@dataclass
class RpfEntry:
    name: str
    size: int
    offset_units: int
    is_directory: bool
    virt_flags: int = 0
    phys_flags: int = 0

    @property
    def data_size(self) -> int:
        """Actual byte size — RPF7 stores size in virtFlags when entry size field is 0."""
        if self.size > 0:
            return self.size
        # OPEN archive binary/resource entries
        if self.virt_flags > 0:
            return self.virt_flags
        return 0


@dataclass
class RpfAnalysis:
    path: str
    valid: bool
    verdict: RpfVerdict = RpfVerdict.UNREADABLE
    entry_count: int = 0
    encryption: str = ""
    file_size: int = 0
    entries: list[RpfEntry] = field(default_factory=list)
    cheat_files: list[tuple[str, str]] = field(default_factory=list)
    string_hits: list[str] = field(default_factory=list)
    nested_scanned: list[str] = field(default_factory=list)
    legitimate_summary: list[str] = field(default_factory=list)


def _read_name(name_table: bytes, offset: int) -> str:
    if offset >= len(name_table):
        return ""
    end = name_table.find(b"\x00", offset)
    if end == -1:
        end = min(offset + 256, len(name_table))
    return name_table[offset:end].decode("ascii", errors="replace")


def _parse_entry(data: bytes, offset: int) -> tuple[int, int, int, int, int]:
    if offset + 16 > len(data):
        return 0, 0, 0, 0, 0
    val = struct.unpack_from("<Q", data, offset)[0]
    virt, phys = struct.unpack_from("<II", data, offset + 8)
    return val & 0xFFFF, (val >> 16) & 0xFFFFFF, (val >> 40) & 0xFFFFFF, virt, phys


def _extract_file(archive: bytes, offset_units: int, size: int) -> bytes:
    start = offset_units * 512
    if start >= len(archive) or size <= 0:
        return b""
    return archive[start : start + size]


def _basename(path: str) -> str:
    return path.lower().replace("\\", "/").rsplit("/", 1)[-1]


def _is_legitimate_asset(name: str) -> bool:
    base = _basename(name)
    if base in LEGITIMATE_FILES:
        return True
    return any(base.endswith(ext) for ext in LEGITIMATE_EXTENSIONS if ext != ".meta")


def _scan_strings(data: bytes) -> list[str]:
    hits: list[str] = []
    chunk = data[: min(len(data), 8 * 1024 * 1024)].lower()
    for pat in RPF_STRING_PATTERNS:
        if pat in chunk:
            hits.append(pat.decode("ascii"))
    return hits


def _parse_rpf_bytes(data: bytes, label: str) -> RpfAnalysis | None:
    if len(data) < 16:
        return None

    magic, entry_count, name_length, encryption = struct.unpack_from("<IIII", data, 0)
    if magic != RPF7_MAGIC:
        return None

    enc_name = ENCRYPTION_NAMES.get(encryption, f"0x{encryption:08X}")
    entries_offset = 16
    names_offset = entries_offset + entry_count * 16
    names_end = names_offset + name_length

    if names_end > len(data):
        return RpfAnalysis(
            path=label, valid=True, encryption=enc_name,
            entry_count=entry_count, file_size=len(data),
            verdict=RpfVerdict.UNREADABLE,
        )

    name_table = data[names_offset:names_end]
    parsed: list[RpfEntry] = []
    cheat_files: list[tuple[str, str]] = []
    nested_rpf_entries: list[RpfEntry] = []
    legit: list[str] = []

    for i in range(entry_count):
        off = entries_offset + i * 16
        name_offset, size, file_offset, virt, phys = _parse_entry(data, off)
        is_dir = file_offset == DIR_OFFSET_MARKER
        name = _read_name(name_table, name_offset)
        if not name:
            continue

        entry = RpfEntry(
            name=name, size=size, offset_units=file_offset,
            is_directory=is_dir, virt_flags=virt, phys_flags=phys,
        )
        parsed.append(entry)

        if is_dir:
            continue

        base = _basename(name)
        if base in CHEAT_INTERNAL_FILES:
            cheat_files.append((name, CHEAT_INTERNAL_FILES[base]))
        elif base.endswith(".rpf"):
            nested_rpf_entries.append(entry)
        elif _is_legitimate_asset(name):
            legit.append(base)

    string_hits = _scan_strings(data)

    return RpfAnalysis(
        path=label,
        valid=True,
        entry_count=entry_count,
        encryption=enc_name,
        file_size=len(data),
        entries=parsed,
        cheat_files=cheat_files,
        string_hits=string_hits,
        legitimate_summary=legit[:12],
        verdict=RpfVerdict.CHEAT if (cheat_files or string_hits) else RpfVerdict.CLEAN,
    )


def _read_rpf_header(path: Path) -> tuple[bytes, int] | None:
    """Read header + TOC + name table without loading the whole archive."""
    try:
        file_size = path.stat().st_size
        if file_size == 0 or file_size > MAX_RPF_READ:
            return None
        with path.open("rb") as f:
            header = f.read(16)
            if len(header) < 16:
                return None
            magic, entry_count, name_length, _enc = struct.unpack_from("<IIII", header, 0)
            if magic != RPF7_MAGIC:
                return None
            toc_size = entry_count * 16
            toc_and_names = f.read(toc_size + name_length)
            return header + toc_and_names, file_size
    except (OSError, PermissionError):
        return None


def _read_rpf_chunk(path: Path, offset_units: int, size: int) -> bytes:
    try:
        start = offset_units * 512
        with path.open("rb") as f:
            f.seek(start)
            return f.read(size)
    except (OSError, PermissionError):
        return b""


def deep_analyze_rpf(path: Path, depth: int = 0) -> RpfAnalysis | None:
    """Parse RPF and recursively inspect nested .rpf archives before verdict."""
    path = Path(path)
    header_result = _read_rpf_header(path)
    if not header_result:
        return None

    header_data, file_size = header_result

    # For string scan on small files, read full content; large files skip string scan on outer
    if file_size <= MAX_FULL_READ:
        try:
            archive = path.read_bytes()
        except (OSError, PermissionError):
            archive = header_data
    else:
        archive = header_data  # TOC only; nested chunks read separately

    analysis = _parse_rpf_bytes(archive if file_size <= MAX_FULL_READ else header_data, str(path))
    if not analysis:
        return None

    analysis.file_size = file_size

    # String scan: for large files read first 8MB only
    if file_size > MAX_FULL_READ:
        try:
            with path.open("rb") as f:
                chunk = f.read(8 * 1024 * 1024)
            analysis.string_hits = _scan_strings(chunk)
        except OSError:
            pass

    if depth >= MAX_NESTED_DEPTH:
        analysis.verdict = RpfVerdict.CHEAT if (analysis.cheat_files or analysis.string_hits) else RpfVerdict.CLEAN
        return analysis

    all_cheat = list(analysis.cheat_files)
    all_strings = list(analysis.string_hits)
    nested_scanned: list[str] = []

    for entry in analysis.entries:
        if entry.is_directory or not entry.name.lower().endswith(".rpf"):
            continue

        nested_bytes = (
            _extract_file(archive, entry.offset_units, entry.data_size)
            if file_size <= MAX_FULL_READ
            else _read_rpf_chunk(path, entry.offset_units, min(entry.data_size, MAX_FULL_READ))
        )
        if len(nested_bytes) < 16 or nested_bytes[:4] != RPF7_MAGIC_BYTES:
            continue

        nested_scanned.append(entry.name)
        nested = _parse_rpf_bytes(nested_bytes, f"{path.name} > {entry.name}")
        if not nested:
            continue

        for cf in nested.cheat_files:
            all_cheat.append((f"{entry.name}/{cf[0]}", cf[1]))
        for s in nested.string_hits:
            if s not in all_strings:
                all_strings.append(s)

        if depth + 1 < MAX_NESTED_DEPTH:
            for sub in nested.entries:
                if sub.is_directory or not sub.name.lower().endswith(".rpf"):
                    continue
                sub_bytes = _extract_file(nested_bytes, sub.offset_units, min(sub.data_size, MAX_FULL_READ))
                if len(sub_bytes) < 16 or sub_bytes[:4] != RPF7_MAGIC_BYTES:
                    continue
                nested_scanned.append(f"{entry.name}/{sub.name}")
                sub_analysis = _parse_rpf_bytes(sub_bytes, f"{path.name} > {entry.name} > {sub.name}")
                if sub_analysis:
                    for cf in sub_analysis.cheat_files:
                        all_cheat.append((f"{entry.name}/{sub.name}/{cf[0]}", cf[1]))
                    for s in sub_analysis.string_hits:
                        if s not in all_strings:
                            all_strings.append(s)

    analysis.cheat_files = all_cheat
    analysis.string_hits = all_strings
    analysis.nested_scanned = nested_scanned
    analysis.verdict = RpfVerdict.CHEAT if (all_cheat or all_strings) else RpfVerdict.CLEAN
    return analysis


def parse_rpf7(path) -> RpfAnalysis | None:
    """Backward-compatible entry point."""
    return deep_analyze_rpf(Path(path))


def suspicious_rpf_filename(name: str) -> str | None:
    lower = name.lower()
    for kw in SUSPICIOUS_RPF_NAMES:
        if kw in lower:
            return kw
    return None
