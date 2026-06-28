# Disk Scanner — Python + tkinter UI Design

**Date:** 2026-06-28  
**Status:** Approved

## Overview

Convert `disk_scan.ps1` to a Python desktop application with a tkinter UI and package it as a single Windows EXE. The app scans the same 7 disk-usage categories as the original script, displays results in a collapsible Treeview, and saves a text report.

---

## Files

| File | Purpose |
|------|---------|
| `disk_scan.py` | Entire app — scanner logic + tkinter UI (~300 lines) |
| `disk_scan.spec` | PyInstaller spec (auto-generated, committed for reproducibility) |
| `build.bat` | One-click EXE rebuild helper |

No third-party runtime dependencies. Pure stdlib: `tkinter`, `os`, `pathlib`, `threading`, `shutil`, `math`.

---

## Architecture

Three logical sections inside `disk_scan.py`:

1. **`get_folder_size(path) -> float`** — recursive `os.walk()` summing file sizes, silently skips permission errors. Returns GB (2 decimal places).
2. **`Scanner` class** — runs the 7 scan steps, calls `on_progress(step, total, label, results)` after each step so the UI updates incrementally. Also writes `disk_report.txt`.
3. **`DiskScanApp` class** — owns the tkinter window, wires up the UI, spawns the `Scanner` on a background thread.

---

## Scan Logic

**User detection:** `pathlib.Path.home()` — no hardcoded usernames. All paths derived from the home directory.

**Disk info:** `shutil.disk_usage('C:\\')` for total/used/free.

**7 scan steps (same categories as PS1):**

| Step | Category | Detail |
|------|----------|--------|
| 1 | C: Drive | Total / Used / Free GB |
| 2 | User Folders | Downloads, Desktop, Documents, Videos, Pictures, Music, OneDrive |
| 3 | AppData Caches | npm, pip, conda, Chrome, Discord, Spotify, Teams, NVIDIA, Ollama, Cursor |
| 4 | Games / Program Files | Per-subfolder breakdown; skip entries < 0.5 GB |
| 5 | Windows System | Temp, WinSxS, Installer |
| 6 | node_modules | Depth-5 search under home, top 5 by size |
| 7 | Downloads & Recycle Bin | Top 10 largest files + Recycle Bin total |

Results with size 0 (or below threshold) are omitted, matching PS1 behaviour.

---

## UI Layout

Window: ~900×650px, resizable.

```
┌─────────────────────────────────────────────────┐
│  Disk Usage Scanner                             │
├─────────────────────────────────────────────────┤
│  [  Scan Now  ]   [  Save Report  ]            │
│                                                  │
│  ████████████░░░░░░  Step 3/7: AppData caches  │
├─────────────────────────────────────────────────┤
│  ▼ C: Drive                                     │
│      Total: 931 GB  |  Used: 412 GB  |  Free: 519 GB │
│  ▶ User Folders                                 │
│  ▶ AppData Caches                               │
│  ▶ Games / Program Files                        │
│  ▶ Windows System                               │
│  ▶ node_modules                                 │
│  ▶ Downloads & Recycle Bin                      │
└─────────────────────────────────────────────────┘
```

**Controls:**
- **Scan Now** — starts scan on background thread; disabled during scan.
- **Save Report** — writes `disk_report.txt`; enabled only after scan completes.
- **Progress bar** (`ttk.Progressbar`) — updates after each of the 7 steps; label shows step name.

**Treeview (`ttk.Treeview`):**
- Two columns: `Name` (left-aligned, stretches) and `Size` (right-aligned, ~80px fixed).
- Parent rows = 7 categories; child rows = individual path entries.
- C: Drive auto-expands on completion; all others start collapsed.
- Results populate incrementally per step (not all at once at the end).

---

## Threading

- `Scanner` runs on `threading.Thread(daemon=True)`.
- UI updates via `root.after(0, callback)` — marshals to main thread safely.
- Window close mid-scan: daemon thread exits with the process automatically.

---

## EXE Packaging

**Tool:** PyInstaller (install once: `pip install pyinstaller`)

**Build command:**
```
pyinstaller --onefile --windowed --name "DiskScan" disk_scan.py
```

- `--onefile` → single `dist/DiskScan.exe`, no folder structure needed.
- `--windowed` → no console/CMD window on launch.
- Output size: ~8–12 MB.
- `build.bat` wraps this command for one-click rebuilds.
