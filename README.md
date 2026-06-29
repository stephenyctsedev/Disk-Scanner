# DiskScan

Windows disk usage scanner with a tkinter UI. Scans the C: drive and shows results in a collapsible tree; saves a text report.

## Requirements

Python 3.x — stdlib only, no pip installs needed.

## Run from source

```
python disk_scan.py
```

## What it scans

1. C: drive total / used / free
2. User folders — Downloads, Desktop, Documents, Videos, Pictures, Music, OneDrive
3. AppData caches — npm, pip, Conda, Chrome, Discord, Spotify, Teams, NVIDIA DXCache, Ollama, Cursor
4. Games / programs — Program Files, C:\Games, Epic Games, Riot Games, SteamLibrary
5. Windows system — Temp, WinSxS, Installer
6. node_modules — top 5 largest found within home directory (max depth 5)
7. Downloads largest files (top 10) + Recycle Bin

## Rebuild EXE

Double-click `build.bat` and accept the admin prompt.  
Output: `dist\DiskScan.exe`

> Note: build.bat adds a Windows Defender exclusion for the `dist\` folder to prevent false-positive quarantine.

## Report

After scanning, click **Save Report** to write `disk_report.txt` next to the EXE (or script when running from source).
