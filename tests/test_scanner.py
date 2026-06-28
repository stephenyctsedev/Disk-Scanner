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
