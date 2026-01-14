@echo off
REM ============================================
REM Build Script for Container Reconciliation Tool V5.7
REM ============================================
REM Usage: Run this batch file to create single EXE
REM Output: dist\ContainerReconciliation_V5.7.exe
REM ============================================

echo ============================================
echo Building Container Reconciliation Tool V5.7
echo ============================================

REM Check if PyInstaller is installed
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

REM Clean previous build
echo.
echo [1/3] Cleaning previous build...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

REM Build EXE
echo.
echo [2/3] Building EXE (this may take a few minutes)...
pyinstaller app_gui.spec --clean --noconfirm

REM Check result
echo.
if exist "dist\ContainerReconciliation_V5.7.exe" (
    echo [3/3] BUILD SUCCESS!
    echo.
    echo ============================================
    echo Output: dist\ContainerReconciliation_V5.7.exe
    echo ============================================
    echo.
    echo To run: Double-click the EXE file
    echo.
    dir "dist\ContainerReconciliation_V5.7.exe"
) else (
    echo [3/3] BUILD FAILED!
    echo Check the error messages above.
)

echo.
pause
