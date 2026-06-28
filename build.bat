@echo off
echo Building DiskScan.exe...
pyinstaller --onefile --windowed --name "DiskScan" disk_scan.py
echo.
echo Done! EXE is in the dist\ folder.
pause
