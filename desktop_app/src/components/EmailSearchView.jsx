import React, { useState } from 'react';
import { invoke } from '@tauri-apps/api/tauri';

function EmailSearchView() {
  const [query, setQuery] = useState('');
  const [dbPath, setDbPath] = useState(''); // For storing the path to the DB directory
  const [searchResultsLog, setSearchResultsLog] = useState('');
  const [formattedResults, setFormattedResults] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  const handleSelectDbDirectory = async () => {
    setIsLoading(true);
    setSearchResultsLog(prev => prev + "Requesting DB directory selection...\n");
    try {
      const selected = await invoke('select_directory'); // Reusing the same command
      if (selected) {
        setDbPath(selected);
        setSearchResultsLog(prev => prev + `Selected DB directory: ${selected}\n`);
      } else {
        setSearchResultsLog(prev => prev + "DB directory selection cancelled.\n");
      }
    } catch (error) {
      setSearchResultsLog(prev => prev + `Error selecting DB directory: ${error}\n`);
      console.error("Error select_directory (for DB):", error);
    }
    setIsLoading(false);
  };

  const handleSearch = async () => {
    if (!query.trim()) {
      setSearchResultsLog("Please enter a search query.\n");
      setFormattedResults([]);
      return;
    }
    if (!dbPath.trim()) {
      setSearchResultsLog("Please select the database directory first.\n");
      setFormattedResults([]);
      return;
    }

    setIsLoading(true);
    setSearchResultsLog(prev => prev + `Searching for: "${query}" in DB at "${dbPath}"...\n`);
    setFormattedResults([]); // Clear previous results

    try {
      const resultJsonString = await invoke('run_cli_command', {
        subCommand: 'search',
        args: ['--query', query, '--db_path', dbPath] 
        // Add other args like --n_results, --collection_name if UI elements are added
      });
      
      setSearchResultsLog(prev => prev + `Raw search result: ${resultJsonString}\n`);
      
      // Attempt to parse the JSON string result
      const parsedResult = JSON.parse(resultJsonString);
      
      if (parsedResult.error) {
        setSearchResultsLog(prev => prev + `Search error from CLI: ${parsedResult.error}\n`);
        setFormattedResults([]);
      } else if (parsedResult.search_results) {
        setFormattedResults(parsedResult.search_results); // Expecting an array of result objects
        setSearchResultsLog(prev => prev + `Search successful. Displaying ${parsedResult.search_results.length} results.\n`);
        if (parsedResult.explanation) {
            setSearchResultsLog(prev => prev + `Search explanation: ${parsedResult.explanation}\n`);
        }
        if (parsedResult.query_type === "count" && parsedResult.count !== undefined) {
            setSearchResultsLog(prev => prev + `This was a count query. Total matching items: ${parsedResult.count}.\n`);
        }
      } else {
        setSearchResultsLog(prev => prev + "Search completed, but no 'search_results' field in output.\n");
        setFormattedResults([]);
      }

    } catch (error) {
      // Error might be a string from Rust or an Error object if JSON parsing fails
      const errorMessage = typeof error === 'string' ? error : (error.message || "Unknown error during search.");
      setSearchResultsLog(prev => prev + `Error during search: ${errorMessage}\n`);
      console.error("Error run_cli_command (search):", error);
      setFormattedResults([]);
    }
    setIsLoading(false);
  };

  return (
    <div className="view">
      <h2>Email Search</h2>
      <p>Select the directory containing the email database (created by the PST Processor) and enter your search query.</p>

      <div className="form-group">
        <label htmlFor="dbPathInput">Database Directory Path:</label>
        <input 
          type="text" 
          id="dbPathInput"
          placeholder="Click 'Select DB Directory' to choose..." 
          value={dbPath}
          readOnly 
        />
        <button onClick={handleSelectDbDirectory} disabled={isLoading}>Select DB Directory</button>
      </div>

      <div className="form-group">
        <label htmlFor="searchInput">Search Query:</label>
        <input 
          type="search" 
          id="searchInput"
          placeholder="Enter search query..." 
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
          disabled={isLoading}
        />
      </div>
      
      <button onClick={handleSearch} className="action-button" disabled={isLoading || !dbPath || !query}>
        {isLoading ? 'Searching...' : 'Search'}
      </button>
      
      <h3>Search Results:</h3>
      <div className="results-area">
        {formattedResults.length === 0 && <p>No results to display. Enter a query and click Search.</p>}
        {formattedResults.map((result, index) => (
          <div key={result.id || index} className="search-result-item">
            <h4>{result.metadata?.subject || 'No Subject'}</h4>
            <p><strong>From:</strong> {result.metadata?.sender_name || 'N/A'}</p>
            <p><strong>Folder:</strong> {result.metadata?.folder_path || 'N/A'}</p>
            <p><strong>Distance:</strong> {result.distance !== null && result.distance !== undefined ? result.distance.toFixed(4) : 'N/A'}</p>
            <p className="body-preview">{result.metadata?.body?.substring(0, 200) || 'No body preview available'}...</p>
          </div>
        ))}
      </div>

      <h3>Raw Log & Output:</h3>
      <textarea 
        className="log-area"
        readOnly 
        value={searchResultsLog} 
        placeholder="Search status and raw output will appear here..."
      />
    </div>
  );
}

export default EmailSearchView;
