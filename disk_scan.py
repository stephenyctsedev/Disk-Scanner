import heapq
import os
import sys
import pathlib
import shutil
import threading
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox

GB = 1024 ** 3
TOP_N = 5


def human_size(num_bytes: float) -> str:
    """Format a byte count as B / KB / MB / GB / TB."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(size)} B"
            return f"{size:.1f} {unit}"
        size /= 1024


def plural(count: int, word: str) -> str:
    """'1 file' / '2 files' - keeps the detail rows reading naturally."""
    return f"{count:,} {word}" + ("" if count == 1 else "s")


def fmt_time(ts: float) -> str:
    """Format a POSIX timestamp as 'YYYY-MM-DD HH:MM', or '-' when missing."""
    if not ts:
        return "-"
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except (OSError, OverflowError, ValueError):
        return "-"


class FolderStats:
    """Everything one walk of a folder can tell us about it."""

    def __init__(self, path: str):
        self.path = path
        self.total_bytes = 0
        self.file_count = 0
        self.dir_count = 0
        self.top_level_dirs = 0
        self.top_level_files = 0
        self.root_file_bytes = 0
        self.newest_mtime = 0.0
        self.oldest_mtime = 0.0
        self.subdir_bytes: dict[str, int] = {}
        self.subdir_files: dict[str, int] = {}
        self.ext_bytes: dict[str, tuple[int, int]] = {}
        self._files_heap: list[tuple[int, str, float]] = []

    @property
    def size_gb(self) -> float:
        return round(self.total_bytes / GB, 2)

    @property
    def avg_file_bytes(self) -> float:
        return self.total_bytes / self.file_count if self.file_count else 0.0

    def top_subdirs(self, n: int = TOP_N) -> list[tuple[str, int]]:
        return sorted(self.subdir_bytes.items(), key=lambda kv: kv[1], reverse=True)[:n]

    def top_exts(self, n: int = TOP_N) -> list[tuple[str, tuple[int, int]]]:
        return sorted(self.ext_bytes.items(), key=lambda kv: kv[1][0], reverse=True)[:n]

    def largest_files(self, n: int = TOP_N) -> list[tuple[int, str, float]]:
        return sorted(self._files_heap, key=lambda f: f[0], reverse=True)[:n]


def scan_folder(path: str, top_n: int = TOP_N) -> FolderStats:
    """Walk `path` once, collecting sizes, counts, timestamps and breakdowns.

    Permission errors and vanished files are skipped silently, so a missing
    path simply yields an all-zero FolderStats.
    """
    stats = FolderStats(path)
    root = os.path.abspath(path)
    for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: None):
        stats.dir_count += len(dirnames)
        rel = os.path.relpath(dirpath, root)
        at_root = rel == os.curdir
        if at_root:
            stats.top_level_dirs = len(dirnames)
            stats.top_level_files = len(filenames)
            branch = ""
        else:
            branch = rel.split(os.sep)[0]
        for fname in filenames:
            fp = os.path.join(dirpath, fname)
            try:
                st = os.stat(fp)
            except OSError:
                continue
            size, mtime = st.st_size, st.st_mtime
            stats.file_count += 1
            stats.total_bytes += size
            if mtime > stats.newest_mtime:
                stats.newest_mtime = mtime
            if stats.oldest_mtime == 0.0 or mtime < stats.oldest_mtime:
                stats.oldest_mtime = mtime
            if branch:
                stats.subdir_bytes[branch] = stats.subdir_bytes.get(branch, 0) + size
                stats.subdir_files[branch] = stats.subdir_files.get(branch, 0) + 1
            else:
                stats.root_file_bytes += size
            ext = os.path.splitext(fname)[1].lower() or "(no extension)"
            prev_b, prev_c = stats.ext_bytes.get(ext, (0, 0))
            stats.ext_bytes[ext] = (prev_b + size, prev_c + 1)
            if top_n:
                heapq.heappush(stats._files_heap, (size, fp, mtime))
                if len(stats._files_heap) > top_n:
                    heapq.heappop(stats._files_heap)
    return stats


def get_folder_size(path: str) -> float:
    """Total size of `path` in GB, rounded to 2 decimal places."""
    return scan_folder(path, top_n=0).size_gb


def folder_details(stats: FolderStats, top_n: int = TOP_N,
                   include_types: bool = True) -> list:
    """Build the nested detail entries shown under a folder in the tree."""
    if stats.file_count == 0:
        return [("Empty (no readable files)", "")]

    details: list = [
        (f"Contents: {plural(stats.file_count, 'file')} in "
         f"{plural(stats.dir_count, 'subfolder')}", ""),
        (f"Top level: {plural(stats.top_level_dirs, 'folder')}, "
         f"{plural(stats.top_level_files, 'file')} "
         f"({human_size(stats.root_file_bytes)})", ""),
        (f"Average file size: {human_size(stats.avg_file_bytes)}", ""),
        (f"Newest file: {fmt_time(stats.newest_mtime)}", ""),
        (f"Oldest file: {fmt_time(stats.oldest_mtime)}", ""),
    ]

    subs = stats.top_subdirs(top_n)
    if subs:
        children = [
            (f"{name}  ({plural(stats.subdir_files.get(name, 0), 'file')})",
             human_size(size))
            for name, size in subs
        ]
        details.append((f"Largest subfolders (top {len(children)})", "", children))

    files = stats.largest_files(top_n)
    if files:
        children = [
            (os.path.basename(fp), human_size(size),
             [(f"Path: {fp}", ""), (f"Modified: {fmt_time(mtime)}", "")])
            for size, fp, mtime in files
        ]
        details.append((f"Largest files (top {len(children)})", "", children))

    if include_types:
        exts = stats.top_exts(top_n)
        if exts:
            children = [
                (f"{ext}  ({plural(count, 'file')}, "
                 f"{(size / stats.total_bytes * 100) if stats.total_bytes else 0:.0f}%)",
                 human_size(size))
                for ext, (size, count) in exts
            ]
            details.append((f"By file type (top {len(children)})", "", children))

    return details


def entry_report_lines(entries, indent: str = "  ") -> list[str]:
    """Flatten nested (name, size[, children]) entries into report text."""
    lines = []
    for entry in entries:
        name, size = entry[0], entry[1]
        children = entry[2] if len(entry) > 2 else ()
        text = f"{indent}{name.strip()}"
        if size:
            text += f": {size}"
        lines.append(text)
        lines.extend(entry_report_lines(children, indent + "  "))
    return lines


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
        total = round(usage.total / GB, 1)
        used  = round(usage.used  / GB, 1)
        free  = round(usage.free  / GB, 1)
        pct   = round(usage.used / usage.total * 100, 1) if usage.total else 0.0
        line  = f"Total: {total} GB  |  Used: {used} GB  |  Free: {free} GB"
        details = [
            (f"Used: {used} GB ({pct}% of drive)", ""),
            (f"Free: {free} GB ({round(100 - pct, 1)}% of drive)", ""),
            (f"Scanned as user: {self.home}", ""),
            (f"Scan started: {fmt_time(datetime.now().timestamp())}", ""),
        ]
        self._emit(1, "Getting disk info...", "C: Drive", [(line, "", details)])
        self.report_lines += [
            "=============================================",
            " C: Disk Usage Report",
            "=============================================",
            f"Total: {total} GB | Used: {used} GB ({pct}%) | Free: {free} GB",
            f"Home: {self.home}",
            f"Scan started: {fmt_time(datetime.now().timestamp())}",
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
                stats = scan_folder(str(path))
                entries.append((name, f"{stats.size_gb} GB", folder_details(stats)))
        self.report_lines.extend(entry_report_lines(entries))
        self.report_lines.append("")
        self._emit(2, "Scanning user folders...", "User Folders", entries)

    def _step3_appdata_caches(self):
        entries = []
        self.report_lines.append("=== AppData Caches ===")
        for name, subpath in APPDATA_PATHS:
            path = self.home / subpath
            if path.exists():
                stats = scan_folder(str(path), top_n=3)
                if stats.size_gb > 0.1:
                    entries.append((name, f"{stats.size_gb} GB",
                                    [(f"Path: {path}", "")]
                                    + folder_details(stats, top_n=3)))
        self.report_lines.extend(entry_report_lines(entries))
        self.report_lines.append("")
        self._emit(3, "Scanning AppData caches...", "AppData Caches", entries)

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
                stats = scan_folder(str(sub), top_n=3)
                sz = stats.size_gb
                if sz > 0.5:
                    sub_entries.append((f"  {sub.name}", f"{sz} GB",
                                        [(f"Path: {sub}", "")]
                                        + folder_details(stats, top_n=3)))
                    total_sz += sz
            if total_sz > 0.5:
                entries.append((f"{base}  (Total: {round(total_sz, 1)} GB)", "",
                                [(f"{plural(len(sub_entries), 'program')} "
                                  f"over 0.5 GB", "")]))
                entries.extend(sub_entries)
        self.report_lines.extend(entry_report_lines(entries))
        self.report_lines.append("")
        self._emit(4, "Scanning games and programs...", "Games / Programs", entries)

    def _step5_windows_system(self):
        entries = []
        self.report_lines.append("=== Windows System ===")
        for label, path_str, hint in [
            ("Windows\\Temp", r"C:\Windows\Temp",
             "Safe to empty; recreated by Windows as needed."),
            ("Windows\\WinSxS (DISM cleanable)", r"C:\Windows\WinSxS",
             "Clean with: DISM /Online /Cleanup-Image /StartComponentCleanup"),
            ("Windows\\Installer", r"C:\Windows\Installer",
             "Do not delete manually - needed to repair/uninstall apps."),
        ]:
            p = pathlib.Path(path_str)
            if p.exists():
                stats = scan_folder(str(p), top_n=3)
                if stats.size_gb > 0:
                    entries.append((label, f"{stats.size_gb} GB",
                                    [(f"Path: {path_str}", ""), (f"Note: {hint}", "")]
                                    + folder_details(stats, top_n=3)))
        self.report_lines.extend(entry_report_lines(entries))
        self.report_lines.append("")
        self._emit(5, "Scanning Windows system folders...", "Windows System", entries)

    def _step6_node_modules(self):
        found = []
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
                    found.append((nm_path, scan_folder(nm_path, top_n=3)))
                    dirnames.remove("node_modules")  # don't descend into it
        except Exception:
            pass
        found.sort(key=lambda item: item[1].total_bytes, reverse=True)
        entries = []
        for nm_path, stats in found[:5]:
            details = [
                (f"Project: {os.path.dirname(nm_path)}", ""),
                (f"Packages (top level): {stats.top_level_dirs:,}", ""),
            ] + folder_details(stats, top_n=3)
            entries.append((nm_path, f"{stats.size_gb} GB", details))
        total_gb = round(sum(s.total_bytes for _, s in found) / GB, 2)
        self.report_lines.append(
            f"=== node_modules (top 5 of {len(found)} found, "
            f"{total_gb} GB total) ===")
        self.report_lines.extend(entry_report_lines(entries))
        self.report_lines.append("")
        self._emit(6, "Scanning node_modules...", "node_modules", entries)

    def _step7_downloads_recycle(self):
        entries = []
        self.report_lines.append("=== Downloads — Largest Files (top 10) ===")
        dl = self.home / "Downloads"
        if dl.exists():
            stats = scan_folder(str(dl), top_n=10)
            entries.append(("Downloads folder summary", "",
                            [(f"Path: {dl}", ""),
                             (f"Total size: {human_size(stats.total_bytes)}", "")]
                            + folder_details(stats)))
            for size, fp, mtime in stats.largest_files(10):
                entries.append((os.path.basename(fp), f"{round(size / GB, 2)} GB",
                                [(f"Path: {fp}", ""),
                                 (f"Exact size: {human_size(size)}", ""),
                                 (f"Modified: {fmt_time(mtime)}", "")]))

        rb = pathlib.Path(r"C:\$Recycle.Bin")
        rb_stats = scan_folder(str(rb), top_n=3)
        rb_details = [(f"Path: {rb}", "")] + folder_details(rb_stats, top_n=3)
        entries.append(("Recycle Bin", f"{rb_stats.size_gb} GB", rb_details))

        self.report_lines.extend(entry_report_lines(entries))
        self._emit(7, "Scanning Downloads and Recycle Bin...",
                   "Downloads & Recycle Bin", entries)

    def write_report(self, path: str) -> None:
        lines = self.report_lines + ["", f"Scan complete! Report saved to: {path}"]
        with open(path, "w", encoding="utf-8", errors="replace") as f:
            f.write("\n".join(lines))


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

        self.btn_expand = tk.Button(bar, text="Expand All", width=12,
                                    command=lambda: self._set_open(True))
        self.btn_expand.pack(side=tk.LEFT, padx=(8, 0))

        self.btn_collapse = tk.Button(bar, text="Collapse All", width=12,
                                      command=lambda: self._set_open(False))
        self.btn_collapse.pack(side=tk.LEFT, padx=(8, 0))

        prog_frame = tk.Frame(self.root, padx=10)
        prog_frame.pack(fill=tk.X, pady=(0, 4))

        self.progress = ttk.Progressbar(prog_frame, maximum=Scanner.STEPS,
                                        mode="determinate")
        self.progress.pack(fill=tk.X)

        self.lbl_status = tk.Label(prog_frame, text="Press 'Scan Now' to begin.",
                                   anchor="w")
        self.lbl_status.pack(fill=tk.X)

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

    def _insert_entries(self, parent: str, entries: list) -> None:
        for entry in entries:
            name, size = entry[0], entry[1]
            children = entry[2] if len(entry) > 2 else ()
            node = self.tree.insert(parent, tk.END, text=name, values=(size,))
            if children:
                self._insert_entries(node, children)

    def _set_open(self, is_open: bool, node: str = "") -> None:
        for child in self.tree.get_children(node):
            self.tree.item(child, open=is_open)
            self._set_open(is_open, child)

    def _update_ui(self, step: int, total: int, label: str,
                   category: str, entries: list) -> None:
        self.progress["value"] = step
        self.lbl_status.config(text=f"Step {step}/{total}: {label}")
        parent = self.tree.insert("", tk.END, text=category,
                                  open=(step == 1))
        self._category_nodes[category] = parent
        self._insert_entries(parent, entries)

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

    def _save_report(self):
        if self.scanner is None:
            return
        path = _report_path()
        try:
            self.scanner.write_report(path)
            messagebox.showinfo("Saved", f"Report saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save report:\n{e}")


def main():
    root = tk.Tk()
    DiskScanApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
