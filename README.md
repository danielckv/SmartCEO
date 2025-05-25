# SmartCEO: Full AI Suit Tools

## I. Introduction

Welcome to CEO Email Explorer! This application helps you process Microsoft Outlook PST email archives and perform powerful semantic searches on the extracted email data.

It features two main functionalities:

1.  **PST Processing & Data Loading**: Extracts emails from a `.pst` file, converts them to a usable format (JSONL), generates embeddings for semantic search, and stores everything in a local vector database (ChromaDB).
2.  **Email Search**: Allows you to search through your processed emails using natural language queries. It can optionally leverage Ollama for advanced query understanding.

## II. System Prerequisites

Before you begin, please ensure your system meets the following requirements:

*   **Operating System**:
    *   Windows 10 or newer
    *   macOS (Catalina 10.15 or newer)
    *   Linux (Note: Pre-built Linux versions may not be available due to build environment constraints; building from source would be required).

*   **Python**:
    *   Python 3.9 or newer is recommended.
    *   Download Python from the official website: [python.org/downloads/](https://www.python.org/downloads/)
    *   Ensure Python and Pip (Python's package installer) are added to your system's PATH during installation.

*   **Rust (Optional - for building from source)**:
    *   If you intend to build the Tauri application from its source code (not required if using a pre-built version), you will need Rust (latest stable version, e.g., 1.78+) and Cargo.
    *   Install Rust via `rustup` from [rustup.rs](https://rustup.rs/).
    *   For detailed instructions on building from source, including local and cross-platform builds, see **Section VIII: Building the Desktop Application from Source (Advanced)**.

*   **Ollama (Optional - for enhanced search)**:
    *   Ollama provides advanced natural language processing capabilities that can improve the understanding of your search queries.
    *   The application can perform basic semantic search without Ollama, but its use is recommended for more nuanced search results.
    *   Download and set up Ollama from [ollama.com](https://ollama.com/). Follow their instructions to install it and pull a model (e.g., `ollama pull llama3`).

## III. Application Setup (Assuming Pre-built Application)

*(This section describes the process for a pre-built application. Due to current build environment limitations, pre-built packages might not be available. If so, you would need to build from source, which is a more advanced process not covered here.)*

1.  **Download**: Download the application installer for your operating system (e.g., `CEO-Email-Explorer.msi` for Windows, `CEO-Email-Explorer.dmg` for macOS, or an `.AppImage`/`.deb` for Linux if available).
2.  **Install**: Run the installer and follow the on-screen prompts to install the application.

## IV. Python Backend Setup (Crucial)

The application's core email processing and search logic relies on a Python backend. This setup is required for the application to function correctly.

**1. Obtain Application Files:**

*   **If using a Pre-built Application**: The necessary Python scripts (`engine_cli.py`, `pst_processor.py`, etc.) and `requirements.txt` are bundled with the application. When the application runs, these files are typically extracted to a temporary resource directory or a specific application data folder. For the purpose of setting up the Python environment, you will need to locate these files.
    *   *The exact location can vary. After running the Tauri app once, it might create a folder in your user's application data directory (e.g., `%APPDATA%` on Windows, `~/Library/Application Support` on macOS). The Python scripts specified in `tauri.conf.json` (`engine_cli.py`, `pst_processor.py`, `data_loader.py`, `db_explorer.py`, `requirements.txt`) would be found inside a subfolder there, potentially named `resources` or directly at the root of these bundled files.*
    *   **For this guide, we'll refer to this location as `<App Resource Dir>`. You will need to identify this directory on your system once the Tauri application is run (even if it doesn't fully function without Python setup yet).**
*   **If running from Source Code**: Ensure you have the complete project repository cloned from Git. The Python scripts are located in the `vector_engine/src/` directory, and `requirements.txt` is in `vector_engine/`.

**2. Navigate to Python Directory:**

*   Open a terminal (Command Prompt, PowerShell, Terminal.app, etc.).
*   Navigate to the directory containing the Python scripts and `requirements.txt`.
    *   **For a Pre-built Application (conceptual)**:
        ```bash
        # Example path - actual path will vary!
        cd "<App Resource Dir>" 
        # If scripts are in a subfolder, e.g., "python_engine":
        # cd "<App Resource Dir>/python_engine" 
        ```
        *(Based on the current Tauri setup, the resources are bundled at the root of the resource directory. So you'd `cd` directly into where `engine_cli.py` and `requirements.txt` are located within the app's resource structure).*
    *   **For Source Code**:
        ```bash
        cd path/to/your_repo_root/vector_engine 
        # (requirements.txt is here, scripts are in src/)
        # For pip install, you can run it from `vector_engine` if requirements.txt is there.
        # The `engine_cli.py` will handle its own pathing to find sibling modules.
        ```

**3. Create a Virtual Environment (Highly Recommended):**

This creates an isolated Python environment for the application's dependencies.

*   Inside the directory from Step 2 (preferably `vector_engine/` if from source, or the root of the Python resources for a packaged app):
    ```bash
    python3 -m venv venv  # Or `python -m venv venv`
    ```
*   Activate the virtual environment:
    *   **Linux/macOS**:
        ```bash
        source venv/bin/activate
        ```
    *   **Windows (Command Prompt/PowerShell)**:
        ```bash
        venv\Scripts\activate
        ```
    Your terminal prompt should now indicate that the virtual environment is active (e.g., `(venv)`).

**4. Install Dependencies:**

*   Ensure your virtual environment is active.
*   Install the required Python packages:
    ```bash
    pip install -r requirements.txt
    ```
    *(Ensure `requirements.txt` is in your current directory, or provide the correct path to it).*

## V. Running the Application

1.  **Launch the Application**:
    *   Once the Python backend setup (virtual environment and dependencies) is complete, launch the "CEO Email Explorer" application (e.g., from your Start Menu, Applications folder, or by running the executable directly if from a build).

2.  **Python Interpreter Path**:
    *   The Tauri application will attempt to call `python3` (or `python` on Windows) to execute its backend scripts.
    *   **For robust execution**: It's best to ensure that the Python interpreter where you installed the dependencies (i.e., the one from your virtual environment) is the one found by the system.
        *   **Option 1 (Recommended for CLI users)**: Launch the Tauri application executable *from the same terminal window where you have already activated the Python virtual environment*. This usually ensures the correct Python interpreter is used.
        *   **Option 2 (System PATH)**: Alternatively, ensure the `python3`/`python` command in your system's PATH points to the interpreter within the created virtual environment, or to a global Python installation where these dependencies have been installed. This is generally less reliable for isolated application setups.

## VI. Usage Guide

### PST Processing

This function processes your `.pst` email archive, extracts emails, and builds a local search database.

1.  **Navigate**: Open the application and go to the **"PST Processor"** tab.
2.  **Select PST File**: Click the "Select PST File" button. A system dialog will appear. Choose the `.pst` file you want to process.
3.  **Select Data Directory**: Click the "Select Data Directory" button. Choose an existing empty folder (or create a new one) where the processed data (JSONL file) and the search database (ChromaDB files) will be stored. This directory should be on a local drive with sufficient free space. **Remember this directory path for the search step.**
4.  **Start Processing**: Click the "Start Full Processing" button.
5.  **Monitor**: Observe the "Processing Log" area in the UI. It will show:
    *   Confirmation of selected paths.
    *   Progress messages for "Step 1: Processing PST to JSONL".
    *   Output from the Python script, including any errors from `pypff`.
    *   Progress messages for "Step 2: Loading data into ChromaDB".
    *   Output from the Python script for data loading and embedding generation.
    *   A final "Full processing finished" message on success.
    *   This process can take a significant amount of time depending on the PST file size.

Upon successful completion, your emails will be processed, and a search index will be created in the specified Data Directory.

### Email Search

This function allows you to search the emails you've previously processed.

1.  **Navigate**: Open the application and go to the **"Email Search"** tab.
2.  **Select Database Directory**: Click the "Select DB Directory" button. Choose the **same Data Directory** that you selected during the "PST Processing" step (this directory contains the `emails.jsonl` and the ChromaDB database).
3.  **Enter Query**: Type your search query into the search bar (e.g., "report from John Doe about Q3 results").
4.  **Search**: Click the "Search" button or press Enter.
5.  **View Results**:
    *   The "Search Results" area will display a list of emails matching your query, showing subject, sender, folder, a relevance score (distance), and a short body preview.
    *   The "Raw Log & Output" area will show the JSON response from the search backend and any diagnostic messages or explanations from the query parsing system (especially if Ollama is used).
6.  **(Optional) Ollama Integration**: If you have Ollama running with a suitable model (e.g., `llama3`), the search functionality will attempt to use it to better understand your query intent, potentially leading to more relevant results for complex queries. The "Raw Log & Output" might provide an "explanation" of how your query was parsed.

## VII. Troubleshooting (Basic)

*   **Python Errors / "Failed to spawn command"**:
    *   Ensure you have completed all steps in **Section IV: Python Backend Setup**.
    *   Make sure the Python virtual environment (e.g., `venv`) is activated in the terminal from which you are trying to debug or (if applicable) launch the Tauri application.
    *   Verify all dependencies in `requirements.txt` were installed correctly in the active virtual environment (`pip list` can show installed packages).
    *   Ensure `python3` (or `python` on Windows) is in your system PATH and points to the correct interpreter.
*   **PST Processing Issues**:
    *   "Error processing PST file": This can occur if the selected file is not a valid PST, is corrupted, or is password-protected (password-protected PSTs are not supported by `pypff`).
    *   "pypff not found" or similar: Indicates an issue with the Python environment setup, specifically the `pypff` library.
*   **Data Loading / Embedding Issues**:
    *   Errors during "Step 2: Loading data" might relate to issues with the `sentence-transformers` model (e.g., model not downloaded correctly if not bundled, or issues during embedding generation). Check logs for details.
    *   Ensure sufficient disk space in the output directory.
*   **Search Issues**:
    *   "Database directory not found" or "Collection not found": Ensure you've selected the correct Data Directory where you previously processed your PST files.
    *   No results: Try broader search terms. If Ollama is used, check if it's running correctly.
*   **Ollama Issues**:
    *   If you expect Ollama to be used, ensure it's running locally and the model specified in the application (or its default) is available via `ollama list`.
    *   The application has a fallback to basic regex/semantic search if Ollama is not available or fails.

For more detailed errors, check the logs printed in the UI and any console output if you launched the application from a terminal.

## VIII. Building the Desktop Application from Source (Advanced)

This section describes how to build the `desktop_app` (Tauri application) from its source code. This is generally needed if you want to make modifications to the application itself or if pre-built binaries are not available for your platform.

### 1. Prerequisites

Ensure you have the following installed:

*   **Node.js and npm**: Required for the web frontend part of Tauri. Download from [nodejs.org](https://nodejs.org/).
*   **Rust and Cargo**: Install via `rustup` from [rustup.rs](https://rustup.rs/).
*   **System Build Tools**:
    *   **Windows**: Microsoft C++ Build Tools (available in Visual Studio Installer).
    *   **macOS**: Xcode Command Line Tools (`xcode-select --install`).
    *   **Linux**: `gcc`, `make`, `webkit2gtk` development libraries (e.g., `sudo apt-get install build-essential libwebkit2gtk-4.0-dev`).
*   **Tauri CLI**: Install using Cargo:
    ```bash
    cargo install tauri-cli
    ```

### 2. Standard Local Build (Current Platform)

To build the application for your current operating system and architecture:

1.  **Navigate to the app directory**:
    ```bash
    cd desktop_app
    ```
2.  **Install frontend dependencies**:
    ```bash
    npm install
    ```
3.  **Build the application**:
    ```bash
    cargo tauri build
    ```
    The resulting installer/bundle will be located in `desktop_app/src-tauri/target/release/bundle/`.

### 3. Cross-Platform Builds (from macOS)

The project includes a script to facilitate building for macOS, Windows (x86_64), and Linux (x86_64) from a macOS environment.

**Additional Prerequisites for Cross-Compilation from macOS:**

*   **`cargo-xwin`**: For Windows builds. Install with `cargo install cargo-xwin`.
    *   Ensure the `XWIN_CACHE_DIR` environment variable is set (e.g., `export XWIN_CACHE_DIR="$HOME/.xwin-cache"`) and the directory exists.
*   **`cross`**: For Linux builds. Install with `cargo install cross`.
    *   `cross` typically uses Docker for its build environments. Ensure Docker is installed and running.
*   **Rust Targets**: Add the necessary cross-compilation targets using `rustup`:
    ```bash
    # For Windows x86_64
    rustup target add x86_64-pc-windows-msvc
    # For Linux x86_64
    rustup target add x86_64-unknown-linux-gnu
    # For macOS (usually pre-installed or add if needed)
    rustup target add x86_64-apple-darwin
    rustup target add aarch64-apple-darwin
    ```
    *(Note: The build script also mentions ARM targets like `aarch64-pc-windows-msvc` and `aarch64-unknown-linux-gnu`. If you need these, add them via `rustup` as well and potentially modify the build script.)*

**Using the Build Script:**

1.  **Navigate to the app directory**:
    ```bash
    cd desktop_app
    ```
2.  **Ensure the script is executable**:
    ```bash
    chmod +x build-cross-platform.sh
    ```
3.  **Run the script**:
    ```bash
    ./build-cross-platform.sh
    ```
    The script will attempt to build for macOS, Windows (x86_64), and Linux (x86_64).
    Bundled applications will be copied into the `desktop_app/dist_cross_platform/` directory.

**Important Notes for Cross-Compilation:**

*   **Windows Builds**: `cargo-xwin` requires the appropriate Windows SDK components. It will attempt to download them into `XWIN_CACHE_DIR`. This can take time and a significant amount of disk space on the first run.
*   **Linux Builds**: `cross` relies on Docker images that contain the necessary toolchains. Ensure Docker is running and has internet access to pull images.
*   **ARM Targets**: The provided script primarily focuses on x86_64 targets. To build for ARM (e.g., `aarch64-apple-darwin`, `aarch64-pc-windows-msvc`, `aarch64-unknown-linux-gnu`), you would need to:
    1.  Ensure the corresponding Rust targets are installed via `rustup`.
    2.  Modify the `build-cross-platform.sh` script to include `cargo tauri build --target <your-arm-target>` commands.
*   **Troubleshooting**: Cross-compilation can be complex. If you encounter issues, check the output logs carefully. Ensure all prerequisites are met, environment variables (like `XWIN_CACHE_DIR`) are correctly set, and that Docker (for `cross`) is functioning. Consult the documentation for `tauri`, `cargo-xwin`, and `cross` for more detailed guidance.
```
