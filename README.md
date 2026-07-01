# FiveM PC Check Scanner

A Windows forensic scanner for **FiveM server administrators** to detect cheats, injectors, and anti-forensic cleaners during PC checks (screenshares).

## What it detects

### Cheats
- **Susano**, **Macho**, **Eulen**, **RedEngine**, **Skript**, **HX**, **Tz Project**, **Gosth**
- Free cheats — generic executor/injector patterns, aimbot, ESP, noclip, money drop scripts
- Injection techniques — KDMapper, process hollowing, DLL injection

### Cleaners / Bypass tools
- **9z** and similar forensic cleaners
- Prefetch / BAM / USN journal wipers
- Screenshare bypass tools, HWID spoofers
- Evidence of prefetch clearing, log wiping, recently deleted cheat files

### Forensic artifacts
- **Prefetch** — execution history for cheat executables
- **BAM/DAM registry** — recent program execution records
- **Browser history** — visits to susano.dev, eulen.gg, unknowncheats.me, etc.
- **FiveM folders** — suspicious mods, Lua/JS exploit scripts
- **Running processes** — active cheat loaders

## Requirements

- **Windows 10/11**
- **Python 3.10+** (no external packages required — uses only the standard library)

## Usage

### Quick start (double-click)
```
run_scan.bat
```
When the scan finishes, **Notepad opens automatically** with the full result.

### Command line
```bash
# Full scan - opens Notepad when done
python main.py

# Fast scan (skips deep file walk)
python main.py --quick

# Don't open Notepad
python main.py --no-notepad
```

Report saved to: `reports/PC_CHECK_RESULT.txt`

**Run as Administrator** (right-click `run_scan.bat` → Run as administrator) for Prefetch and BAM registry access.

## Scan modules

| Module | What it checks |
|--------|----------------|
| Process Scanner | Running cheat/cleaner processes |
| Prefetch Scanner | `C:\Windows\Prefetch` execution artifacts |
| Registry Scanner | BAM/DAM execution logs, Run key autoruns |
| File Scanner | Downloads, Desktop, AppData, Temp for cheat files |
| FiveM Scanner | FiveM data folder, mods, Lua exploit scripts |
| **RPF Scanner** | Custom `.rpf` mods — weapons.meta, handling.meta, FiveM mods folder |
| Browser Scanner | Chrome/Edge/Firefox history for cheat sites |
| Cleaner Scanner | Anti-forensic tools, recycle bin, log gaps |

## Verdicts

| Verdict | Meaning |
|---------|---------|
| **CLEAN** | No significant findings |
| **REVIEW NEEDED** | Medium-severity items — manual review |
| **SUSPICIOUS** | High-severity findings |
| **CHEATING LIKELY** | Critical detections (known cheat or cleaner) |

## Adding custom signatures

Edit `pccheck/signatures.py`:

```python
FileSignature(
    "MyCheat",
    ("mycheat", "mycheat.exe", "mycheat_loader"),
    Severity.CRITICAL,
    Category.CHEAT,
    "Description of the cheat",
),
```

## Run as admin (recommended)

Some checks need elevated access:
- Prefetch folder (`C:\Windows\Prefetch`)
- BAM registry (`HKLM\SYSTEM\...\bam\`)
- Security event logs

Right-click `run_scan.bat` → **Run as administrator** for best results.

## Important notes

- This tool is for **server staff conducting legitimate PC checks** on players who consent to a screenshare.
- Close Chrome/Edge before scanning for best browser history results (browsers lock their DB files).
- False positives are possible on suspicious filenames — always review findings manually.
- Keep signatures updated as new cheats emerge.

## Project structure

```
fivem-pc-check/
├── main.py              # Entry point / CLI
├── run_scan.bat         # Windows launcher
├── pccheck/
│   ├── signatures.py    # Detection database (edit this)
│   ├── engine.py        # Scan orchestrator
│   ├── models.py        # Finding / result types
│   ├── scanners/        # Individual scan modules
│   └── report/          # HTML report builder
└── reports/             # Output (created on first scan)
```

## License

For educational and server administration use.
