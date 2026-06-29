# DiskScan — README and EXE Build Design

**Date:** 2026-06-28  
**Status:** Approved

## Overview

Add a lean personal-use README to the DiskScan repo and produce the EXE via the existing `build.bat`.

## README

Single `README.md` at repo root. Sections: what it is, Python requirements (stdlib only), how to run from source, what the 7 scan categories are, how to rebuild the EXE, and where the report is saved. No license, badges, or contribution sections — personal tool.

## EXE Build

Run `build.bat` (requires admin). It:
1. Adds a Windows Defender exclusion for `dist/` to prevent false-positive quarantine
2. Runs `pyinstaller --onefile --windowed --name DiskScan disk_scan.py`
3. Confirms `dist\DiskScan.exe` was produced

Output: `dist\DiskScan.exe` (gitignored).
