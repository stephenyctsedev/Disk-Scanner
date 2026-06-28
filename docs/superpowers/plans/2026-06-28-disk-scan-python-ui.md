# Disk Scanner Python UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert `disk_scan.ps1` to a single-file Python desktop app with a tkinter Treeview UI and package it as a standalone Windows EXE.

**Architecture:** `disk_scan.py` has three logical sections: `get_folder_size()` utility, a `Scanner` class that runs 7 scan steps and fires a progress callback after each one, and a `DiskScanApp` tkinter class that owns the window. The scanner runs on a daemon background thread; results populate the Treeview incrementally via `root.after(0, ...)` to keep the UI responsive.

**Tech Stack:** Python 3.x stdlib only — `tkinter`, `os`, `shutil`, `threading`, `pathlib`; PyInstaller for EXE packaging.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `disk_scan.py` | Create | Entire app — utility + scanner + UI |
| `tests/test_scanner.py` | Create | Unit tests for scanner logic |
| `build.bat` | Create | One-click PyInstaller EXE build |
| `disk_scan.spec` | Auto-generated | PyInstaller config (commit after first build) |

---

## Task 1: Project scaffold + `get_folder_size()`

**Files:**
- Create: `disk_scan.py`
- Create: `tests/test_scanner.py`

- [ ] **Step 1: Install pytest**

```
pip install pytest
```

- [ ] **Step 2: Write failing tests**

Create `tests/test_scanner.py`:

```python
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from disk_scan import get_folder_size


def test_get_folder_size_nonexistent():
    assert get_folder_size("C:/this/does/not/exist/12345") == 0.0


def test_get_folder_size_empty_dir(tmp_path):
    assert get_folder_size(str(tmp_path)) == 0.0


def test_get_folder_size_single_file(tmp_path):
    # 10 MB = 0.01 GB (rounded to 2dp)
    (tmp_path / "a.bin").write_bytes(b"x" * (10 * 1024 * 1024))
    assert get_folder_size(str(tmp_path)) == 0.01


def test_get_folder_size_nested(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.bin").write_bytes(b"x" * (10 * 1024 * 1024))
    (tmp_path / "a.bin").write_bytes(b"x" * (10 * 1024 * 1024))
    assert get_folder_size(str(tmp_path)) == 0.02
```

- [ ] **Step 3: Run tests — confirm they fail**

```
pytest tests/test_scanner.py -v
```

Expected: `ImportError` — `disk_scan` not found.

- [ ] **Step 4: Create `disk_scan.py` with `get_folder_size()` and stub `main()`**

```python
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
```

- [ ] **Step 5: Run tests — confirm all pass**

```
pytest tests/test_scanner.py -v
```

Expected: 4 PASSED.

- [ ] **Step 6: Commit**

```
git add disk_scan.py tests/test_scanner.py
git commit -m "feat: add get_folder_size utility with tests"
```

---

## Task 2: `Scanner` class skeleton + Step 1 (disk info)

**Files:**
- Modify: `disk_scan.py` — add constants + `Scanner` class
- Modify: `tests/test_scanner.py` — add Scanner tests

- [ ] **Step 1: Append failing tests to `tests/test_scanner.py`**

```python
from disk_scan import Scanner


def test_scanner_step1_calls_on_progress():
    calls = []

    def on_progress(step, total, label, category, entries):
        calls.append((step, total, category, entries))

    Scanner(on_progress=on_progress)._step1_disk_info()

    assert len(calls) == 1
    step, total, category, entries = calls[0]
    assert step == 1
    assert total == 7
    assert category == "C: Drive"
    assert len(entries) == 1
    name, size = entries[0]
    assert "Total" in name and "Used" in name and "Free" in name
    assert size == ""


def test_scanner_step1_populates_report():
    scanner = Scanner(on_progress=lambda *a: None)
    scanner._step1_disk_info()
    report = "\n".join(scanner.report_lines)
    assert "C: Disk Usage Report" in report
    assert "Total:" in report
```

- [ ] **Step 2: Run tests — confirm new ones fail**

```
pytest tests/test_scanner.py -v -k "scanner"
```

Expected: `ImportError` or `AttributeError` — `Scanner` not defined.

- [ ] **Step 3: Add module-level constants and `Scanner` class to `disk_scan.py`**

