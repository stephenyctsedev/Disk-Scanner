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
    name, size, details = entries[0]
    assert "Total" in name and "Used" in name and "Free" in name
    assert size == ""
    # Step 1 now carries drive-level detail rows
    assert any("Free:" in d[0] for d in details)
    assert any("Scan started" in d[0] for d in details)


def test_scanner_step1_populates_report():
    scanner = Scanner(on_progress=lambda *a: None)
    scanner._step1_disk_info()
    report = "\n".join(scanner.report_lines)
    assert "C: Disk Usage Report" in report
    assert "Total:" in report


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
    # At most 10 download entries + 1 summary + 1 Recycle Bin entry
    assert entries[0][0] == "Downloads folder summary"
    download_entries = [e for e in entries
                        if e[1].endswith(" GB") and "Recycle" not in e[0]]
    assert len(download_entries) <= 10
    # Entries are sorted largest first
    sizes = [float(e[1].replace(" GB", "")) for e in download_entries]
    assert sizes == sorted(sizes, reverse=True)


def test_scanner_write_report(tmp_path):
    scanner = Scanner(on_progress=lambda *a: None)
    scanner._step1_disk_info()  # populate report_lines
    report_file = tmp_path / "disk_report.txt"
    scanner.write_report(str(report_file))
    content = report_file.read_text(encoding="utf-8")
    assert "C: Disk Usage Report" in content
    assert "Scan complete" in content


# --- Folder detail helpers -------------------------------------------------

import os

from disk_scan import (human_size, fmt_time, scan_folder, folder_details,
                       entry_report_lines)


def test_human_size_units():
    assert human_size(0) == "0 B"
    assert human_size(512) == "512 B"
    assert human_size(1536) == "1.5 KB"
    assert human_size(5 * 1024 ** 2) == "5.0 MB"
    assert human_size(2 * 1024 ** 3) == "2.0 GB"
    assert human_size(3 * 1024 ** 4) == "3.0 TB"


def test_fmt_time_missing():
    assert fmt_time(0) == "-"


def test_scan_folder_missing_path_is_empty():
    stats = scan_folder("C:/this/does/not/exist/12345")
    assert stats.total_bytes == 0
    assert stats.file_count == 0
    assert stats.size_gb == 0.0


def test_scan_folder_collects_counts_and_breakdowns(tmp_path):
    (tmp_path / "notes.txt").write_bytes(b"x" * 1024)
    docs = tmp_path / "reports"
    docs.mkdir()
    (docs / "q1.pdf").write_bytes(b"x" * (4 * 1024 * 1024))
    (docs / "q2.pdf").write_bytes(b"x" * (2 * 1024 * 1024))
    nested = docs / "archive"
    nested.mkdir()
    (nested / "old.zip").write_bytes(b"x" * (1024 * 1024))

    stats = scan_folder(str(tmp_path))

    assert stats.file_count == 4
    assert stats.dir_count == 2              # reports + reports/archive
    assert stats.top_level_dirs == 1
    assert stats.top_level_files == 1
    assert stats.root_file_bytes == 1024
    assert stats.total_bytes == 7 * 1024 * 1024 + 1024
    # Subfolder rollup includes nested content
    assert stats.subdir_bytes["reports"] == 7 * 1024 * 1024
    assert stats.subdir_files["reports"] == 3
    # Extension breakdown
    assert stats.ext_bytes[".pdf"] == (6 * 1024 * 1024, 2)
    assert stats.ext_bytes[".txt"] == (1024, 1)
    # Largest files, biggest first
    largest = stats.largest_files(2)
    assert [os.path.basename(f[1]) for f in largest] == ["q1.pdf", "q2.pdf"]
    assert stats.newest_mtime > 0
    assert stats.oldest_mtime > 0


def test_scan_folder_top_n_limits_largest_files(tmp_path):
    for i in range(8):
        (tmp_path / f"f{i}.bin").write_bytes(b"x" * ((i + 1) * 1024))
    stats = scan_folder(str(tmp_path), top_n=3)
    largest = stats.largest_files(10)
    assert len(largest) == 3
    assert [os.path.basename(f[1]) for f in largest] == ["f7.bin", "f6.bin", "f5.bin"]


