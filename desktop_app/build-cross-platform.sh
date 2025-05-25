#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Define the output directory for bundled applications
# This will be created in the root of the desktop_app directory
OUTPUT_DIR="dist_cross_platform"
mkdir -p "$OUTPUT_DIR"

echo "Cross-platform build script for CEO Email Explorer"
echo "=================================================="
echo ""
echo "Make sure you have installed the necessary cross-compilation tools and Rust targets:"
echo "- For Windows builds: cargo install cargo-xwin; rustup target add x86_64-pc-windows-msvc aarch64-pc-windows-msvc"
echo "- For Linux builds: cargo install cross; rustup target add x86_64-unknown-linux-gnu aarch64-unknown-linux-gnu"
echo "- For macOS builds: rustup target add x86_64-apple-darwin aarch64-apple-darwin (usually available on macOS)"
echo "=================================================="
echo ""

# Navigate to the tauri app directory if the script is not run from there
# This script is expected to be in desktop_app/
if [ ! -f "src-tauri/tauri.conf.json" ]; then
  echo "Error: This script must be run from the 'desktop_app' directory, or a subdirectory of it."
  echo "Current directory: $(pwd)"
  if [ -d "desktop_app" ]; then
    echo "Found 'desktop_app' subdirectory, changing to it."
    cd desktop_app
  else
    exit 1
  fi
fi

echo "Building for macOS (current architecture)..."
cargo tauri build
# Tauri by default outputs to src-tauri/target/[target-triple]/release/bundle/
# For macOS, it's usually src-tauri/target/release/bundle/macos/YourApp.app
# Or src-tauri/target/aarch64-apple-darwin/release/bundle/macos/YourApp.app
# We will attempt to copy the .app and .dmg
if [ -d "src-tauri/target/release/bundle/macos/" ]; then
  cp -R src-tauri/target/release/bundle/macos/*.app "$OUTPUT_DIR/"
  cp src-tauri/target/release/bundle/macos/*.dmg "$OUTPUT_DIR/"
  echo "macOS bundle and DMG copied to $OUTPUT_DIR/"
elif [ -d "src-tauri/target/$(rustc -Vv | grep host | awk '{print $2}')/release/bundle/macos/" ]; then
  TARGET_TRIPLE=$(rustc -Vv | grep host | awk '{print $2}')
  cp -R "src-tauri/target/$TARGET_TRIPLE/release/bundle/macos/*.app" "$OUTPUT_DIR/"
  cp "src-tauri/target/$TARGET_TRIPLE/release/bundle/macos/*.dmg" "$OUTPUT_DIR/"
  echo "macOS bundle and DMG for $TARGET_TRIPLE copied to $OUTPUT_DIR/"
else
  echo "Warning: macOS .app or .dmg not found in expected default location."
fi


echo ""
echo "Building for Windows (x86_64)..."
if ! command -v cargo-xwin &> /dev/null
then
    echo "WARNING: cargo-xwin not found. Skipping Windows build."
    echo "Please install it using: cargo install cargo-xwin"
else
    # Ensure XWIN_CACHE_DIR is set, default if not
    : "${XWIN_CACHE_DIR:="$HOME/.xwin-cache"}"
    export XWIN_CACHE_DIR
    echo "Using XWIN_CACHE_DIR: $XWIN_CACHE_DIR"
    mkdir -p "$XWIN_CACHE_DIR"

    cargo tauri build --target x86_64-pc-windows-msvc
    # Copy the .msi installer
    if [ -f "src-tauri/target/x86_64-pc-windows-msvc/release/bundle/msi/"*.msi ]; then
      cp src-tauri/target/x86_64-pc-windows-msvc/release/bundle/msi/*.msi "$OUTPUT_DIR/"
      echo "Windows x86_64 MSI installer copied to $OUTPUT_DIR/"
    else
      echo "Warning: Windows x86_64 .msi not found in expected location."
    fi
fi

echo ""
echo "Building for Linux (x86_64 using cross)..."
if ! command -v cross &> /dev/null
then
    echo "WARNING: cross not found. Skipping Linux build."
    echo "Please install it using: cargo install cross"
else
    # Tauri might not directly support --target with `cross` in the same way `cargo build` does.
    # We might need to use `cross` to build the Rust backend and then `tauri bundle`
    # However, Tauri's `build` command itself can often handle cross-compilation if the Rust toolchain is set up.
    # Let's try direct first, assuming underlying cargo uses the cross-linker setup.
    # For `cross`, you typically need a Cross.toml or rely on its automatic Docker image selection.
    cargo tauri build --target x86_64-unknown-linux-gnu
    # Copy the .AppImage and .deb
    if [ -f "src-tauri/target/x86_64-unknown-linux-gnu/release/bundle/appimage/"*.AppImage ]; then
        cp src-tauri/target/x86_64-unknown-linux-gnu/release/bundle/appimage/*.AppImage "$OUTPUT_DIR/"
        echo "Linux x86_64 AppImage copied to $OUTPUT_DIR/"
    else
        echo "Warning: Linux x86_64 AppImage not found."
    fi
    if [ -f "src-tauri/target/x86_64-unknown-linux-gnu/release/bundle/deb/"*.deb ]; then
        cp src-tauri/target/x86_64-unknown-linux-gnu/release/bundle/deb/*.deb "$OUTPUT_DIR/"
        echo "Linux x86_64 Debian package copied to $OUTPUT_DIR/"
    else
        echo "Warning: Linux x86_64 .deb not found."
    fi
fi

echo ""
echo "Build process complete. Check the '$OUTPUT_DIR' directory for bundles."
echo "Note: ARM builds (macOS, Windows, Linux) are not explicitly scripted here but can be added if needed by specifying --target aarch64-apple-darwin, aarch64-pc-windows-msvc, or aarch64-unknown-linux-gnu."