Add after `get_folder_size()`, before `main()`:

```python
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

    # Stubs — replaced in Tasks 3-5
    def _step2_user_folders(self): pass
    def _step3_appdata_caches(self): pass
    def _step4_games_programs(self): pass
    def _step5_windows_system(self): pass
    def _step6_node_modules(self): pass
    def _step7_downloads_recycle(self): pass
```

- [ ] **Step 4: Run tests — confirm all pass**

```
pytest tests/test_scanner.py -v
```

Expected: 6 PASSED.

- [ ] **Step 5: Commit**

```
git add disk_scan.py tests/test_scanner.py
git commit -m "feat: add Scanner class with disk info step"
```

---

## Task 3: Scanner Steps 2 & 3 — User Folders + AppData Caches

**Files:**
- Modify: `disk_scan.py` — replace `_step2_user_folders` and `_step3_appdata_caches` stubs
- Modify: `tests/test_scanner.py` — add tests

- [ ] **Step 1: Append failing tests**

```python
def test_scanner_step2_user_folders(tmp_path):
    (tmp_path / "Downloads").mkdir()
    (tmp_path / "Downloads" / "file.bin").write_bytes(b"x" * (10 * 1024 * 1024))
    (tmp_path / "Desktop").mkdir()  # empty — still reported

    calls = []
    Scanner(on_progress=lambda *a: calls.append(a), home=str(tmp_path))._step2_user_folders()

    _, _, _, category, entries = calls[0]
    assert category == "User Folders"
    names = [e[0] for e in entries]
    assert "Downloads" in names
    assert "Desktop" in names
    sizes = {e[0]: e[1] for e in entries}
    assert sizes["Downloads"] == "0.01 GB"
    assert sizes["Desktop"] == "0.0 GB"


def test_scanner_step3_appdata_skips_small(tmp_path):
    appdata = tmp_path / "AppData" / "Local"
    appdata.mkdir(parents=True)
    # 0.05 GB < threshold 0.1 GB — should be excluded
    (appdata / "tiny.bin").write_bytes(b"x" * int(0.05 * 1024 ** 3))

    calls = []
    Scanner(on_progress=lambda *a: calls.append(a), home=str(tmp_path))._step3_appdata_caches()

    _, _, _, category, entries = calls[0]
    assert category == "AppData Caches"
    # AppData Local (total) threshold is 0.1 GB — tiny file is below it
    names = [e[0] for e in entries]
    assert "AppData Local (total)" not in names
```

- [ ] **Step 2: Run tests — confirm they fail**

```
pytest tests/test_scanner.py -v -k "step2 or step3"
```

Expected: AttributeError (stubs return None).

- [ ] **Step 3: Replace stubs in `disk_scan.py`**

Replace `_step2_user_folders` and `_step3_appdata_caches` stubs with:

```python
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
```

- [ ] **Step 4: Run tests — confirm all pass**

```
pytest tests/test_scanner.py -v
```

Expected: 8 PASSED.

- [ ] **Step 5: Commit**

```
git add disk_scan.py tests/test_scanner.py
git commit -m "feat: implement user folders and AppData cache scan steps"
```

---

## Task 4: Scanner Steps 4 & 5 — Games/Programs + Windows System

**Files:**
- Modify: `disk_scan.py` — replace `_step4_games_programs` and `_step5_windows_system` stubs
- Modify: `tests/test_scanner.py` — add tests

- [ ] **Step 1: Append failing tests**

```python
def test_scanner_step4_games_programs(tmp_path):
    # Simulate a Programs subfolder under AppData\Local\Programs
    progs = tmp_path / "AppData" / "Local" / "Programs"
    app_dir = progs / "MyApp"
    app_dir.mkdir(parents=True)
    # Write 1 GB worth of data (1 file × 1 GB)
    (app_dir / "data.bin").write_bytes(b"x" * (1024 ** 3))

    calls = []
    Scanner(on_progress=lambda *a: calls.append(a), home=str(tmp_path))._step4_games_programs()

    _, _, _, category, entries = calls[0]
    assert category == "Games / Programs"
    names = [e[0] for e in entries]
    assert any("MyApp" in n for n in names)


def test_scanner_step5_windows_system_runs():
    # Just verify it completes and calls on_progress — real paths may or may not exist
    calls = []
    Scanner(on_progress=lambda *a: calls.append(a))._step5_windows_system()
    assert len(calls) == 1
    _, _, _, category, _ = calls[0]
    assert category == "Windows System"
```

