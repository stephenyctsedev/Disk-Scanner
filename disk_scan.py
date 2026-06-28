import os
import sys
import pathlib
import shutil
import threading
import tkinter as tk
from tkinter import ttk, messagebox


def get_folder_size(path: str) -> float:
    total = 0
    for dirpath, _, filenames in os.walk(path, onerror=lambda e: None):
        for fname in filenames:
            fp = os.path.join(dirpath, fname)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return round(total / (1024 ** 3), 2)


APPDATA_PATHS = [
    ("AppData Local (total)",     r"AppData\Local"),
    ("AppData Roaming",           r"AppData\Roaming"),
    ("Temp (user)",               r"AppData\Local\Temp"),
    ("npm cache",                 r"AppData\Roaming\npm-cache"),
    ("pip cache",                 r"AppData\Local\pip\Cache"),
    ("Conda pkgs",                r"AppData\Local\conda\pkgs"),
    ("Google Chrome Cache",       r"AppData\Local\Google\Chrome\User Data\Default\Cache"),
    ("Discord Cache",             r"AppData\Roaming\discord\Cache"),
    ("Spotify Cache",             r"AppData\Local\Spotify\Storage"),
    ("Microsoft Teams Cache",     r"AppData\Roaming\Microsoft\Teams"),
    ("NVIDIA DXCache",            r"AppData\Local\NVIDIA\DXCache"),
    ("Ollama models",             r"AppData\Local\Ollama"),
    ("Cursor",                    r"AppData\Roaming\Cursor"),
]

GAME_PATHS_ABS = [
    r"C:\Program Files",
    r"C:\Program Files (x86)",
    r"C:\Games",
    r"C:\Epic Games",
    r"C:\Riot Games",
    r"C:\SteamLibrary",
    r"C:\Steam",
]

GAME_PATHS_HOME = [
    r"AppData\Local\Programs",
]


class Scanner:
    STEPS = 7

    def __init__(self, on_progress, home=None):
        self.on_progress = on_progress
        self.home = pathlib.Path(home) if home else pathlib.Path.home()
        self.report_lines = []

    def run(self):
        self._step1_disk_info()
        self._step2_user_folders()
        self._step3_appdata_caches()
        self._step4_games_programs()
        self._step5_windows_system()
        self._step6_node_modules()
        self._step7_downloads_recycle()

    def _emit(self, step, label, category, entries):
        self.on_progress(step, self.STEPS, label, category, entries)

    def _step1_disk_info(self):
        usage = shutil.disk_usage("C:\\")
        total = round(usage.total / (1024 ** 3), 1)
        used  = round(usage.used  / (1024 ** 3), 1)
        free  = round(usage.free  / (1024 ** 3), 1)
        line  = f"Total: {total} GB  |  Used: {used} GB  |  Free: {free} GB"
        self._emit(1, "Getting disk info...", "C: Drive", [(line, "")])
        self.report_lines += [
            "=============================================",
            " C: Disk Usage Report",
            "=============================================",
            f"Total: {total} GB | Used: {used} GB | Free: {free} GB",
            "",
        ]

    def _step2_user_folders(self):
        folders = ["Downloads", "Desktop", "Documents", "Videos",
                   "Pictures", "Music", "OneDrive"]
        entries = []
        self.report_lines.append("=== User Folders ===")
        for name in folders:
            path = self.home / name
            if path.exists():
                sz = get_folder_size(str(path))
                entries.append((name, f"{sz} GB"))
                self.report_lines.append(f"  {name}: {sz} GB")
        self.report_lines.append("")
        self._emit(2, "Scanning user folders...", "User Folders", entries)

    def _step3_appdata_caches(self):
        entries = []
        self.report_lines.append("=== AppData Caches ===")
        for name, subpath in APPDATA_PATHS:
            path = self.home / subpath
            if path.exists():
                sz = get_folder_size(str(path))
                if sz > 0.1:
                    entries.append((name, f"{sz} GB"))
                    self.report_lines.append(f"  {name}: {sz} GB")
        self.report_lines.append("")
        self._emit(3, "Scanning AppData caches...", "AppData Caches", entries)
    def _step4_games_programs(self): pass
    def _step5_windows_system(self): pass
    def _step6_node_modules(self): pass
    def _step7_downloads_recycle(self): pass


def main():
    pass  # UI added in Task 7


if __name__ == "__main__":
    main()
