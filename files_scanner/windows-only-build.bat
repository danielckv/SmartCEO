@echo off
REM Windows build script for file-scanner

IF "%1"=="--current" GOTO :current
IF "%1"=="--all" GOTO :all
IF "%1"=="--setup" GOTO :setup

ECHO File Scanner Build Script
ECHO Usage:
ECHO   build.bat --current  # Build for current platform
ECHO   build.bat --all      # Build for all supported platforms (requires setup)
ECHO   build.bat --setup    # Show setup instructions
GOTO :eof

:current
ECHO Building for Windows...
cargo build --release

IF NOT EXIST dist MKDIR dist
COPY target\release\file-scanner.exe dist\
ECHO Binary created in dist\ directory
GOTO :eof

:all
ECHO Building for all supported platforms from Windows...

IF NOT EXIST dist MKDIR dist

ECHO Building for Windows (x86_64)...
cargo build --release
COPY target\release\file-scanner.exe dist\file-scanner-windows-x86_64.exe

ECHO Note: To build for other platforms from Windows, you'll need WSL or cross-compilation tools.
ECHO See 'build.bat --setup' for more information.
GOTO :eof

:setup
ECHO To set up cross-compilation on Windows:
ECHO.
ECHO 1. For Linux targets, install WSL and set up Rust there:
ECHO    https://docs.microsoft.com/en-us/windows/wsl/install
ECHO.
ECHO 2. For macOS targets, you'll need a macOS machine or VM.
ECHO.
ECHO 3. Alternatively, use GitHub Actions for cross-platform builds.
GOTO :eof