- [ ] **Step 2: Run tests — confirm new ones fail**

```
pytest tests/test_scanner.py -v -k "step4 or step5"
```

Expected: AttributeError (stubs).

- [ ] **Step 3: Replace stubs in `disk_scan.py`**

```python
    def _step4_games_programs(self):
        all_paths = (
            [pathlib.Path(p) for p in GAME_PATHS_ABS]
            + [self.home / p for p in GAME_PATHS_HOME]
        )
        entries = []
        self.report_lines.append("=== Games / Installed Programs ===")
        for base in all_paths:
            if not base.exists():
                continue
            try:
                subs = sorted(base.iterdir(), key=lambda p: p.name)
            except PermissionError:
                continue
            total_sz = 0
            sub_entries = []
            for sub in subs:
                if not sub.is_dir():
                    continue
                sz = get_folder_size(str(sub))
                if sz > 0.5:
                    sub_entries.append((f"  {sub.name}", f"{sz} GB"))
                    total_sz += sz
            if total_sz > 0.5:
                entries.append((f"{base}  (Total: {round(total_sz, 1)} GB)", ""))
                entries.extend(sub_entries)
                self.report_lines.append(f"  {base} (Total: {round(total_sz, 1)} GB)")
                for name, sz in sub_entries:
                    self.report_lines.append(f"    - {name.strip()}: {sz}")
        self.report_lines.append("")
        self._emit(4, "Scanning games and programs...", "Games / Programs", entries)

    def _step5_windows_system(self):
        entries = []
        self.report_lines.append("=== Windows System ===")
        for label, path_str in [
            ("Windows\\Temp",                  r"C:\Windows\Temp"),
            ("Windows\\WinSxS (DISM cleanable)", r"C:\Windows\WinSxS"),
            ("Windows\\Installer",             r"C:\Windows\Installer"),
        ]:
            p = pathlib.Path(path_str)
            if p.exists():
                sz = get_folder_size(str(p))
                if sz > 0:
                    entries.append((label, f"{sz} GB"))
                    self.report_lines.append(f"  {path_str}: {sz} GB")
        self.report_lines.append("")
        self._emit(5, "Scanning Windows system folders...", "Windows System", entries)
```

- [ ] **Step 4: Run tests — confirm all pass**

```
pytest tests/test_scanner.py -v
```

Expected: 10 PASSED.

- [ ] **Step 5: Commit**

```
git add disk_scan.py tests/test_scanner.py
git commit -m "feat: implement games/programs and Windows system scan steps"
```

---

## Task 5: Scanner Steps 6 & 7 — node_modules + Downloads/Recycle Bin

**Files:**
- Modify: `disk_scan.py` — replace `_step6_node_modules` and `_step7_downloads_recycle` stubs
- Modify: `tests/test_scanner.py` — add tests

- [ ] **Step 1: Append failing tests**

```python
def test_scanner_step6_node_modules_found(tmp_path):
    proj = tmp_path / "myproject"
    nm = proj / "node_modules" / "some-pkg"
    nm.mkdir(parents=True)
    (nm / "index.js").write_bytes(b"x" * (10 * 1024 * 1024))  # 10 MB

    calls = []
    Scanner(on_progress=lambda *a: calls.append(a), home=str(tmp_path))._step6_node_modules()

    _, _, _, category, entries = calls[0]
    assert category == "node_modules"
    assert len(entries) >= 1
    assert any("node_modules" in e[0] for e in entries)


def test_scanner_step7_downloads_top_files(tmp_path):
    dl = tmp_path / "Downloads"
    dl.mkdir()
    for i in range(12):
        (dl / f"file{i}.bin").write_bytes(b"x" * (i * 1024 * 1024))  # i MB each

    calls = []
    Scanner(on_progress=lambda *a: calls.append(a), home=str(tmp_path))._step7_downloads_recycle()

    _, _, _, category, entries = calls[0]
    assert category == "Downloads & Recycle Bin"
    # At most 10 download entries + 1 Recycle Bin entry
    download_entries = [e for e in entries if "Recycle" not in e[0]]
    assert len(download_entries) <= 10
    # Entries are sorted largest first
    sizes = [float(e[1].replace(" GB", "")) for e in download_entries]
    assert sizes == sorted(sizes, reverse=True)
```

