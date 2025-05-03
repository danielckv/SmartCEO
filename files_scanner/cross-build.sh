#!/bin/bash
# Cross-platform build script for file-scanner

# Function to detect the platform
detect_platform() {
    case "$(uname -s)" in
        Linux*)     echo "linux";;
        Darwin*)    echo "macos";;
        CYGWIN*)    echo "windows";;
        MINGW*)     echo "windows";;
        MSYS*)      echo "windows";;
        *)          echo "unknown";;
    esac
}

# Function to build for the current platform
build_current() {
    echo "Building for current platform..."
    cargo build --release
    
    # Create output directory
    mkdir -p dist
    
    # Copy binary to dist folder
    if [ "$(detect_platform)" = "windows" ]; then
        cp target/release/file-scanner.exe dist/
    else
        cp target/release/file-scanner dist/
    fi
    
    echo "Binary created in dist/ directory"
}

# Function to build for all platforms (requires cross-compilation setup)
build_all() {
    echo "Building for all platforms..."
    
    # Create output directory
    mkdir -p dist
    
    # Build for Linux
    if command -v cross > /dev/null; then
        echo "Building for Linux (x86_64)..."
        cross build --release --target x86_64-unknown-linux-gnu
        cp target/x86_64-unknown-linux-gnu/release/file-scanner dist/file-scanner-linux-x86_64
        
        echo "Building for Linux (aarch64)..."
        cross build --release --target aarch64-unknown-linux-gnu
        cp target/aarch64-unknown-linux-gnu/release/file-scanner dist/file-scanner-linux-aarch64
    else
        echo "WARNING: 'cross' tool not found, skipping Linux cross-compilation"
    fi
    
    # Build for macOS if on macOS
    if [ "$(detect_platform)" = "macos" ]; then
        echo "Building for macOS (x86_64)..."
        cargo build --release --target x86_64-apple-darwin
        cp target/x86_64-apple-darwin/release/file-scanner dist/file-scanner-macos-x86_64
        
        if command -v rustup > /dev/null && rustup target list --installed | grep -q "aarch64-apple-darwin"; then
            echo "Building for macOS (arm64)..."
            cargo build --release --target aarch64-apple-darwin
            cp target/aarch64-apple-darwin/release/file-scanner dist/file-scanner-macos-arm64
        fi
    fi
    
    # Build for Windows
    if [ "$(detect_platform)" = "windows" ]; then
        echo "Building for Windows (x86_64)..."
        cargo build --release
        cp target/release/file-scanner.exe dist/file-scanner-windows-x86_64.exe
    elif command -v cargo-xwin > /dev/null; then
        echo "Building for Windows (x86_64)..."
        cargo xwin build --release --target x86_64-pc-windows-msvc
        cp target/x86_64-pc-windows-msvc/release/file-scanner.exe dist/file-scanner-windows-x86_64.exe
    else
        echo "WARNING: Not on Windows and 'cargo-xwin' not found, skipping Windows build"
    fi
    
    echo "All binaries created in dist/ directory"
}

# Setup instructions
setup_instructions() {
    echo "To set up cross-compilation tools:"
    echo ""
    echo "1. Install 'cross' for Linux targets:"
    echo "   cargo install cross"
    echo ""
    echo "2. Install 'cargo-xwin' for Windows target:"
    echo "   cargo install cargo-xwin"
    echo ""
    echo "3. For macOS targets, add the targets with rustup:"
    echo "   rustup target add x86_64-apple-darwin aarch64-apple-darwin"
}

# Main script
case "$1" in
    "--current")
        build_current
        ;;
    "--all")
        build_all
        ;;
    "--setup")
        setup_instructions
        ;;
    *)
        echo "File Scanner Build Script"
        echo "Usage:"
        echo "  ./build.sh --current  # Build for current platform"
        echo "  ./build.sh --all      # Build for all platforms (requires cross-compilation tools)"
        echo "  ./build.sh --setup    # Show setup instructions for cross-compilation"
        ;;
esac
