# DiskScan

Windows disk usage scanner with a tkinter UI. Scans the C: drive and shows results in a collapsible tree — every folder expands into a detail breakdown — and saves a text report.

## Requirements

Python 3.x — stdlib only, no pip installs needed.

## Run from source

```
python disk_scan.py
```

## What it scans

1. C: drive total / used / free
2. User folders — Downloads, Desktop, Documents, Videos, Pictures, Music, OneDrive
3. AppData caches — AppData Local (total), AppData Roaming, npm, pip, Conda, Chrome, Discord, Spotify, Teams, NVIDIA DXCache, Ollama, Cursor
4. Games / programs — Program Files, C:\Games, Epic Games, Riot Games, SteamLibrary
5. Windows system — Temp, WinSxS, Installer
6. node_modules — top 5 largest found within home directory (max depth 5)
7. Downloads largest files (top 10) + Recycle Bin

## Folder details

Every scanned folder (Documents, Downloads, each AppData cache, each installed
program, each `node_modules`, the Recycle Bin, …) expands in the tree into:

| Detail | Example |
|--------|---------|
| Contents | `Contents: 4,182 files in 611 subfolders` |
| Top level | `Top level: 12 folders, 3 files (2.4 MB)` |
| Average file size | `Average file size: 1.8 MB` |
| Newest / oldest file | `Newest file: 2026-08-27 21:04` |
| Largest subfolders | top 5, each with its own file count |
| Largest files | top 5, each expanding to full path + modified date |
| By file type | top 5 extensions with size, file count and % of the folder |

Each folder is walked **once** — the totals, counts, timestamps and breakdowns
all come from that single pass, so the extra detail costs no extra scan time.

Use **Expand All** / **Collapse All** in the toolbar to open or close the whole
tree at once.

## Rebuild EXE

Double-click `build.bat` and accept the admin prompt.  
Output: `dist\DiskScan.exe`

> Note: build.bat adds a Windows Defender exclusion for the `dist\` folder to prevent false-positive quarantine.

## Report

After scanning, click **Save Report**. Saves as `disk_report.txt` next to the EXE (or script when running from source). The report mirrors the tree, including every folder's detail breakdown as indented lines.