- [ ] **Step 2: Run tests — confirm new ones fail**

```
pytest tests/test_scanner.py -v -k "step6 or step7"
```

Expected: AttributeError (stubs).

- [ ] **Step 3: Replace stubs in `disk_scan.py`**

```python
    def _step6_node_modules(self):
        nm_sizes = []
        home_str = str(self.home)
        try:
            for dirpath, dirnames, _ in os.walk(home_str, onerror=lambda e: None):
                rel = os.path.relpath(dirpath, home_str)
                depth = 0 if rel == "." else rel.count(os.sep) + 1
                if depth > 5:
                    dirnames[:] = []
                    continue
                if "node_modules" in dirnames:
                    nm_path = os.path.join(dirpath, "node_modules")
                    nm_sizes.append((nm_path, get_folder_size(nm_path)))
                    dirnames.remove("node_modules")  # don't descend into it
        except Exception:
            pass
        nm_sizes.sort(key=lambda x: x[1], reverse=True)
        entries = [(p, f"{sz} GB") for p, sz in nm_sizes[:5]]
        self.report_lines.append("=== node_modules (top 5) ===")
        for name, size in entries:
            self.report_lines.append(f"  {name}: {size}")
        self.report_lines.append("")
        self._emit(6, "Scanning node_modules...", "node_modules", entries)

    def _step7_downloads_recycle(self):
        entries = []
        self.report_lines.append("=== Downloads — Largest Files (top 10) ===")
        dl = self.home / "Downloads"
        if dl.exists():
            files = []
            for dirpath, _, filenames in os.walk(str(dl), onerror=lambda e: None):
                for fname in filenames:
                    fp = os.path.join(dirpath, fname)
                    try:
                        files.append((fname, os.path.getsize(fp)))
                    except OSError:
                        pass
            files.sort(key=lambda x: x[1], reverse=True)
            for name, size in files[:10]:
                sz = round(size / (1024 ** 3), 2)
                entries.append((name, f"{sz} GB"))
                self.report_lines.append(f"  {name}: {sz} GB")
        self.report_lines.append("")
        self.report_lines.append("=== Recycle Bin ===")
        rb_total = 0
        try:
            rb = pathlib.Path(r"C:\$Recycle.Bin")
            if rb.exists():
                for dirpath, _, filenames in os.walk(str(rb), onerror=lambda e: None):
                    for fname in filenames:
                        try:
                            rb_total += os.path.getsize(os.path.join(dirpath, fname))
                        except OSError:
                            pass
        except Exception:
            pass
        rb_gb = round(rb_total / (1024 ** 3), 2)
        entries.append(("Recycle Bin", f"{rb_gb} GB"))
        self.report_lines.append(f"  Recycle Bin: {rb_gb} GB")
        self._emit(7, "Scanning Downloads and Recycle Bin...", "Downloads & Recycle Bin", entries)
```

- [ ] **Step 4: Run tests — confirm all pass**

```
pytest tests/test_scanner.py -v
```

Expected: 12 PASSED.

- [ ] **Step 5: Commit**

```
git add disk_scan.py tests/test_scanner.py
git commit -m "feat: implement node_modules and downloads/recycle bin scan steps"
```

---

## Task 6: Scanner `write_report()`

**Files:**
- Modify: `disk_scan.py` — add `write_report()` to `Scanner`
- Modify: `tests/test_scanner.py` — add test

- [ ] **Step 1: Append failing test**

```python
def test_scanner_write_report(tmp_path):
    scanner = Scanner(on_progress=lambda *a: None)
    scanner._step1_disk_info()  # populate report_lines
    report_file = tmp_path / "disk_report.txt"
    scanner.write_report(str(report_file))
    content = report_file.read_text(encoding="utf-8")
    assert "C: Disk Usage Report" in content
    assert "Scan complete" in content
```

- [ ] **Step 2: Run test — confirm it fails**

```
pytest tests/test_scanner.py -v -k "write_report"
```

Expected: AttributeError — `Scanner` has no `write_report`.

- [ ] **Step 3: Add `write_report()` to `Scanner` in `disk_scan.py`**

Add as the last method of `Scanner`, before `_step2_user_folders`:

