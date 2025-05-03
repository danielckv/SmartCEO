// src/main.rs
use chrono::{DateTime, Local};
use rayon::prelude::*;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use structopt::StructOpt;
use walkdir::{DirEntry, WalkDir};

#[cfg(target_os = "windows")]
use outlook::scan_outlook;

#[derive(Debug, StructOpt)]
#[structopt(
    name = "file-scanner",
    about = "Scan for data files across your system"
)]
struct Opt {
    /// Output directory for scan results
    #[structopt(short, long)]
    output: Option<PathBuf>,

    /// Directories to scan
    #[structopt(short, long, parse(from_os_str))]
    dirs: Option<Vec<PathBuf>>,

    /// Directories to exclude
    #[structopt(short, long)]
    exclude: Option<Vec<String>>,

    /// Number of threads to use
    #[structopt(short, long, default_value = "0")]
    threads: usize,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
struct FileInfo {
    path: String,
    size: u64,
    modified: String,
    created: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
struct ScanResults {
    csv: Vec<FileInfo>,
    excel: Vec<FileInfo>,
    text: Vec<FileInfo>,
    json: Vec<FileInfo>,
    email: Vec<EmailInfo>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
struct EmailInfo {
    name: String,
    folders: Vec<FolderInfo>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
struct FolderInfo {
    name: String,
    item_count: i32,
    subfolders: Vec<FolderInfo>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
struct Summary {
    timestamp: String,
    platform: String,
    scan_dirs: Vec<String>,
    file_count: usize,
    duration: f64,
    categories: HashMap<String, usize>,
}

#[derive(Debug, Serialize, Deserialize)]
struct OutputData {
    summary: Summary,
    results: ScanResults,
}

fn get_default_scan_dirs() -> Vec<PathBuf> {
    let mut dirs = Vec::new();

    #[cfg(target_os = "windows")]
    {
        // Scan drives from C to Z
        for drive_letter in b'C'..=b'Z' {
            let drive = format!("{}:\\", drive_letter as char);
            let path = PathBuf::from(&drive);
            if path.exists() {
                dirs.push(path);
            }
        }
    }

    #[cfg(target_os = "macos")]
    {
        // On macOS, scan home directory
        if let Some(home) = dirs_next::home_dir() {
            dirs.push(home);
        }
    }

    #[cfg(target_os = "linux")]
    {
        // On Linux, scan home directory
        dirs.push(PathBuf::from("/home"));
    }

    dirs
}

fn get_default_exclude_dirs() -> Vec<String> {
    let mut exclude = vec![
        "Windows".to_string(),
        "Program Files".to_string(),
        "Program Files (x86)".to_string(),
        "ProgramData".to_string(),
        "System Volume Information".to_string(),
        "$Recycle.Bin".to_string(),
        "$RECYCLE.BIN".to_string(),
        "node_modules".to_string(),
        "venv".to_string(),
        ".venv".to_string(),
        "env".to_string(),
        ".env".to_string(),
        "__pycache__".to_string(),
        "AppData".to_string(),
        "tmp".to_string(),
        "temp".to_string(),
        ".git".to_string(),
    ];

    #[cfg(target_os = "macos")]
    {
        exclude.extend(vec!["Library".to_string(), "System".to_string()]);
    }

    #[cfg(target_os = "linux")]
    {
        exclude.extend(vec![
            "bin".to_string(),
            "boot".to_string(),
            "dev".to_string(),
            "etc".to_string(),
            "lib".to_string(),
            "lib64".to_string(),
            "proc".to_string(),
            "sys".to_string(),
            "var".to_string(),
        ]);
    }

    exclude
}

fn should_skip_dir(path: &Path, exclude_dirs: &[String]) -> bool {
    let dir_name = path
        .file_name()
        .unwrap_or_default()
        .to_string_lossy()
        .to_lowercase();

    // Skip hidden directories
    if dir_name.starts_with('.') {
        return true;
    }

    // Skip excluded directories
    let path_str = path.to_string_lossy().to_lowercase();
    for excluded in exclude_dirs {
        if path_str.contains(&excluded.to_lowercase()) {
            return true;
        }
    }

    false
}

fn is_target_file(path: &Path) -> Option<String> {
    let extension = path
        .extension()
        .unwrap_or_default()
        .to_string_lossy()
        .to_lowercase();

    match extension.as_str() {
        "csv" => Some("csv".to_string()),
        "xlsx" | "xls" | "xlsm" | "xlsb" => Some("excel".to_string()),
        "txt" | "md" | "log" | "rtf" => Some("text".to_string()),
        "json" => Some("json".to_string()),
        _ => None,
    }
}

fn process_file(path: &Path) -> Option<(String, FileInfo)> {
    let category = is_target_file(path)?;

    let metadata = match fs::metadata(path) {
        Ok(meta) => meta,
        Err(_) => return None,
    };

    let modified = match metadata.modified() {
        Ok(time) => {
            let datetime: DateTime<Local> = time.into();
            datetime.to_rfc3339()
        }
        Err(_) => "unknown".to_string(),
    };

    let created = match metadata.created() {
        Ok(time) => {
            let datetime: DateTime<Local> = time.into();
            datetime.to_rfc3339()
        }
        Err(_) => "unknown".to_string(),
    };

    let file_info = FileInfo {
        path: path.to_string_lossy().to_string(),
        size: metadata.len(),
        modified,
        created,
    };

    Some((category, file_info))
}

fn is_hidden_entry(entry: &DirEntry) -> bool {
    entry
        .file_name()
        .to_str()
        .map(|s| s.starts_with('.'))
        .unwrap_or(false)
}

fn scan_directory(
    dir: &Path,
    exclude_dirs: &[String],
    results: Arc<Mutex<ScanResults>>,
    file_count: Arc<Mutex<usize>>,
) {
    let walker = WalkDir::new(dir).follow_links(false).into_iter();

    // Filter out errors and apply exclusion rules
    let entries = walker
        .filter_entry(|e| {
            !is_hidden_entry(e) && (e.path() == dir || !should_skip_dir(e.path(), exclude_dirs))
        })
        .filter_map(|e| e.ok())
        .filter(|e| e.file_type().is_file());

    // Process files in parallel
    entries.par_bridge().for_each(|entry| {
        if let Some((category, file_info)) = process_file(entry.path()) {
            let mut results_lock = results.lock().unwrap();
            let mut count_lock = file_count.lock().unwrap();

            match category.as_str() {
                "csv" => results_lock.csv.push(file_info),
                "excel" => results_lock.excel.push(file_info),
                "text" => results_lock.text.push(file_info),
                "json" => results_lock.json.push(file_info),
                _ => {}
            }

            *count_lock += 1;
        }
    });
}

fn save_results(
    results: &ScanResults,
    summary: &Summary,
    output_dir: &Path,
) -> Result<(), Box<dyn std::error::Error>> {
    // Create output directory if it doesn't exist
    fs::create_dir_all(output_dir)?;

    // Create timestamp string for filenames
    let timestamp = chrono::Local::now().format("%Y%m%d_%H%M%S").to_string();

    // Create output data structure
    let output_data: OutputData = OutputData {
        summary: (*summary).clone(),
        results: (*results).clone(),
    };

    // Save JSON results
    let json_path = output_dir.join(format!("scan_results_{}.json", timestamp));
    let json_content = serde_json::to_string_pretty(&output_data)?;
    fs::write(&json_path, json_content)?;

    // Save text summary
    let summary_path = output_dir.join(format!("summary_{}.txt", timestamp));
    let mut summary_content = String::new();
    summary_content.push_str("File Scanner Summary\n");
    summary_content.push_str("==================\n\n");
    summary_content.push_str(&format!("Scan completed: {}\n", summary.timestamp));
    summary_content.push_str(&format!("Platform: {}\n", summary.platform));
    summary_content.push_str(&format!(
        "Directories scanned: {}\n",
        summary.scan_dirs.join(", ")
    ));
    summary_content.push_str(&format!("Total files found: {}\n\n", summary.file_count));
    summary_content.push_str("Files by category:\n");
    for (category, count) in &summary.categories {
        summary_content.push_str(&format!("  - {}: {}\n", category, count));
    }
    summary_content.push_str(&format!(
        "\nFull results saved to: {}\n",
        json_path.to_string_lossy()
    ));
    fs::write(summary_path, summary_content)?;

    Ok(())
}

#[cfg(target_os = "windows")]
mod outlook {
    use super::{EmailInfo, FolderInfo};
    use log::{error, info};
    use std::sync::{Arc, Mutex};
    use winapi::um::combaseapi::{CoInitialize, CoUninitialize};
    use winreg::enums::HKEY_CURRENT_USER;
    use winreg::RegKey;

