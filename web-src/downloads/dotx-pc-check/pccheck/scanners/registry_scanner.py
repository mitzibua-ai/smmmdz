from __future__ import annotations

import re
import winreg
from datetime import datetime, timezone

from pccheck.models import Category, Finding, ScanResult, Severity
from pccheck.signatures import CHEAT_FILE_SIGNATURES, CLEANER_FILE_SIGNATURES, SUSPICIOUS_FILENAMES

BAM_PATHS = [
  r"SYSTEM\CurrentControlSet\Services\bam\State\UserSettings",
  r"SYSTEM\CurrentControlSet\Services\dam\State\UserSettings",
]

RUN_KEYS = [
  (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
  (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
  (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
]

# FILETIME epoch offset
FILETIME_EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)


def _filetime_to_datetime(ft: int) -> datetime | None:
  if ft <= 0:
    return None
  try:
    return FILETIME_EPOCH + __import__("datetime").timedelta(microseconds=ft / 10)
  except (OverflowError, ValueError):
    return None


def _match_suspicious_path(path: str) -> tuple[str, str, Severity, Category] | None:
  lower = path.lower()
  all_sigs = CHEAT_FILE_SIGNATURES + CLEANER_FILE_SIGNATURES
  for sig in all_sigs:
    for pattern in sig.patterns:
      if pattern.lower() in lower:
        return sig.name, pattern, sig.severity, sig.category
  for sus in SUSPICIOUS_FILENAMES:
    if sus in lower:
      return "Suspicious path", sus, Severity.MEDIUM, Category.SUSPICIOUS
  return None


class RegistryScanner:
  name = "Registry Scanner"

  def scan(self, result: ScanResult) -> None:
    self._scan_bam(result)
    self._scan_run_keys(result)

  def _scan_bam(self, result: ScanResult) -> None:
    seen: set[str] = set()
    for reg_path in BAM_PATHS:
      try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path) as users_key:
          i = 0
          while True:
            try:
              sid = winreg.EnumKey(users_key, i)
              with winreg.OpenKey(users_key, sid) as sid_key:
                j = 0
                while True:
                  try:
                    name, value, _ = winreg.EnumValue(sid_key, j)
                    # BAM values are binary with path embedded
                    if isinstance(value, bytes):
                      try:
                        path = value.decode("utf-16-le", errors="ignore")
                      except Exception:
                        path = repr(value)
                    else:
                      path = str(value)

                    # Extract executable path from BAM value
                    path_match = re.search(r"([A-Za-z]:\\[^\x00]+)", path)
                    clean_path = path_match.group(1) if path_match else name

                    hit = _match_suspicious_path(clean_path)
                    if hit and clean_path not in seen:
                      seen.add(clean_path)
                      sig_name, pattern, severity, category = hit
                      result.add(
                        Finding(
                          title=f"BAM execution record: {sig_name}",
                          description="Program was executed recently (Background Activity Moderator)",
                          severity=severity,
                          category=category,
                          evidence=f"BAM entry — matched '{pattern}'",
                          path=clean_path,
                          signature=pattern,
                        )
                      )
                    j += 1
                  except OSError:
                    break
              i += 1
            except OSError:
              break
      except (OSError, PermissionError) as exc:
        if getattr(exc, "winerror", None) != 2:
          result.errors.append(f"BAM scan ({reg_path}): {exc}")

  def _scan_run_keys(self, result: ScanResult) -> None:
    seen: set[str] = set()
    for hive, subkey in RUN_KEYS:
      try:
        with winreg.OpenKey(hive, subkey) as key:
          i = 0
          while True:
            try:
              name, value, _ = winreg.EnumValue(key, i)
              val_str = str(value)
              hit = _match_suspicious_path(val_str) or _match_suspicious_path(name)
              if hit and val_str not in seen:
                seen.add(val_str)
                sig_name, pattern, severity, category = hit
                result.add(
                  Finding(
                    title=f"Autorun entry: {sig_name}",
                    description="Suspicious program in Windows startup (Run key)",
                    severity=severity,
                    category=category,
                    evidence=f"Run key '{name}' — matched '{pattern}'",
                    path=val_str,
                    signature=pattern,
                  )
                )
              i += 1
            except OSError:
              break
      except (OSError, PermissionError) as exc:
        result.errors.append(f"Run key scan ({subkey}): {exc}")
