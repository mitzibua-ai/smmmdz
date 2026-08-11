"""Scan ZIP/RAR/7Z/TAR archives for hidden cheat and cleaner payloads."""
from __future__ import annotations

import os
import tarfile
import zipfile
from pathlib import Path

from pccheck.models import Category, Finding, ScanResult, Severity
from pccheck.signatures import CHEAT_FILE_SIGNATURES, CLEANER_FILE_SIGNATURES
from pccheck.utils.match import is_legit_cleaner_name, is_whitelisted_path, match_path
from pccheck.utils.pe import is_random_cheat_filename
from pccheck.utils.walk import iter_files_limited

ARCHIVE_EXTENSIONS = {
    ".zip",
    ".rar",
    ".7z",
    ".tar",
    ".gz",
    ".tgz",
    ".bz2",
    ".xz",
    ".cab",
    ".iso",
}

# Members we peek inside (text / scripts / configs)
INNER_TEXT_EXTS = {".txt", ".lua", ".cfg", ".ini", ".bat", ".cmd", ".ps1", ".json", ".log", ".md", ".vbs", ".js"}
# Members that are themselves executables / nested archives
INNER_DANGER_EXTS = {".exe", ".dll", ".sys", ".asi", ".zip", ".rar", ".7z", ".bat", ".cmd", ".ps1", ".lua"}

MAX_ARCHIVES = 80
MAX_MEMBERS_LIST = 400
MAX_MEMBER_PEEK = 64 * 1024
MAX_ARCHIVE_BYTES = 80 * 1024 * 1024  # skip huge archives for deep read
MAX_DEPTH = 5

PASSWORD_HINTS = (
    "password",
    "passwd",
    "pass_",
    "pw_",
    "encrypted",
    "locked",
)


def _scan_roots() -> list[Path]:
    home = Path.home()
    temp = Path(os.environ.get("TEMP", str(home / "AppData" / "Local" / "Temp")))
    return [
        p
        for p in [
            home / "Downloads",
            home / "Desktop",
            home / "Documents",
            temp,
            home / "AppData" / "Local" / "Temp",
            home / "AppData" / "Roaming",
            Path(r"C:\Cheats"),
            Path(r"C:\Bypass"),
            Path(r"C:\Tools"),
            Path(r"C:\Inject"),
            Path(r"D:\Cheats"),
            Path(r"D:\Downloads"),
        ]
        if p.exists()
    ]


def _all_sigs():
    return CHEAT_FILE_SIGNATURES + CLEANER_FILE_SIGNATURES


def _match_sig_blob(blob: str):
    """Return (signature, pattern) if blob matches a known cheat/cleaner pattern."""
    lower = blob.lower()
    for sig in _all_sigs():
        for pattern in sig.patterns:
            pl = pattern.lower().strip()
            if len(pl) < 4:
                continue
            if pl in lower or match_path(pattern, blob):
                return sig, pattern
    return None, None