    pub fn scan_outlook() -> Vec<EmailInfo> {
        info!("Scanning Outlook folders...");
        let mut results = Vec::new();

        unsafe {
            CoInitialize(std::ptr::null_mut());
        }

        // Use Windows Registry to find Outlook profiles
        let hkcu = RegKey::predef(HKEY_CURRENT_USER);

        // Check if Outlook is installed
        match hkcu.open_subkey("Software\\Microsoft\\Office\\Outlook\\Profiles") {
            Ok(profiles_key) => {
                for profile_result in profiles_key.enum_keys().filter_map(|r| r.ok()) {
                    let profile_name = profile_result;

                    let email_info = EmailInfo {
                        name: profile_name,
                        folders: Vec::new(), // We won't actually populate folder details for security reasons
                    };

                    results.push(email_info);
                }
            }
            Err(_) => {
                info!("Outlook profiles not found or access denied");
            }
        }

        unsafe {
            CoUninitialize();
        }

        // Just return the profile names - actual email scanning would require
        // more permissions than a scanner should have
        results
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize logger
    env_logger::init();

    // Parse command line arguments
    let opt = Opt::from_args();

    // Set the number of threads if specified
    if opt.threads > 0 {
        rayon::ThreadPoolBuilder::new()
            .num_threads(opt.threads)
            .build_global()?;
    }

    // Start timing
    let start_time = std::time::Instant::now();

    // Setup scan directories
    let scan_dirs = opt.dirs.unwrap_or_else(get_default_scan_dirs);

    // Setup exclude directories
    let exclude_dirs = opt.exclude.unwrap_or_else(get_default_exclude_dirs);

    // Setup output directory
    let output_dir = opt.output.unwrap_or_else(|| {
        let mut path = dirs_next::home_dir().unwrap_or_else(|| PathBuf::from("."));
        path.push("file_scanner_results");
        path
    });

    println!("Starting file scan in: {:?}", scan_dirs);

    // Initialize results
    let results = Arc::new(Mutex::new(ScanResults {
        csv: Vec::new(),
        excel: Vec::new(),
        text: Vec::new(),
        json: Vec::new(),
        email: Vec::new(),
    }));

    let file_count = Arc::new(Mutex::new(0));

    // Scan directories in parallel
    scan_dirs.par_iter().for_each(|dir| {
        if dir.exists() {
            println!("Scanning {}...", dir.to_string_lossy());
            scan_directory(
                dir,
                &exclude_dirs,
                Arc::clone(&results),
                Arc::clone(&file_count),
            );
        }
    });

    // Scan Outlook on Windows
    #[cfg(target_os = "windows")]
    {
        let mut results_lock = results.lock().unwrap();
        results_lock.email = scan_outlook();
    }

    // Calculate duration
    let duration = start_time.elapsed().as_secs_f64();

    // Create summary
    let result_data = results.lock().unwrap();
    let total_count = *file_count.lock().unwrap();

    let scan_dirs_str: Vec<String> = scan_dirs
        .iter()
        .map(|p| p.to_string_lossy().to_string())
        .collect();

    let mut categories = HashMap::new();
    categories.insert("csv".to_string(), result_data.csv.len());
    categories.insert("excel".to_string(), result_data.excel.len());
    categories.insert("text".to_string(), result_data.text.len());
    categories.insert("json".to_string(), result_data.json.len());
    categories.insert("email".to_string(), result_data.email.len());

    let summary = Summary {
        timestamp: chrono::Local::now().to_rfc3339(),
        platform: env::consts::OS.to_string(),
        scan_dirs: scan_dirs_str,
        file_count: total_count,
        duration,
        categories,
    };

    // Save results
    save_results(&result_data, &summary, &output_dir)?;

    println!("Scan completed in {:.2} seconds", duration);
    println!("Found {} files", total_count);
    println!("Results saved to {}", output_dir.to_string_lossy());

    Ok(())
}
