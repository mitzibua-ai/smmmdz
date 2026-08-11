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
        ("susano", "susano.dev", "susano_loader", "susanocheats", "susano.exe", "susanomenu"),
        Severity.CRITICAL,
        Category.CHEAT,
        "Susano — popular paid FiveM cheat menu",
    ),
    FileSignature(
        "Macho",
        ("macho", "machocheats", "macho_loader", "macho.exe", "macho_menu", "machocheats.com", "machomenu"),
        Severity.CRITICAL,
        Category.CHEAT,
        "Macho — FiveM cheat menu",
    ),
    FileSignature(
        "Eulen",
        ("eulen", "eulen.gg", "eulen_loader", "eulen.exe", "eulencheats", "eulenmenu", "eulenclient"),
        Severity.CRITICAL,
        Category.CHEAT,
        "Eulen — widely used FiveM cheat",
    ),
    FileSignature(
        "RedEngine",
        ("redengine", "red_engine", "redengine.exe", "redeng", "redenginev2", "redenginev3"),
        Severity.CRITICAL,
        Category.CHEAT,
        "RedEngine — FiveM cheat framework",
    ),
    FileSignature(
        "Skript",
        ("skript.gg", "skript_loader", "skript.exe", "skriptgg", "skriptclient"),
        Severity.CRITICAL,
        Category.CHEAT,
        "Skript — FiveM cheat loader",
    ),
    FileSignature(
        "HX Software",
        ("hxsoftware", "hx software", "hxcheats", "hx.exe", "hxmenu", "hxcheats.com"),
        Severity.CRITICAL,
        Category.CHEAT,
        "HX Software cheat",
    ),
    FileSignature(
        "Tz Project",
        ("tzproject", "tz project", "tzcheat", "tzproject.com", "tzcheats"),
        Severity.CRITICAL,
        Category.CHEAT,
        "Tz Project cheat",
    ),
    FileSignature(
        "Gosth",
        ("gosth", "gosth.gg", "gosthclient", "gosthloader", "gosthmenu"),
        Severity.CRITICAL,
        Category.CHEAT,
        "Gosth external cheat",
    ),
    FileSignature(
        "KekHack",
        ("kekhack", "kek hack", "kekmenu", "kekloader"),
        Severity.HIGH,
        Category.CHEAT,
        "KekHack free cheat",
    ),
    FileSignature(
        "Lumia",
        ("lumia", "lumiamenu", "lumia cheats", "lumialoader"),
        Severity.HIGH,
        Category.CHEAT,
        "Lumia cheat menu",
    ),
    FileSignature(
        "Brutan / Project",
        ("brutan", "brutanpremium", "brutanmenu", "projectloader", "projectcheat"),
        Severity.HIGH,
        Category.CHEAT,
        "Brutan / Project cheat family",
    ),
    FileSignature(
        "Degeo / Project Family",
        (
            "degeo", "degeo cracked", "projectyx", "project loader", "projectloader",
            "combatproject", "astaroth", "lunacy", "cutie external", "stringless",
            "katana", "asgard", "monster menu", "monkeyware",
        ),
        Severity.CRITICAL,
        Category.CHEAT,
        "Degeo / Project / community DPS cheat family",
    ),
    FileSignature(
        "Community DPS Cheats",
        (
            "88cheats", "88-cheats", "testo.gg", "mindselling", "sicario", "ciapak",
            "nightware", "hammafia", "ov projekt", "cfx mafia", "sylace loader",
            "byte cleaner", "stringcleaner", "ravenx", "khub", "tdpremium",
        ),
        Severity.HIGH,
        Category.CHEAT,
        "Additional cheats from imported DPS detection lists",
    ),
    FileSignature(
        "DPS Cleaner Tools",
        (
            "iObit unlocker", "iobit unlocker", "veracrypt bypass", "imdisk",
            "usb oblivion", "bleach bit", "phantom string cleaner", "eventvwr clear",
            "osf mount", "usbdeview", "ccleaner",
        ),
        Severity.CRITICAL,
        Category.CLEANER,
        "Cleaner / anti-forensic tools from DPS detection lists",
    ),
    FileSignature(
        "Generic Lua Executor",
        (
            "lua executor",
            "fivem executor",
            "citizen executor",
            "fivem mod menu",
            "fivem hack",
            "fivem cheat",
            "triggerbot.dll",
            "aimbot.dll",
            "noclip.lua",
            "godmode.lua",
            "moneydrop",
            "money drop",
            "injector fivem",
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
            "reflective dll",
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
        ("9zcleaner", "9z cleaner", "9z.exe", "ninez", "9z_cleaner", "9zcleaner.exe"),
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
            "prefetchwiper",
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
            "damcleaner",
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
            "fsutil usn deletejournal",
            "deletejournal",
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
            "evidence wiper",
            "clean traces",
            "removetraces",
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

# PowerShell / cmd commands that indicate evidence cleaning
CLEANER_COMMANDS: tuple[str, ...] = (
    "remove-item -path $env:systemroot\\prefetch",
    "del /f /q %windir%\\prefetch",
    "wevtutil cl security",
    "wevtutil cl system",
    "wevtutil cl application",
    "clear-eventlog",
    "clear-history",
    "remove-item (get-psreadlineoption).historysavepath",
    "fsutil usn deletejournal",
    "vssadmin delete shadows",
    "cipher /w:",
    "sdelete -p",
    "sdelete -z",
    "reg delete hklm\\system\\currentcontrolset\\services\\bam",
)

# ── Suspicious filenames (executable types only, matched with word boundaries) ──

SUSPICIOUS_FILENAMES: tuple[str, ...] = (
    "cheat",
    "hack",
    "injector",
    "loader",
    "bypass",
    "spoofer",
    "cleaner",
    "wiper",
    "executor",
    "modmenu",
    "mod_menu",
    "aimbot",
    "triggerbot",
    "noclip",
    "godmode",
    "eulen",
    "susano",
    "macho",
    "redengine",
    "skript",
    "9zcleaner",
    "gosth",
    "lumia",
    "kekhack",
    "brutan",
    "pccheck_bypass",
    "ss_bypass",
)

# Forum sites — lower severity (research != active cheat)
BROWSER_FORUM_DOMAINS: tuple[str, ...] = (
    "unknowncheats.me",
    "mpgh.net",
    "elitepvpers.com",
    "cheatglobal.com",
)

CHEAT_WEBSITE_DOMAINS: tuple[str, ...] = (
    "susano.dev",
    "eulen.gg",
    "skript.gg",
    "gosth.gg",
    "hxcheats",
    "machocheats",
    "redengine",
    "tzproject",
)


def load_cheat_domains() -> tuple[str, ...]:
    """Extra cheat/cleaner domains from imported detection lists."""
    from functools import lru_cache
    from pathlib import Path

    @lru_cache(maxsize=1)
    def _load() -> tuple[str, ...]:
        candidates = [
            Path(__file__).resolve().parent / "data" / "cheat_domains.txt",
            Path(__file__).resolve().parent / "cheat_domains.txt",
        ]
        try:
            from pccheck.data.trace_db import _bundled_data_file

            candidates.insert(0, _bundled_data_file("cheat_domains.txt"))
        except ImportError:
            pass
        path = next((p for p in candidates if p.is_file()), None)
        if path is None:
            return ()
        domains: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            d = line.strip().lower()
            if d and d not in domains:
                domains.append(d)
        return tuple(domains)

    return _load()

CHEAT_PROCESS_SIGNATURES: list[ProcessSignature] = [
    ProcessSignature(
        "Susano",
        ("susano", "susano_loader", "susanomenu"),
        ("susano",),
        Severity.CRITICAL,
        Category.CHEAT,
        "Susano process running",
    ),
    ProcessSignature(
        "Macho",
        ("macho", "macho_loader", "macho_menu", "machomenu"),
        ("macho",),
        Severity.CRITICAL,
        Category.CHEAT,
        "Macho process running",
    ),
    ProcessSignature(
        "Eulen",
        ("eulen", "eulen_loader", "eulenmenu"),
        ("eulen",),
        Severity.CRITICAL,
        Category.CHEAT,
        "Eulen process running",
    ),
    ProcessSignature(
        "9z Cleaner",
        ("9zcleaner", "ninez", "9z_cleaner"),
        ("9z",),
        Severity.CRITICAL,
        Category.CLEANER,
        "9z cleaner process running",
    ),
    ProcessSignature(
        "Cheat Loader",
        ("kdmapper", "susano_loader", "eulen_loader", "macho_loader", "skript_loader"),
        (),
        Severity.HIGH,
        Category.INJECTION,
        "Known cheat loader process",
    ),
]

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

MAX_CONTENT_SCAN_BYTES = 10 * 1024 * 1024
