from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

from pccheck.models import Category, Finding, ScanResult, Severity
from pccheck.signatures import BROWSER_FORUM_DOMAINS, CHEAT_WEBSITE_DOMAINS

CHROME_HISTORY = Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/User Data/Default/History"
EDGE_HISTORY = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Edge/User Data/Default/History"
FIREFOX_PROFILES = Path(os.environ.get("APPDATA", "")) / "Mozilla/Firefox/Profiles"


def _query_urls(db_path: Path, limit: int = 50000) -> list[str]:
  if not db_path.exists():
    return []
  # Copy to temp because browser locks the DB
  import shutil
  import tempfile

  tmp = Path(tempfile.gettempdir()) / f"pccheck_hist_{db_path.parent.parent.name}.db"
  try:
    shutil.copy2(db_path, tmp)
  except (OSError, PermissionError):
    return []

  urls: list[str] = []
  try:
    conn = sqlite3.connect(f"file:{tmp}?mode=ro", uri=True)
    cur = conn.cursor()
    cur.execute("SELECT url FROM urls ORDER BY last_visit_time DESC LIMIT ?", (limit,))
    urls = [row[0] for row in cur.fetchall() if row[0]]
    conn.close()
  except sqlite3.Error:
    pass
  finally:
    try:
      tmp.unlink(missing_ok=True)
    except OSError:
      pass
  return urls


def _scan_firefox() -> list[str]:
  urls: list[str] = []
  if not FIREFOX_PROFILES.exists():
    return urls
  for profile in FIREFOX_PROFILES.iterdir():
    if profile.is_dir():
      urls.extend(_query_urls(profile / "places.sqlite", limit=10000))
  return urls


class BrowserScanner:
  name = "Browser History Scanner"

  def scan(self, result: ScanResult) -> None:
    all_urls: list[str] = []
    all_urls.extend(_query_urls(CHROME_HISTORY))
    all_urls.extend(_query_urls(EDGE_HISTORY))
    all_urls.extend(_scan_firefox())

    if not all_urls:
      result.errors.append("No browser history accessible (browser may be open or none installed)")
      return

    seen: set[str] = set()
    combined = "\n".join(all_urls).lower()

    for domain in CHEAT_WEBSITE_DOMAINS:
      if domain.lower() in combined and domain not in seen:
        seen.add(domain)
        example = next((u for u in all_urls if domain.lower() in u.lower()), domain)
        result.add(
          Finding(
            title=f"Cheat website visit: {domain}",
            description="Browser history shows visit to known cheat provider site",
            severity=Severity.HIGH,
            category=Category.CHEAT,
            evidence=example[:200],
            path="Browser History",
            signature=domain,
          )
        )

    for domain in BROWSER_FORUM_DOMAINS:
      if domain.lower() in combined and domain not in seen:
        seen.add(domain)
        example = next((u for u in all_urls if domain.lower() in u.lower()), domain)
        result.add(
          Finding(
            title=f"Cheat forum visit: {domain}",
            description="Browser history shows visit to cheat forum (review context — not proof alone)",
            severity=Severity.LOW,
            category=Category.SUSPICIOUS,
            evidence=example[:200],
            path="Browser History",
            signature=domain,
          )
        )

    # Generic cheat search terms in URLs (require cheat-site context, skip video search pages)
    cheat_url_patterns = [
        (r"https?://[^/\s]*fivem[^/\s]*/.*cheat", "FiveM cheat download page"),
        (r"https?://[^/\s]*fivem[^/\s]*/.*hack", "FiveM hack download page"),
        (r"https?://[^/\s]*executor", "Lua executor download page"),
        (r"eulen\.gg", "Eulen-related page"),
        (r"susano\.dev", "Susano-related page"),
        (r"machocheats\.com", "Macho cheat page"),
    ]
    for pattern, desc in cheat_url_patterns:
      if re.search(pattern, combined, re.IGNORECASE) and pattern not in seen:
        seen.add(pattern)
        example = next(
          (u for u in all_urls if re.search(pattern, u, re.IGNORECASE)),
          pattern,
        )
        result.add(
          Finding(
            title="Suspicious browser activity",
            description=desc,
            severity=Severity.MEDIUM,
            category=Category.SUSPICIOUS,
            evidence=str(example)[:200],
            path="Browser History",
            signature=pattern,
          )
        )
