"""Detection signatures for FiveM cheats, injectors, and forensic cleaners."""

from __future__ import annotations

from dataclasses import dataclass

from pccheck.models import Category, Severity


@dataclass(frozen=True)
class FileSignature:
    name: str
    patterns: tuple[str, ...]
    severity: Severity
    category: Category
    description: str


@dataclass(frozen=True)
class ProcessSignature:
    name: str
    process_names: tuple[str, ...]
    window_titles: tuple[str, ...]
    severity: Severity
    category: Category
    description: str


# ── Known FiveM cheat menus / loaders ──────────────────────────────────────

CHEAT_FILE_SIGNATURES: list[FileSignature] = [
    FileSignature(
        "Susano",
        ("susano", "susano.dev", "susano_loader", "susanocheats", "susano.exe"),
        Severity.CRITICAL,
        Category.CHEAT,
        "Susano — popular paid FiveM cheat menu",
    ),
    FileSignature(
        "Macho",
        ("macho", "machocheats", "macho_loader", "macho.exe", "macho_menu", "machocheats.com"),
        Severity.CRITICAL,
        Category.CHEAT,
        "Macho — FiveM cheat menu",
    ),
    FileSignature(
        "Eulen",
        ("eulen", "eulen.gg", "eulen_loader", "eulen.exe", "eulencheats", "eulen.gg"),
        Severity.CRITICAL,
        Category.CHEAT,
        "Eulen — widely used FiveM cheat",
    ),
    FileSignature(
        "RedEngine",
        ("redengine", "red_engine", "redengine.exe", "redeng"),
        Severity.CRITICAL,
        Category.CHEAT,
        "RedEngine — FiveM cheat framework",
    ),
    FileSignature(
        "Skript",
        ("skript.gg", "skript_loader", "skript.exe", "skriptgg"),
        Severity.CRITICAL,
        Category.CHEAT,
        "Skript — FiveM cheat loader",
    ),
    FileSignature(
        "HX Software",
        ("hxsoftware", "hx software", "hxcheats", "hx.exe"),
        Severity.CRITICAL,
        Category.CHEAT,
        "HX Software cheat",
    ),
    FileSignature(
        "Tz Project",
        ("tzproject", "tz project", "tzcheat", "tzproject.com"),
        Severity.CRITICAL,
        Category.CHEAT,
        "Tz Project cheat",
    ),
    FileSignature(
        "Gosth",
        ("gosth", "gosth.gg", "gosthclient"),
        Severity.CRITICAL,
        Category.CHEAT,
        "Gosth external cheat",
    ),
    FileSignature(
        "KekHack",
        ("kekhack", "kek hack", "kekmenu"),
        Severity.HIGH,
        Category.CHEAT,
        "KekHack free cheat",
    ),
    FileSignature(
        "Lumia",
        ("lumia", "lumiamenu", "lumia cheats"),
        Severity.HIGH,
        Category.CHEAT,
        "Lumia cheat menu",
    ),
    FileSignature(
        "Generic Lua Executor",
        (
            "lua executor",
            "fivem executor",
            "citizen executor",
            "triggerbot",
            "aimbot.dll",
            "esp.dll",
            "noclip.lua",
            "godmode.lua",
            "moneydrop",
            "money drop",
            "injector fivem",
            "fivem hack",
            "fivem cheat",
            "fivem mod menu",
        ),
        Severity.HIGH,
        Category.CHEAT,
        "Generic free FiveM cheat / executor pattern",
    ),
    FileSignature(
        "Cheat Loader Patterns",
        (
            "kdmapper",
            "manual map",
            "process hollowing",
            "processhollowing",
            "dll inject",
            "loadlibrary inject",
            "citizenfx.inject",
            "d3d11 hook",
            "present hook",
        ),
        Severity.HIGH,
        Category.INJECTION,
        "Injection / mapper technique used by cheats",
    ),
]

# ── Cleaners & anti-forensic tools ─────────────────────────────────────────

