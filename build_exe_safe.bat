@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"

echo ============================================
echo Reading Tracker V3 safe build
echo Current folder: %CD%
echo ============================================
echo.

set "LOG_FILE=build_safe_log.txt"

echo [1/7] Check source file...
if not exist "reading_app_v3.py" (
    if exist "reading_app_v3_1.py" (
        echo Found reading_app_v3_1.py, copying to reading_app_v3.py
        copy /Y "reading_app_v3_1.py" "reading_app_v3.py" >nul
    )
)

if not exist "reading_app_v3.py" (
    echo ERROR: reading_app_v3.py not found.
    echo Please put reading_app_v3.py in this folder.
    pause
    exit /b 1
)

echo [2/7] Select Python...
if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else (
    set "PY=python"
)

echo Python executable: %PY%
"%PY%" --version
if errorlevel 1 (
    echo ERROR: Python is not available.
    pause
    exit /b 1
)

echo.
echo [3/7] Upgrade pip and install dependencies...
"%PY%" -m pip install --upgrade pip > "%LOG_FILE%" 2>&1
"%PY%" -m pip install pyinstaller matplotlib >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo ERROR: Dependency installation failed.
    echo See build_safe_log.txt
    type "%LOG_FILE%"
    pause
    exit /b 1
)

echo.
echo [4/7] Clean old build...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "ReadingTracker.spec" del /q "ReadingTracker.spec"

echo.
echo [5/7] Build exe with PyInstaller...
echo This may take several minutes.
"%PY%" -m PyInstaller --noconfirm --clean --onedir --windowed --name ReadingTracker "reading_app_v3.py" >> "%LOG_FILE%" 2>&1

if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller build failed.
    echo Last log lines:
    echo --------------------------------------------
    powershell -NoProfile -Command "Get-Content '%LOG_FILE%' -Tail 100"
    echo --------------------------------------------
    pause
    exit /b 1
)

echo.
echo [6/7] Check output...
if exist "dist\ReadingTracker\ReadingTracker.exe" (
    echo SUCCESS: exe created.
    echo.
    echo Output:
    echo %CD%\dist\ReadingTracker\ReadingTracker.exe
    echo.
    echo [7/7] Opening output folder...
    start "" "%CD%\dist\ReadingTracker"
) else (
    echo ERROR: Build finished but exe was not found.
    echo See build_safe_log.txt
    pause
    exit /b 1
)

echo.
echo Done.
pause
endlocal