def _archive_kind(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in {".tgz"}:
        return "tar"
    if ext == ".gz" and path.name.lower().endswith(".tar.gz"):
        return "tar"
    if ext in {".tar", ".bz2", ".xz"}:
        return "tar" if ext == ".tar" else ext.lstrip(".")
    return ext.lstrip(".") if ext else "unknown"


def _looks_like_zip(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            magic = fh.read(4)
        return magic.startswith(b"PK")
    except OSError:
        return False


def _looks_like_rar(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            magic = fh.read(7)
        return magic.startswith(b"Rar!\x1a\x07") or magic.startswith(b"Rar!")
    except OSError:
        return False


def _looks_like_7z(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            magic = fh.read(6)
        return magic.startswith(b"7z\xbc\xaf\x27\x1c")
    except OSError:
        return False


class ArchiveScanner:
    name = "Archive Scanner"

    def scan(self, result: ScanResult) -> None:
        seen: set[str] = set()
        archives_checked = 0

        for root in _scan_roots():
            per_root = max(15, MAX_ARCHIVES // max(len(_scan_roots()), 1))
            try:
                for path in iter_files_limited(root, max_files=800, max_depth=MAX_DEPTH):
                    if archives_checked >= MAX_ARCHIVES:
                        return
                    ext = path.suffix.lower()
                    if ext not in ARCHIVE_EXTENSIONS and not path.name.lower().endswith(".tar.gz"):
                        continue
                    if is_whitelisted_path(path):
                        continue
                    if is_legit_cleaner_name(path.name):
                        continue

                    key = str(path).lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    archives_checked += 1
                    self._inspect_archive(path, result)
            except (OSError, PermissionError) as exc:
                result.errors.append(f"Archive scan error in {root}: {exc}")

        if archives_checked == 0:
            result.errors.append("Archive scanner found no archives in scan paths")

    def _inspect_archive(self, path: Path, result: ScanResult) -> None:
        lower_name = path.name.lower()
        kind = _archive_kind(path)

        # 1) Outer archive filename matches cheat/cleaner brand
        sig, pattern = _match_sig_blob(lower_name)
        if sig and pattern:
            result.add(
                Finding(
                    title=f"Suspicious archive name: {path.name}",
                    description=(
                        f"{sig.name} pattern found in archive filename — "
                        "cheats are often shipped as ZIP/RAR/7Z packs"
                    ),
                    severity=sig.severity if sig.severity != Severity.INFO else Severity.HIGH,
                    category=sig.category,
                    evidence=f"Archive '{path.name}' matched '{pattern}'",
                    path=str(path),
                    signature=f"archive_name:{pattern}",
                )
            )

        # Password-hint filenames (password_is_eulen.rar etc.)
        if any(h in lower_name for h in PASSWORD_HINTS) or "password_is_" in lower_name:
            result.add(
                Finding(
                    title=f"Password-hint archive: {path.name}",
                    description=(
                        "Archive name suggests a password-protected cheat pack "
                        "(common for Eulen and similar loaders)"
                    ),
                    severity=Severity.HIGH,
                    category=Category.CHEAT,
                    evidence=path.name,
                    path=str(path),
                    signature="archive_password_hint",
                )
            )

        # Random short name archives in Downloads/Desktop (rename-to-hide)
        stem = path.stem.lower()
        if (
            path.parent.name.lower() in {"downloads", "desktop", "temp", "tmp"}
            and len(stem) <= 10
            and is_random_cheat_filename(f"{stem}.exe")
        ):
            result.add(
                Finding(
                    title=f"Random-name archive: {path.name}",
                    description="Short random archive name in a common drop folder — often used to hide loaders",
                    severity=Severity.MEDIUM,
                    category=Category.SUSPICIOUS,
                    evidence=path.name,
                    path=str(path),
                    signature="archive_random_name",
                )
            )

        # 2) Deep inspect by format
        try:
            size = path.stat().st_size
        except OSError:
            return

        if size <= 0:
            return

        # Prefer real format over extension
        if _looks_like_zip(path) or kind == "zip":
            self._scan_zip(path, result, size)
            return
        if kind in {"tar", "tgz"} or path.name.lower().endswith(".tar.gz"):
            self._scan_tar(path, result, size)
            return
        if _looks_like_rar(path) or kind == "rar":
            self._flag_opaque(path, result, "RAR", size)
            return
        if _looks_like_7z(path) or kind == "7z":
            self._flag_opaque(path, result, "7Z", size)
            return
        if kind in {"cab", "iso", "gz", "bz2", "xz"}:
            # Outer name already checked; note presence if suspicious folder
            if any(tok in str(path).lower() for tok in ("cheat", "bypass", "inject", "spoofer", "fivem")):
                result.add(
                    Finding(
                        title=f"Archive in suspicious location: {path.name}",
                        description=f"{kind.upper()} archive found under a cheat/bypass-related path",
                        severity=Severity.MEDIUM,
                        category=Category.SUSPICIOUS,
                        evidence=str(path),
                        path=str(path),
                        signature=f"archive_location:{kind}",
                    )
                )

    def _flag_opaque(self, path: Path, result: ScanResult, fmt: str, size: int) -> None:
        """RAR/7Z: cannot unpack without extra tools — escalate when name already suspicious."""
        lower = path.name.lower()
        sig, pattern = _match_sig_blob(lower)
        if sig:
            return  # already flagged by outer name
        # Generic presence of executable-looking RAR/7Z in Downloads still worth noting if large enough
        if path.parent.name.lower() in {"downloads", "desktop", "temp", "tmp", "cheats", "bypass", "tools"}:
            if size >= 50_000:  # skip tiny junk
                result.add(
                    Finding(
                        title=f"{fmt} archive in drop folder: {path.name}",
                        description=(
                            f"{fmt} archives are commonly used to hide FiveM cheats. "
                            "Open and inspect manually if the name looks unfamiliar."
                        ),
                        severity=Severity.LOW,
                        category=Category.SUSPICIOUS,
                        evidence=f"{fmt} · {size} bytes · {path.parent}",
                        path=str(path),
                        signature=f"archive_opaque:{fmt.lower()}",
                    )
                )

    def _scan_zip(self, path: Path, result: ScanResult, size: int) -> None:
        if size > MAX_ARCHIVE_BYTES:
            result.add(
                Finding(
                    title=f"Large ZIP skipped deep scan: {path.name}",
                    description="Archive too large for automatic member inspection — review manually",
                    severity=Severity.LOW,
                    category=Category.SUSPICIOUS,
                    evidence=f"{size} bytes",
                    path=str(path),
                    signature="archive_too_large",
                )
            )
            return

        try:
            zf = zipfile.ZipFile(path, "r")
        except zipfile.BadZipFile:
            # Misnamed or corrupt — still note if name looked zip-like
            if path.suffix.lower() == ".zip":
                result.add(
                    Finding(
                        title=f"Unreadable / protected ZIP: {path.name}",
                        description=(
                            "ZIP could not be opened (corrupt or password-protected). "
                            "Cheats are often distributed as locked archives."
                        ),
                        severity=Severity.MEDIUM,
                        category=Category.SUSPICIOUS,
                        evidence="zipfile.BadZipFile",
                        path=str(path),
                        signature="archive_zip_locked",
                    )
                )
            return
        except (OSError, RuntimeError) as exc:
            result.errors.append(f"ZIP open failed {path}: {exc}")
            return

        with zf:
            # Password / encryption detection
            encrypted = any(info.flag_bits & 0x1 for info in zf.infolist()[:MAX_MEMBERS_LIST])
            if encrypted:
                result.add(
                    Finding(
                        title=f"Encrypted ZIP members: {path.name}",
                        description="ZIP contains password-protected entries — common cheat distribution method",
                        severity=Severity.HIGH,
                        category=Category.CHEAT,
                        evidence="ZIP encryption flag set on one or more members",
                        path=str(path),
                        signature="archive_zip_encrypted",
                    )
                )

            members = zf.namelist()[:MAX_MEMBERS_LIST]
            self._score_member_names(path, members, result, fmt="ZIP")

            # Peek text members for signature strings
            for name in members:
                lower = name.lower().replace("\\", "/")
                ext = Path(lower).suffix
                if ext not in INNER_TEXT_EXTS:
                    continue
                try:
                    info = zf.getinfo(name)
                    if info.file_size > MAX_MEMBER_PEEK * 4:
                        continue
                    raw = zf.read(name, pwd=None)[:MAX_MEMBER_PEEK]
                except RuntimeError:
                    # Likely password required
                    continue
                except (KeyError, OSError, zipfile.BadZipFile):
                    continue
                text = raw.decode("utf-8", errors="ignore").lower()
                sig, pattern = _match_sig_blob(f"{lower} {text}")
                if sig and pattern:
                    result.add(
                        Finding(
                            title=f"Cheat/cleaner content inside ZIP: {Path(name).name}",
                            description=f"{sig.description} (found inside archive member)",
                            severity=sig.severity,
                            category=sig.category,
                            evidence=f"{path.name} → {name} · matched '{pattern}'",
                            path=str(path),
                            signature=f"archive_zip_content:{pattern}",
                        )
                    )
                    break  # one strong content hit per archive is enough

            # Nested archives / exes inside
            nested = [
                m
                for m in members
                if Path(m.lower()).suffix in INNER_DANGER_EXTS
            ]
            dangerous_exe = [
                m
                for m in nested
                if Path(m.lower()).suffix in {".exe", ".dll", ".asi"}
            ]
            if dangerous_exe:
                # Escalate if any inner exe name matches cheat OR random rename pattern
                for m in dangerous_exe[:12]:
                    base = Path(m).name
                    sig, pattern = _match_sig_blob(base.lower())
                    if sig and pattern:
                        result.add(
                            Finding(
                                title=f"Cheat loader inside ZIP: {base}",
                                description=f"{sig.name} executable packed inside {path.name}",
                                severity=Severity.CRITICAL,
                                category=sig.category,
                                evidence=f"{path.name} → {m}",
                                path=str(path),
                                signature=f"archive_zip_exe:{pattern}",
                            )
                        )
                    elif is_random_cheat_filename(base):
                        result.add(
                            Finding(
                                title=f"Random-name EXE inside ZIP: {base}",
                                description="Random-name loader hidden inside an archive",
                                severity=Severity.HIGH,
                                category=Category.CHEAT,
                                evidence=f"{path.name} → {m}",
                                path=str(path),
                                signature="archive_zip_random_exe",
                            )
                        )

    def _scan_tar(self, path: Path, result: ScanResult, size: int) -> None:
        if size > MAX_ARCHIVE_BYTES:
            return
        try:
            with tarfile.open(path, "r:*") as tf:
                names = []
                for member in tf.getmembers()[:MAX_MEMBERS_LIST]:
                    if member.isfile():
                        names.append(member.name)
                self._score_member_names(path, names, result, fmt="TAR")
        except (tarfile.TarError, OSError) as exc:
            result.errors.append(f"TAR open failed {path}: {exc}")

    def _score_member_names(
        self,
        archive: Path,
        members: list[str],
        result: ScanResult,
        *,
        fmt: str,
    ) -> None:
        hit_patterns: list[str] = []
        hit_sig_name = ""
        hit_category = Category.SUSPICIOUS
        hit_severity = Severity.HIGH

        for name in members:
            lower = name.lower().replace("\\", "/")
            base = Path(lower).name
            sig, pattern = _match_sig_blob(lower)
            if sig and pattern:
                hit_patterns.append(f"{base}('{pattern}')")
                hit_sig_name = sig.name
                hit_category = sig.category
                hit_severity = sig.severity
                if len(hit_patterns) >= 5:
                    break

        if hit_patterns:
            result.add(
                Finding(
                    title=f"Cheat/cleaner files inside {fmt}: {archive.name}",
                    description=(
                        f"{hit_sig_name or 'Known pattern'} detected in archived filenames — "
                        "payload may be hidden until extracted"
                    ),
                    severity=hit_severity if hit_severity != Severity.INFO else Severity.HIGH,
                    category=hit_category,
                    evidence=f"{archive.name} contains: " + ", ".join(hit_patterns[:5]),
                    path=str(archive),
                    signature=f"archive_{fmt.lower()}_members",
                )
            )
            return

        # Generic: many .lua/.asi/.dll together in a small pack can be a FiveM menu dump
        exts = [Path(m.lower()).suffix for m in members]
        lua_count = sum(1 for e in exts if e == ".lua")
        dll_count = sum(1 for e in exts if e in {".dll", ".asi"})
        exe_count = sum(1 for e in exts if e == ".exe")
        if lua_count >= 3 and (dll_count + exe_count) >= 1:
            result.add(
                Finding(
                    title=f"Possible FiveM menu pack: {archive.name}",
                    description=(
                        "Archive contains multiple Lua scripts plus native/binary modules — "
                        "common layout for injected menus"
                    ),
                    severity=Severity.HIGH,
                    category=Category.FIVEM,
                    evidence=f"{lua_count} .lua · {dll_count} dll/asi · {exe_count} exe",
                    path=str(archive),
                    signature="archive_fivem_menu_layout",
                )
            )
