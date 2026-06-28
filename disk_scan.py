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
            ("Windows\\Temp",                    r"C:\Windows\Temp"),
            ("Windows\\WinSxS (DISM cleanable)", r"C:\Windows\WinSxS"),
            ("Windows\\Installer",               r"C:\Windows\Installer"),
        ]:
            p = pathlib.Path(path_str)
            if p.exists():
                sz = get_folder_size(str(p))
                if sz > 0:
                    entries.append((label, f"{sz} GB"))
                    self.report_lines.append(f"  {path_str}: {sz} GB")
        self.report_lines.append("")
        self._emit(5, "Scanning Windows system folders...", "Windows System", entries)

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

    def _update_ui(self, step: int, total: int, label: str,
                   category: str, entries: list) -> None:
        self.progress["value"] = step
        self.lbl_status.config(text=f"Step {step}/{total}: {label}")
        parent = self.tree.insert("", tk.END, text=category,
                                  open=(step == 1))
        self._category_nodes[category] = parent
        for name, size in entries:
            self.tree.insert(parent, tk.END, text=name, values=(size,))

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
