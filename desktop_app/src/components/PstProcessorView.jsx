import React, { useState } from 'react';
import { invoke } from '@tauri-apps/api/tauri';
// Dialog API is used from backend, so no direct import needed here for select_pst_file / select_directory

function PstProcessorView() {
  const [pstPath, setPstPath] = useState('');
  const [outputPath, setOutputPath] = useState('');
  const [processingLog, setProcessingLog] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSelectPstFile = async () => {
    setIsLoading(true);
    setProcessingLog(prev => prev + "Requesting PST file selection...\n");
    try {
      const selected = await invoke('select_pst_file');
      if (selected) {
        setPstPath(selected);
        setProcessingLog(prev => prev + `Selected PST file: ${selected}\n`);
      } else {
        setProcessingLog(prev => prev + "PST file selection cancelled.\n");
      }
    } catch (error) {
      setProcessingLog(prev => prev + `Error selecting PST file: ${error}\n`);
      console.error("Error select_pst_file:", error);
    }
    setIsLoading(false);
  };

  const handleSelectDataDirectory = async () => {
    setIsLoading(true);
    setProcessingLog(prev => prev + "Requesting output directory selection...\n");
    try {
      const selected = await invoke('select_directory');
      if (selected) {
        setOutputPath(selected);
        setProcessingLog(prev => prev + `Selected output directory: ${selected}\n`);
      } else {
        setProcessingLog(prev => prev + "Output directory selection cancelled.\n");
      }
    } catch (error) {
      setProcessingLog(prev => prev + `Error selecting output directory: ${error}\n`);
      console.error("Error select_directory:", error);
    }
    setIsLoading(false);
  };

  const handleStartProcessing = async () => {
    if (!pstPath || !outputPath) {
      setProcessingLog(prev => prev + "Error: PST file path and Output data directory must be set.\n");
      return;
    }
    setIsLoading(true);
    setProcessingLog(prev => prev + `Starting full processing...\n`);

    // Step 1: Process PST to JSONL
    const jsonlFileName = "emails.jsonl"; // Fixed name for the output JSONL
    const jsonlPath = `${outputPath}/${jsonlFileName}`; // Construct full path
    setProcessingLog(prev => prev + `Step 1: Processing PST file '${pstPath}' to JSONL file '${jsonlPath}'...\n`);

    try {
      const processResult = await invoke('run_cli_command', { 
        subCommand: 'process-pst', 
        args: ['--pst_path', pstPath, '--jsonl_path', jsonlPath] 
      });
      setProcessingLog(prev => prev + `PST processing output: ${processResult}\n`);
      setProcessingLog(prev => prev + "Step 1: PST processing complete.\n");

      // Step 2: Load data from JSONL into ChromaDB
      setProcessingLog(prev => prev + `Step 2: Loading data from '${jsonlPath}' into ChromaDB at '${outputPath}'...\n`);
      // Assuming default collection name and model name for now.
      // These could be made configurable in the UI later.
      const loadResult = await invoke('run_cli_command', {
        subCommand: 'load-data',
        args: [
          '--jsonl_path', jsonlPath, 
          '--db_path', outputPath 
          // '--collection_name', 'my_emails', // Example if needed
          // '--model_name', 'all-MiniLM-L6-v2' // Example if needed
        ]
      });
      setProcessingLog(prev => prev + `Data loading output: ${loadResult}\n`);
      setProcessingLog(prev => prev + "Step 2: Data loading complete.\nFull processing finished.\n");

    } catch (error) {
      setProcessingLog(prev => prev + `Error during processing: ${error}\n`);
      console.error("Error run_cli_command (processing):", error);
    }
    setIsLoading(false);
  };

  return (
    <div className="view">
      <h2>PST Processor & Data Loader</h2>
      <p>Select a PST file and an output directory. The PST will be processed into a JSONL file, and then the data will be loaded into a Vector DB (ChromaDB) in the same output directory.</p>
      
      <div className="form-group">
        <label htmlFor="pstPath">PST File Path:</label>
        <input 
          type="text" 
          id="pstPathInput" // Changed id to avoid conflict if label's htmlFor="pstPath" points to a non-input
          placeholder="Click 'Select PST File' to choose..." 
          value={pstPath}
          readOnly // Path is set via dialog
        />
        <button onClick={handleSelectPstFile} disabled={isLoading}>Select PST File</button>
      </div>
      
      <div className="form-group">
        <label htmlFor="outputPath">Output Data Directory:</label>
        <input 
          type="text" 
          id="outputPathInput" // Changed id
          placeholder="Click 'Select Data Directory' to choose..." 
          value={outputPath}
          readOnly // Path is set via dialog
        />
        <button onClick={handleSelectDataDirectory} disabled={isLoading}>Select Data Directory</button>
      </div>
      
      <button onClick={handleStartProcessing} className="action-button" disabled={isLoading || !pstPath || !outputPath}>
        {isLoading ? 'Processing...' : 'Start Full Processing'}
      </button>
      
      <h3>Processing Log:</h3>
      <textarea 
        className="log-area"
        readOnly 
        value={processingLog} 
        placeholder="Processing status and results will appear here..."
      />
    </div>
  );
}

export default PstProcessorView;
