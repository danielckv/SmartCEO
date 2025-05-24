#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::api::dialog::FileDialogBuilder;
use tauri::api::shell::Command; // CommandEvent is not used in the final version of run_cli_command
use tauri::Manager; // For AppHandle
// use std::path::PathBuf; // Not strictly needed after changes to get_cli_script_path

#[tauri::command]
async fn select_pst_file() -> Result<Option<String>, String> {
    let (sender, receiver) = std::sync::mpsc::channel();
    FileDialogBuilder::new()
        .add_filter("PST files", &["pst"])
        .pick_file(move |path_buf| {
            sender.send(path_buf).unwrap_or_else(|e| eprintln!("Failed to send path from dialog: {:?}", e));
        });
    
    match receiver.recv().map_err(|e| format!("Failed to receive path: {}", e))? {
        Some(path) => Ok(Some(path.to_string_lossy().to_string())),
        None => Ok(None),
    }
}

#[tauri::command]
async fn select_directory() -> Result<Option<String>, String> {
    let (sender, receiver) = std::sync::mpsc::channel();
    FileDialogBuilder::new().pick_folder(move |path_buf| {
        sender.send(path_buf).unwrap_or_else(|e| eprintln!("Failed to send path from dialog: {:?}", e));
    });

    match receiver.recv().map_err(|e| format!("Failed to receive path: {}", e))? {
        Some(path) => Ok(Some(path.to_string_lossy().to_string())),
        None => Ok(None),
    }
}

// Helper function to determine the path to the engine_cli.py script
// This function now uses Tauri's resource resolver.
fn get_cli_script_path(app_handle: &tauri::AppHandle) -> Result<String, String> {
    // Assumes "engine_cli.py" is the name of the resource as bundled.
    // This should correspond to an entry like "../../vector_engine/src/engine_cli.py"
    // in "tauri.conf.json" resources, which gets bundled with "engine_cli.py" as its resource name.
    let resource_path = app_handle.path_resolver()
        .resolve_resource("engine_cli.py") // This looks for "engine_cli.py" at the root of bundled resources
        .ok_or_else(|| "Failed to resolve resource path for engine_cli.py. Ensure it's listed in tauri.conf.json resources.".to_string())?;
    
    Ok(resource_path.to_string_lossy().to_string())
}


#[tauri::command]
async fn run_cli_command(app_handle: tauri::AppHandle, sub_command: String, args: Vec<String>) -> Result<String, String> {
    let python_interpreter = if cfg!(windows) { "python" } else { "python3" };
    
    // Get the script path using the updated helper function, handling potential error
    let script_path = get_cli_script_path(&app_handle)?; // Use '?' to propagate error

    let mut command_args = vec![script_path.clone()]; 
    command_args.push(sub_command.clone()); 
    command_args.extend(args); 
    
    println!("Attempting to run command: '{}' with args: {:?}", python_interpreter, command_args);

    // Spawn the command
    let (_rx, child) = Command::new(python_interpreter) // Renamed mut rx to _rx as it's not used
        .args(&command_args) 
        .spawn()
        .map_err(|e| {
            let err_msg = format!("Failed to spawn command '{}' with script '{}': {}. Check if Python is installed and the script path is correct.", python_interpreter, script_path, e);
            eprintln!("{}", err_msg); // Log to Rust console
            err_msg // Return error message to frontend
        })?;

    // Wait for the command to complete and get all output
    let output = child.wait_with_output().await.map_err(|e| format!("Failed to wait for command: {}", e))?;

    if output.status.success() {
        let stdout_str = String::from_utf8_lossy(&output.stdout).to_string();
        println!("CLI stdout:\n{}", stdout_str); // Log to Rust console
        Ok(stdout_str) // Return stdout to frontend
    } else {
        let stderr_str = String::from_utf8_lossy(&output.stderr).to_string();
        eprintln!("CLI stderr:\n{}", stderr_str); // Log to Rust console
        // It's often useful to also include stdout in the error if stderr is empty but it failed
        let stdout_str = String::from_utf8_lossy(&output.stdout).to_string();
        if stderr_str.is_empty() && !stdout_str.is_empty() {
             Err(format!("CLI command failed with status {}. Output:\n{}", output.status, stdout_str))
        } else if stderr_str.is_empty() && stdout_str.is_empty() && !output.status.success() {
             Err(format!("CLI command failed with status {} and no output.", output.status))
        }
        else {
             Err(format!("CLI command failed with status {}. Error:\n{}", output.status, stderr_str))
        }
    }
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            select_pst_file,
            select_directory,
            run_cli_command
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
