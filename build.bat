@echo off
cd /d "%~dp0"
echo ============================================
echo  Blog Tool - EXE Build Script
echo ============================================
echo.

:: Check PyInstaller
python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [1/3] Installing PyInstaller...
    python -m pip install pyinstaller
) else (
    echo [1/3] PyInstaller already installed.
)

:: Clean previous build
echo [2/3] Cleaning previous build...
if exist dist\blog_tool rmdir /s /q dist\blog_tool
if exist build\blog_tool rmdir /s /q build\blog_tool

:: Build
echo [3/3] Building EXE... (may take a few minutes)
python -m PyInstaller blog_tool.spec --noconfirm

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. Check the messages above.
    pause
    exit /b 1
)

:: Copy user data folders
echo.
echo [Post] Copying user data...

if exist src (
    xcopy /e /i /y src dist\blog_tool\src >nul
    echo   - src: OK
)
if exist clinic_profiles (
    xcopy /e /i /y clinic_profiles dist\blog_tool\clinic_profiles >nul
    echo   - clinic_profiles: OK
)
if exist profiles.json (
    copy /y profiles.json dist\blog_tool\profiles.json >nul
    echo   - profiles.json: OK
)
if exist chrome_profile (
    xcopy /e /i /y chrome_profile dist\blog_tool\chrome_profile >nul
    echo   - chrome_profile: OK
)

echo.
echo ============================================
echo  Build complete!
echo  Output : dist\blog_tool\
echo  Run    : dist\blog_tool\blog_tool.exe
echo.
echo  To share: copy the entire dist\blog_tool\ folder.
echo  (Chrome must be installed on the target PC)
echo ============================================
echo.
pause
