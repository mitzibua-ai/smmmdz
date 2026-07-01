from __future__ import annotations

import ctypes
import ctypes.wintypes as wt

from pccheck.models import Category, Finding, ScanResult, Severity
from pccheck.signatures import CHEAT_PROCESS_SIGNATURES
from pccheck.utils.pe import is_random_cheat_filename

TH32CS_SNAPPROCESS = 0x00000002
MAX_PATH = 260


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD),
        ("cntUsage", wt.DWORD),
        ("th32ProcessID", wt.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wt.DWORD),
        ("cntThreads", wt.DWORD),
        ("th32ParentProcessID", wt.DWORD),
        ("pcPriClassBase", wt.LONG),
        ("dwFlags", wt.DWORD),
        ("szExeFile", wt.WCHAR * MAX_PATH),
    ]


def _enum_processes() -> list[tuple[int, str]]:
    kernel32 = ctypes.windll.kernel32
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        return []

    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    processes: list[tuple[int, str]] = []

    if kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
        while True:
            processes.append((entry.th32ProcessID, entry.szExeFile))
            if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                break

    kernel32.CloseHandle(snapshot)
    return processes


def _get_window_titles() -> list[str]:
    titles: list[str] = []
    user32 = ctypes.windll.user32

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def callback(hwnd, _lparam):
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            if buf.value.strip():
                titles.append(buf.value.lower())
        return True

    user32.EnumWindows(callback, 0)
    return titles


class ProcessScanner:
    name = "Process Scanner"

    def scan(self, result: ScanResult) -> None:
        try:
            processes = _enum_processes()
        except Exception as exc:
            result.errors.append(f"Process enumeration failed: {exc}")
            return

        try:
            window_titles = _get_window_titles()
        except Exception:
            window_titles = []

        seen: set[str] = set()

        for pid, exe_name in processes:
            lower_exe = exe_name.lower()

            # Detect running cheat with random rename (e.g. sz05e.exe)
            if is_random_cheat_filename(exe_name):
                key = f"random-proc:{lower_exe}"
                if key not in seen:
                    seen.add(key)
                    # Check if FiveM/GTA is also running — stronger signal
                    game_running = bool({"fivem.exe", "fivem_gtaprocess.exe", "gta5.exe"} & {p[1].lower() for p in processes})
                    severity = Severity.CRITICAL if game_running else Severity.HIGH
                    result.add(
                        Finding(
                            title="Random-name process running",
                            description=(
                                "Process uses short random name (cheats rename each run). "
                                + ("FiveM is running — likely active cheat." if game_running else "")
                            ),
                            severity=severity,
                            category=Category.CHEAT,
                            evidence=f"Process: {exe_name} (PID {pid})",
                            path=lower_exe,
                            signature="random_name_process",
                        )
                    )

            for sig in CHEAT_PROCESS_SIGNATURES:
                key = f"{sig.name}:{lower_exe}"
                if key in seen:
                    continue

                proc_hit = any(p in lower_exe for p in sig.process_names)
                title_hit = any(t in " ".join(window_titles) for t in sig.window_titles)

                if proc_hit or title_hit:
                    seen.add(key)
                    result.add(
                        Finding(
                            title=f"Active process: {sig.name}",
                            description=sig.description,
                            severity=sig.severity,
                            category=sig.category,
                            evidence=f"Process: {exe_name}",
                            path=lower_exe,
                            signature=sig.name,
                        )
                    )

        game_procs = {"fivem.exe", "fivem_gtaprocess.exe", "gta5.exe"}
        running = {p[1].lower() for p in processes}
        if game_procs & running:
            result.add(
                Finding(
                    title="FiveM/GTA process detected",
                    description="Game is currently running — memory injection checks are more relevant",
                    severity=Severity.INFO,
                    category=Category.FIVEM,
                    evidence=", ".join(sorted(game_procs & running)),
                )
            )
