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
    name, size = entries[0]
    assert "Total" in name and "Used" in name and "Free" in name
    assert size == ""


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