CLEANER_FILE_SIGNATURES: list[FileSignature] = [
    FileSignature(
        "9z Cleaner",
        ("9z", "9zcleaner", "9z cleaner", "9z.exe", "ninez", "9z_cleaner"),
        Severity.CRITICAL,
        Category.CLEANER,
        "9z — forensic evidence cleaner used before PC checks",
    ),
    FileSignature(
        "Prefetch Cleaner",
        (
            "prefetch clean",
            "prefetchcleaner",
            "prefetch_clean",
            "clearprefetch",
            "wipe prefetch",
            "deleteprefetch",
        ),
        Severity.CRITICAL,
        Category.CLEANER,
        "Tool that clears Windows Prefetch artifacts",
    ),
    FileSignature(
        "BAM/Registry Wiper",
        (
            "bam clean",
            "bamcleaner",
            "bam wiper",
            "registry wiper",
            "registrywiper",
            "dam clean",
        ),
        Severity.CRITICAL,
        Category.CLEANER,
        "Tool that wipes BAM/DAM execution records",
    ),
    FileSignature(
        "USN Journal Wiper",
        (
            "usn clean",
            "usn journal",
            "journal wiper",
            "usnjrnl",
            "journal clean",
            "$usnjrnl",
        ),
        Severity.CRITICAL,
        Category.CLEANER,
        "Tool that manipulates NTFS USN journal",
    ),
    FileSignature(
        "Generic Screenshare Bypass",
        (
            "screenshare bypass",
            "pc check bypass",
            "pccheck bypass",
            "echo bypass",
            "ocean bypass",
            "anticheat bypass",
            "ss bypass",
            "forensic clean",
            "trace clean",
            "artifact clean",
            "evidence clean",
            "cleaner.exe",
            "bypass.exe",
            "wiper.exe",
        ),
        Severity.CRITICAL,
        Category.BYPASS,
        "Anti-forensic / screenshare bypass tool",
    ),
    FileSignature(
        "HWID Spoofer",
        (
            "hwid spoofer",
            "hwidspoof",
            "spoofer.exe",
            "serial spoofer",
            "disk spoofer",
            "mac spoofer",
            "ban bypass",
            "globalban bypass",
        ),
        Severity.HIGH,
        Category.BYPASS,
        "HWID / ban evasion spoofer",
    ),
]

# ── Suspicious filenames (exact / partial match) ───────────────────────────

SUSPICIOUS_FILENAMES: tuple[str, ...] = (
    "cheat",
    "hack",
    "inject",
    "loader",
    "bypass",
    "spoofer",
    "cleaner",
    "wiper",
    "executor",
    "modmenu",
    "mod_menu",
    "aimbot",
    "esp",
    "triggerbot",
    "noclip",
    "godmode",
    "eulen",
    "susano",
    "macho",
    "redengine",
    "skript",
    "9z",
    "gosth",
    "lumia",
    "kekhack",
)

CHEAT_WEBSITE_DOMAINS: tuple[str, ...] = (
    "susano.dev",
    "eulen.gg",
    "skript.gg",
    "gosth.gg",
    "unknowncheats.me",
    "mpgh.net",
    "cheatglobal.com",
    "elitepvpers.com",
    "hxcheats",
    "machocheats",
    "redengine",
    "tzproject",
)

CHEAT_PROCESS_SIGNATURES: list[ProcessSignature] = [
    ProcessSignature(
        "Susano",
        ("susano", "susano_loader"),
        ("susano",),
        Severity.CRITICAL,
        Category.CHEAT,
        "Susano process running",
    ),
    ProcessSignature(
        "Macho",
        ("macho", "macho_loader", "macho_menu"),
        ("macho",),
        Severity.CRITICAL,
        Category.CHEAT,
        "Macho process running",
    ),
    ProcessSignature(
        "Eulen",
        ("eulen", "eulen_loader"),
        ("eulen",),
        Severity.CRITICAL,
        Category.CHEAT,
        "Eulen process running",
    ),
    ProcessSignature(
        "9z Cleaner",
        ("9z", "9zcleaner", "ninez"),
        ("9z",),
        Severity.CRITICAL,
        Category.CLEANER,
        "9z cleaner process running",
    ),
    ProcessSignature(
        "Generic Injector",
        ("injector", "loader", "kdmapper", "cheat", "hack"),
        (),
        Severity.HIGH,
        Category.INJECTION,
        "Suspicious injector/loader process",
    ),
]

# FiveM-specific paths to scan
FIVEM_RELATIVE_PATHS: tuple[str, ...] = (
    "FiveM",
    "FiveM Application Data",
    "CitizenFX",
)

SCAN_EXTENSIONS: tuple[str, ...] = (
    ".exe",
    ".dll",
    ".sys",
    ".bat",
    ".cmd",
    ".ps1",
    ".vbs",
    ".lua",
    ".js",
    ".json",
    ".cfg",
    ".ini",
    ".txt",
    ".log",
    ".zip",
    ".rar",
    ".7z",
)

# Max file size to read for content scan (10 MB)
MAX_CONTENT_SCAN_BYTES = 10 * 1024 * 1024
