@echo off
cd /d "%~dp0"

:: Self-elevate to admin so we can manage Defender exclusions
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator access to manage Defender exclusions...
    powershell -Command "Start-Process cmd -Verb RunAs -ArgumentList '/c cd /d \"%~dp0\" && \"%~f0\"'"
    exit /b
)

echo ================================
echo  Building DiskScan.exe
echo ================================
echo.

echo [1/3] Allowing build output in Windows Defender...
powershell -Command "Add-MpPreference -ExclusionPath '%~dp0dist' -ErrorAction SilentlyContinue"

echo.
echo [2/3] Running PyInstaller...
pyinstaller --onefile --windowed --name "DiskScan" disk_scan.py

echo.
echo [3/3] Finalizing...
if exist "dist\DiskScan.exe" (
    powershell -Command "Add-MpPreference -ExclusionPath '%~dp0dist\DiskScan.exe' -ErrorAction SilentlyContinue"
    echo.
    echo Build successful!
    echo EXE location: %~dp0dist\DiskScan.exe
) else (
    echo.
    echo Warning: dist\DiskScan.exe not found - build may have failed.
)
echo.
pause
