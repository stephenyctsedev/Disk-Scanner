# Folder Detail Drill-Down — Design

**Date:** 2026-08-29
**Status:** Implemented

## Overview

Each scanned folder previously showed only a name and a size in GB. That answers
"what is big?" but not "why is it big?". This change makes every folder in the
tree expand into a detail breakdown, and mirrors the same breakdown into the
saved text report.

## Detail collected per folder

| Row | Source |
|-----|--------|
| `Contents: N files in M subfolders` | running counters over the walk |
| `Top level: N folders, M files (size)` | first `os.walk` iteration |
| `Average file size` | `total_bytes / file_count` |
| `Newest file` / `Oldest file` | min/max `st_mtime` |
| `Largest subfolders (top 5)` | bytes rolled up to the immediate child folder |
| `Largest files (top 5)` | bounded min-heap; each expands to path + modified |
| `By file type (top 5)` | extension → (bytes, count), shown with % of folder |

An unreadable or empty folder collapses to a single `Empty (no readable files)`
row rather than a wall of zeros.

## Single-pass scanning

`get_folder_size()` used to `os.walk()` a folder purely to sum sizes, and step 4
walked each program folder separately from the size call. Both are now backed by
one function:

```
scan_folder(path, top_n=5) -> FolderStats
```

It walks the tree once and accumulates every counter above. `get_folder_size()`
is kept (it is the public helper the tests use) and delegates with `top_n=0`,
which skips largest-file tracking. Memory stays bounded: the largest-files heap
is capped at `top_n`, and only aggregates are retained otherwise.

Permission errors and files that vanish mid-scan are skipped silently, so a
missing path yields an all-zero `FolderStats` — same contract as before.

## Entry format

Progress entries were `(name, size)` tuples. They are now `(name, size)` **or**
`(name, size, children)`, where `children` is a list of the same shape, nested
arbitrarily deep.

- `DiskScanApp._insert_entries()` inserts them recursively into the Treeview.
- `entry_report_lines()` flattens the same structure into indented report text,
  so the tree and `disk_report.txt` can never drift apart.

## UI

Two toolbar buttons — **Expand All** / **Collapse All** — walk the tree and set
every node's `open` state, since the tree is now several levels deep.

## Step-specific detail

- **Step 1** — used/free as a percentage of the drive, home path, scan start time.
- **Step 3/4/5** — full path of each entry; Windows System rows also carry a
  cleanup hint (e.g. the DISM command for WinSxS).
- **Step 6** — owning project directory and top-level package count per
  `node_modules`, plus a total across all copies found in the report header.
- **Step 7** — a Downloads summary entry before the top-10 file list; each file
  row expands to its full path, exact size (KB/MB/GB) and modified date.

## Formatting

`human_size()` renders detail rows in B/KB/MB/GB/TB so sub-gigabyte items stop
reading as `0.0 GB`. Top-level folder sizes stay in GB for continuity with the
existing report and column, with the exact size available on the detail row.