```python
    def write_report(self, path: str) -> None:
        lines = self.report_lines + ["", f"Scan complete! Report saved to: {path}"]
        with open(path, "w", encoding="utf-8", errors="replace") as f:
            f.write("\n".join(lines))
```

- [ ] **Step 4: Run tests — confirm all pass**

```
pytest tests/test_scanner.py -v
```

Expected: 13 PASSED.

- [ ] **Step 5: Commit**

```
git add disk_scan.py tests/test_scanner.py
git commit -m "feat: add write_report to Scanner"
```

---

## Task 7: `DiskScanApp` — window, buttons, and progress bar

**Files:**
- Modify: `disk_scan.py` — add `_report_path()` + `DiskScanApp` class, update `main()`

No automated tests for UI — manual verification.

- [ ] **Step 1: Add `_report_path()` and `DiskScanApp` skeleton to `disk_scan.py`**

Add after the `Scanner` class, before `main()`:

```python
def _report_path() -> str:
    if getattr(sys, "frozen", False):
        base = pathlib.Path(sys.executable).parent
    else:
        base = pathlib.Path(__file__).parent
    return str(base / "disk_report.txt")


class DiskScanApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Disk Usage Scanner")
        self.root.geometry("900x650")
        self.root.minsize(600, 400)
        self.scanner: "Scanner | None" = None
        self._build_ui()

    def _build_ui(self):
        bar = tk.Frame(self.root, pady=6)
        bar.pack(fill=tk.X, padx=10)

        self.btn_scan = tk.Button(bar, text="Scan Now", width=12,
                                  command=self._start_scan)
        self.btn_scan.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_save = tk.Button(bar, text="Save Report", width=12,
                                  state=tk.DISABLED, command=self._save_report)
        self.btn_save.pack(side=tk.LEFT)

        prog_frame = tk.Frame(self.root, padx=10)
        prog_frame.pack(fill=tk.X, pady=(0, 4))

        self.progress = ttk.Progressbar(prog_frame, maximum=Scanner.STEPS,
                                        mode="determinate")
        self.progress.pack(fill=tk.X)

        self.lbl_status = tk.Label(prog_frame, text="Press 'Scan Now' to begin.",
                                   anchor="w")
        self.lbl_status.pack(fill=tk.X)

    def _start_scan(self):
        pass  # wired up in Task 9

    def _save_report(self):
        pass  # wired up in Task 9
```

Replace `main()` with:

```python
def main():
    root = tk.Tk()
    DiskScanApp(root)
    root.mainloop()
```

- [ ] **Step 2: Run the app manually**

```
python disk_scan.py
```

Expected: window opens with "Scan Now" and "Save Report" (disabled) buttons and a progress bar. Clicking "Scan Now" does nothing yet. Close the window to exit.

- [ ] **Step 3: Commit**

```
git add disk_scan.py
git commit -m "feat: add DiskScanApp UI skeleton with buttons and progress bar"
```

---

## Task 8: `DiskScanApp` — Treeview with collapsible sections

**Files:**
- Modify: `disk_scan.py` — add Treeview to `_build_ui`, add `_update_ui()`

- [ ] **Step 1: Add Treeview to `_build_ui` in `DiskScanApp`**

Append to the end of `_build_ui()` (after the progress label):

```python
        tree_frame = tk.Frame(self.root)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.tree = ttk.Treeview(tree_frame, columns=("size",),
                                 show="tree headings")
        self.tree.heading("#0", text="Name", anchor=tk.W)
        self.tree.heading("size", text="Size", anchor=tk.E)
        self.tree.column("#0", stretch=True, minwidth=400)
        self.tree.column("size", width=100, anchor=tk.E, stretch=False)

        scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL,
                               command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self._category_nodes: dict[str, str] = {}
```

- [ ] **Step 2: Add `_update_ui()` method to `DiskScanApp`**

```python
    def _update_ui(self, step: int, total: int, label: str,
                   category: str, entries: list) -> None:
        self.progress["value"] = step
        self.lbl_status.config(text=f"Step {step}/{total}: {label}")
        parent = self.tree.insert("", tk.END, text=category,
                                  open=(step == 1))
        self._category_nodes[category] = parent
        for name, size in entries:
            self.tree.insert(parent, tk.END, text=name, values=(size,))
```