def test_scan_folder_top_n_zero_skips_file_tracking(tmp_path):
    (tmp_path / "a.bin").write_bytes(b"x" * 1024)
    stats = scan_folder(str(tmp_path), top_n=0)
    assert stats.total_bytes == 1024
    assert stats.largest_files() == []


def test_folder_details_empty_folder(tmp_path):
    details = folder_details(scan_folder(str(tmp_path)))
    assert details == [("Empty (no readable files)", "")]


def test_folder_details_sections(tmp_path):
    sub = tmp_path / "invoices"
    sub.mkdir()
    (sub / "big.pdf").write_bytes(b"x" * (2 * 1024 * 1024))
    (tmp_path / "note.txt").write_bytes(b"x" * 1024)

    details = folder_details(scan_folder(str(tmp_path)))
    labels = [d[0] for d in details]

    assert any(l.startswith("Contents: 2 files") for l in labels)
    assert any(l.startswith("Top level:") for l in labels)
    assert any(l.startswith("Average file size:") for l in labels)
    assert any(l.startswith("Newest file:") for l in labels)
    assert any(l.startswith("Oldest file:") for l in labels)

    sections = {d[0].split(" (top")[0]: d for d in details if len(d) > 2}
    assert "Largest subfolders" in sections
    assert "Largest files" in sections
    assert "By file type" in sections

    sub_children = sections["Largest subfolders"][2]
    assert sub_children[0][0].startswith("invoices  (1 file)")
    assert sub_children[0][1] == "2.0 MB"

    file_children = sections["Largest files"][2]
    assert file_children[0][0] == "big.pdf"
    # Each file row carries path + modified detail
    assert any(c[0].startswith("Path:") for c in file_children[0][2])
    assert any(c[0].startswith("Modified:") for c in file_children[0][2])

    type_children = sections["By file type"][2]
    assert type_children[0][0].startswith(".pdf")


def test_folder_details_can_skip_type_breakdown(tmp_path):
    (tmp_path / "a.bin").write_bytes(b"x" * 1024)
    details = folder_details(scan_folder(str(tmp_path)), include_types=False)
    assert not any(d[0].startswith("By file type") for d in details)


def test_entry_report_lines_nests_children():
    entries = [("Documents", "1.5 GB", [
        ("Contents: 3 files in 1 subfolders", ""),
        ("Largest files (top 1)", "", [("big.pdf", "1.0 GB")]),
    ])]
    assert entry_report_lines(entries) == [
        "  Documents: 1.5 GB",
        "    Contents: 3 files in 1 subfolders",
        "    Largest files (top 1)",
        "      big.pdf: 1.0 GB",
    ]


def test_step2_user_folders_include_details(tmp_path):
    docs = tmp_path / "Documents"
    (docs / "taxes").mkdir(parents=True)
    (docs / "taxes" / "2025.pdf").write_bytes(b"x" * (10 * 1024 * 1024))

    calls = []
    scanner = Scanner(on_progress=lambda *a: calls.append(a), home=str(tmp_path))
    scanner._step2_user_folders()

    _, _, _, _, entries = calls[0]
    documents = [e for e in entries if e[0] == "Documents"][0]
    assert documents[1] == "0.01 GB"
    detail_labels = [d[0] for d in documents[2]]
    assert any("Contents: 1 file in 1 subfolder" in l for l in detail_labels)
    assert any(l.startswith("Largest subfolders") for l in detail_labels)
    # The same detail is mirrored into the saved report
    report = "\n".join(scanner.report_lines)
    assert "Documents: 0.01 GB" in report
    assert "2025.pdf" in report


def test_step6_node_modules_details(tmp_path):
    nm = tmp_path / "proj" / "node_modules" / "pkg"
    nm.mkdir(parents=True)
    (nm / "index.js").write_bytes(b"x" * (10 * 1024 * 1024))

    calls = []
    scanner = Scanner(on_progress=lambda *a: calls.append(a), home=str(tmp_path))
    scanner._step6_node_modules()

    _, _, _, _, entries = calls[0]
    detail_labels = [d[0] for d in entries[0][2]]
    assert any(l.startswith("Project:") for l in detail_labels)
    assert any(l.startswith("Packages (top level): 1") for l in detail_labels)
