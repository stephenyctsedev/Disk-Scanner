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


def main():
    pass  # UI added in Task 7


if __name__ == "__main__":
    main()