- [ ] **Step 3: Run the app manually to verify Treeview layout**

```
python disk_scan.py
```

Expected: window shows the Treeview with "Name" and "Size" columns and a scrollbar. It's empty until a scan runs. Clicking "Scan Now" still does nothing.

- [ ] **Step 4: Commit**

```
git add disk_scan.py
git commit -m "feat: add collapsible Treeview to DiskScanApp"
```

---

## Task 9: Wire Scanner to UI — background thread + incremental updates

**Files:**
- Modify: `disk_scan.py` — implement `_start_scan()`, `_save_report()`, add `_on_progress()` and `_on_scan_complete()`

- [ ] **Step 1: Replace `_start_scan()` stub in `DiskScanApp`**

```python
    def _start_scan(self):
        self.tree.delete(*self.tree.get_children())
        self._category_nodes.clear()
        self.progress["value"] = 0
        self.lbl_status.config(text="Starting scan...")
        self.btn_scan.config(state=tk.DISABLED)
        self.btn_save.config(state=tk.DISABLED)
        self.scanner = Scanner(on_progress=self._on_progress)
        threading.Thread(target=self._run_scan, daemon=True).start()

    def _run_scan(self):
        self.scanner.run()
        self.root.after(0, self._on_scan_complete)

    def _on_progress(self, step, total, label, category, entries):
        self.root.after(0, self._update_ui, step, total, label, category, entries)

    def _on_scan_complete(self):
        self.lbl_status.config(text="Scan complete!")
        self.btn_scan.config(state=tk.NORMAL)
        self.btn_save.config(state=tk.NORMAL)
```

- [ ] **Step 2: Replace `_save_report()` stub in `DiskScanApp`**

```python
    def _save_report(self):
        if self.scanner is None:
            return
        path = _report_path()
        try:
            self.scanner.write_report(path)
            messagebox.showinfo("Saved", f"Report saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save report:\n{e}")
```

- [ ] **Step 3: Run full end-to-end test manually**

```
python disk_scan.py
```

Expected:
- Click "Scan Now" — progress bar increments through 7 steps; status label updates each step; Treeview categories populate one by one as each step completes.
- "C: Drive" category auto-expands; others start collapsed. Click a category to expand/collapse.
- On completion: "Scan complete!" in status; "Save Report" button enables.
- Click "Save Report" — confirmation dialog shows path to `disk_report.txt`; file exists on disk with full report.

- [ ] **Step 4: Run all automated tests to confirm nothing broken**

```
pytest tests/test_scanner.py -v
```

Expected: 13 PASSED.

- [ ] **Step 5: Commit**

```
git add disk_scan.py
git commit -m "feat: wire Scanner to DiskScanApp with background thread and incremental Treeview updates"
```

---

## Task 10: `build.bat` + PyInstaller EXE

**Files:**
- Create: `build.bat`

- [ ] **Step 1: Install PyInstaller**

```
pip install pyinstaller
```

- [ ] **Step 2: Create `build.bat`**

```bat
@echo off
echo Building DiskScan.exe...
pyinstaller --onefile --windowed --name "DiskScan" disk_scan.py
echo.
echo Done! EXE is in the dist\ folder.
pause
```

- [ ] **Step 3: Run the build**

Double-click `build.bat`, or run in terminal:

```
build.bat
```

Expected output ends with:
```
Building EXE from EXE-00.toc
Appending PKG archive to EXE
Building EXE from EXE-00.toc completed successfully.
```

`dist\DiskScan.exe` is created (~8–12 MB).

- [ ] **Step 4: Test the EXE**

Double-click `dist\DiskScan.exe`.

Expected: app opens with no console window. Run a full scan and save report — identical behaviour to `python disk_scan.py`.

- [ ] **Step 5: Commit spec file and build script**

```
git add build.bat disk_scan.spec
git commit -m "feat: add build.bat and PyInstaller spec for EXE packaging"
```

---

## Done

Final file structure:
```
Disk_scan/
├── disk_scan.py          # complete app
├── disk_scan.spec        # PyInstaller config
├── build.bat             # one-click EXE build
├── disk_report.txt       # generated on scan
├── dist/
│   └── DiskScan.exe      # distributable EXE
└── tests/
    └── test_scanner.py   # 13 unit tests
```
