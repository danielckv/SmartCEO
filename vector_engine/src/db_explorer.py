import json
import re
from typing import Any, Dict, List
import chromadb
# import gradio as gr # Removed Gradio
import requests
import logging # Added
import sys # Added
import argparse # Added

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Removed CHROMA_DB_PATH global constant

def get_chroma_client(db_path: str): # Modified signature
    try:
        client = chromadb.PersistentClient(path=db_path)
        logging.info(f"Successfully connected to ChromaDB at {db_path}")
        return client
    except Exception as e:
        logging.error(f"Error connecting to ChromaDB at '{db_path}': {e}", exc_info=True)
        raise ConnectionError(f"Error connecting to ChromaDB at '{db_path}': {str(e)}")


def semantic_search(query: str, db_path: str, collection_name: str, n_results: int = 5) -> List[Dict[str, Any]]: # Modified signature
    """
    Perform semantic search on the email collection.
    """
    results_list = [] # Renamed to avoid conflict with 'results' from query

    try:
        client = get_chroma_client(db_path)
        # collections = client.list_collections() # Optional: for debugging
        # logging.debug(f"Available collections: {[col.name for col in collections]}")

        logging.info(f"Attempting to load collection: '{collection_name}'")
        collection = client.get_collection(name=collection_name)
        logging.info(f"Collection '{collection_name}' loaded successfully.")

        query_results = collection.query( # Results from ChromaDB
            query_texts=[query],
            n_results=n_results
        )
        
        # Format the results
        if query_results and query_results["metadatas"] and len(query_results["metadatas"]) > 0:
            for i, metadata in enumerate(query_results["metadatas"][0]):
                results_list.append({
                    "id": query_results["ids"][0][i],
                    "metadata": metadata,
                    "distance": query_results["distances"][0][i] if query_results.get("distances") and query_results["distances"][0] else None
                })
        logging.info(f"Found {len(results_list)} results for query '{query}' in collection '{collection_name}'.")

    except ConnectionError: # Propagate if get_chroma_client fails
        raise
    except Exception as e: # Catch other ChromaDB errors (e.g., collection not found)
        logging.error(f"Error during semantic search in collection '{collection_name}': {e}", exc_info=True)
        raise LookupError(f"Error during semantic search in collection '{collection_name}': {e}. Ensure collection exists and data is loaded.")
    
    return results_list


def query_ollama(prompt: str, ollama_model: str, ollama_url: str = "http://localhost:11434/api/generate"): # Modified signature
    """
    Query the Ollama API with a given prompt.
    """
    # Removed global OLLAMA_MODEL reference
    logging.info(f"Querying Ollama model '{ollama_model}' at '{ollama_url}'")
    try:
        response = requests.post(
            ollama_url, # Use parameter
            json={
                "model": ollama_model, # Use parameter
                "prompt": prompt,
                "stream": False
            },
            timeout=20 # Increased timeout slightly
        )

        if response.status_code == 200:
            logging.info("Successfully received response from Ollama.")
            return response.json().get("response", "")
        else:
            err_msg = f"Error querying Ollama ({ollama_model} at {ollama_url}): {response.status_code} - {response.text}"
            logging.error(err_msg)
            raise ConnectionError(err_msg)
    except requests.exceptions.RequestException as e: # More specific exception for requests
        err_msg = f"Network exception when querying Ollama ({ollama_model} at {ollama_url}): {e}"
        logging.error(err_msg, exc_info=True)
        raise ConnectionError(err_msg)
    except Exception as e: # Catch any other unexpected errors
        err_msg = f"Unexpected exception when querying Ollama ({ollama_model} at {ollama_url}): {e}"
        logging.error(err_msg, exc_info=True)
        raise ConnectionError(err_msg)


def parse_query_with_ollama(query: str, ollama_model: str, ollama_url: str) -> Dict[str, Any]: # Modified signature
    """
    Use Ollama to parse the natural language query, with a regex fallback.
    """
    prompt = f"""
    Parse the following email search query and extract key information.
    Query: "{query}"

    Please provide a JSON response with the following structure:
    {{
        "is_count_query": true/false,
        "subject_filter": "...",
        "sender_filter": "...",
        "folder_filter": "...",
        "body_filter": "...",
        "date_filter": "...",
        "language_detection": "...",
        "query_type": "count"/"search"
    }}

    Only include filters that are explicitly or implicitly mentioned in the query. If a filter is not mentioned, set its value to null.
    For 'language_detection', attempt to identify the language of the query (e.g., "en", "es", "fr").
    'query_type' should be "count" if the query asks for a number of items, otherwise "search".
    """

    try:
        logging.info("Attempting to parse query with Ollama...")
        response_text = query_ollama(prompt, ollama_model, ollama_url) # Pass params

        if response_text:
            # Extract the JSON part from the response (handle potential non-JSON text)
            # This regex is a bit more robust to variations in Ollama's output formatting
            json_match = re.search(r'\{\s*("is_count_query"|is_count_query)[\s\S]*\}', response_text, re.MULTILINE | re.IGNORECASE)
            if json_match:
                json_str = json_match.group(0)
                try:
                    parsed_info = json.loads(json_str)
                    logging.info("Successfully parsed query with Ollama.")
                    return parsed_info
                except json.JSONDecodeError as json_err:
                    logging.warning(f"Could not parse JSON from Ollama response: {json_err}. Response snippet: '{json_str[:200]}...'")
            else:
                logging.warning(f"No JSON object found in Ollama response. Response: '{response_text[:200]}...'")
    except ConnectionError as e: # Catch if Ollama is down or query_ollama raises ConnectionError
        logging.warning(f"Ollama connection error during query parsing: {e}. Falling back to regex parsing.")
    except Exception as e: # Catch other unexpected errors from Ollama parsing attempt
        logging.warning(f"Unexpected error using Ollama for query parsing: {e}. Falling back to regex parsing.", exc_info=True)

    # Fallback to regex parsing if Ollama fails or is unavailable
    logging.info("Falling back to regex-based query parsing.")
    is_count = any(re.search(pattern, query, re.IGNORECASE) for pattern in [
        r"how many emails?", r"count.*emails?", r"number of emails?", r"total emails?"
    ])
    
    subject_match = re.search(r"subject\s+[\"\']?([^\"\',]+)[\"\']?", query, re.IGNORECASE)
    sender_match = re.search(r"(?:from|sender is|sent by)\s+[\"\']?([^\"\',]+)[\"\']?", query, re.IGNORECASE)
    folder_match = re.search(r"(?:in\s+folder|folder\s+is|folder:)\s+[\"\']?([^\"\',]+)[\"\']?", query, re.IGNORECASE)
    # Basic body filter example (can be expanded)
    body_match = re.search(r"(?:body contains|content includes)\s+[\"\']?([^\"\',]+)[\"\']?", query, re.IGNORECASE)


    return {
        "is_count_query": is_count,
        "subject_filter": subject_match.group(1).strip() if subject_match else None,
        "sender_filter": sender_match.group(1).strip() if sender_match else None,
        "folder_filter": folder_match.group(1).strip() if folder_match else None,
        "body_filter": body_match.group(1).strip() if body_match else None, # Added basic body filter
        "date_filter": None, # Date parsing can be complex, keeping as None for now
        "language_detection": "en", # Default, could be improved with a small lang detect lib if needed
        "query_type": "count" if is_count else "search"
    }

# Removed format_text_for_html as it's Gradio specific

def perform_search_logic(query: str, db_path: str, collection_name: str, 
                         use_ollama_parsing: bool = True, 
                         ollama_model: str = "llama3.1:latest", 
                         ollama_url: str = "http://localhost:11434/api/generate", 
                         n_results: int = 20) -> Dict[str, Any]:
    """
    Core logic for performing semantic search, optionally using Ollama for query parsing.
    Returns a dictionary with structured search results.
    """
    logging.info(f"Performing search for query: '{query}' with n_results={n_results}")
    
    # Perform initial semantic search
    try:
        search_results_raw = semantic_search(query, db_path, collection_name, n_results=n_results)
    except LookupError as e: # If collection not found or other semantic search error
        logging.error(f"Semantic search failed: {e}")
        raise # Re-raise to be handled by the caller
    except ConnectionError as e: # If ChromaDB connection failed
        logging.error(f"ChromaDB connection failed: {e}")
        raise # Re-raise

    result_data = {
        "query": query,
        "parsed_query": {},
        "explanation": "",
        "query_type": "search", # Default type
        "count": 0, # Default count
        "search_results": [],
    }

    parsed_query_info = {}
    if use_ollama_parsing:
        try:
            # This will use Ollama or fall back to regex if Ollama fails
            parsed_query_info = parse_query_with_ollama(query, ollama_model, ollama_url)
        except ConnectionError as e: # Should be caught within parse_query_with_ollama, but as a safeguard
            logging.warning(f"Ollama parsing failed due to connection error: {e}. Using regex fallback only.")
            # Ensure regex fallback is explicitly called if the above failed before returning
            parsed_query_info = parse_query_with_ollama(query, "fallback_dummy_model", "fallback_dummy_url") # Forces regex
    else: # use_ollama_parsing is False, so force regex
        logging.info("Ollama parsing disabled. Using regex-based parsing.")
        # Call parse_query_with_ollama with dummy values that would cause it to use regex,
        # or modify parse_query_with_ollama to have a specific flag for regex.
        # For now, this will trigger its internal fallback.
        parsed_query_info = parse_query_with_ollama(query, "fallback_dummy_model_for_regex", "http://dummyurl")


    result_data["parsed_query"] = parsed_query_info
    result_data["query_type"] = parsed_query_info.get("query_type", "search")


    # Filter results based on parsed query
    filtered_results = search_results_raw
    current_explanation_parts = []

    # Helper to check if a filter value exists and is a non-empty string
    def is_valid_filter(value):
        return value and isinstance(value, str) and value.strip()

    if is_valid_filter(parsed_query_info.get("subject_filter")):
        subject_filter_val = parsed_query_info["subject_filter"].lower()
        filtered_results = [r for r in filtered_results if r["metadata"].get("subject") and subject_filter_val in str(r["metadata"]["subject"]).lower()]
        current_explanation_parts.append(f"subject containing '{parsed_query_info['subject_filter']}'")
    
    if is_valid_filter(parsed_query_info.get("sender_filter")):
        sender_filter_val = parsed_query_info["sender_filter"].lower()
        filtered_results = [r for r in filtered_results if r["metadata"].get("sender_name") and sender_filter_val in str(r["metadata"]["sender_name"]).lower()]
        current_explanation_parts.append(f"sender containing '{parsed_query_info['sender_filter']}'")

    if is_valid_filter(parsed_query_info.get("folder_filter")):
        folder_filter_val = parsed_query_info["folder_filter"].lower()
        filtered_results = [r for r in filtered_results if r["metadata"].get("folder_path") and folder_filter_val in str(r["metadata"]["folder_path"]).lower()]
        current_explanation_parts.append(f"folder containing '{parsed_query_info['folder_filter']}'")

    if is_valid_filter(parsed_query_info.get("body_filter")):
        body_filter_val = parsed_query_info["body_filter"].lower()
        filtered_results = [r for r in filtered_results if r["metadata"].get("body") and body_filter_val in str(r["metadata"]["body"]).lower()]
        current_explanation_parts.append(f"body containing '{parsed_query_info['body_filter']}'")
    
    if current_explanation_parts:
        result_data["explanation"] = "Filtered for " + ", and ".join(current_explanation_parts) + "."
    else:
        result_data["explanation"] = "No specific filters applied beyond semantic search."


    if result_data["query_type"] == "count" or parsed_query_info.get("is_count_query"):
        result_data["count"] = len(filtered_results)
        result_data["query_type"] = "count" # Ensure it's set
        result_data["explanation"] += f" Found {result_data['count']} matching emails after filtering."
        # For count queries, we might not need to return all results, but API returns them for now.
        # Client can choose to display only count or also the (potentially large) list.
    
    result_data["search_results"] = filtered_results[:n_results] # Ensure we don't exceed n_results after filtering
    if result_data["query_type"] != "count": # If not a count query, set count to number of returned results
        result_data["count"] = len(result_data["search_results"])

    logging.info(f"Search logic complete. Explanation: {result_data['explanation']}")
    return result_data

# Removed Gradio specific functions: format_results_as_html, search_emails, check_ollama_status
# Removed OLLAMA_MODEL global variable
# Removed Gradio UI (gr.Blocks)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Perform semantic search on email data via CLI.")
    parser.add_argument("query", help="Search query string.")
    parser.add_argument("db_path", help="Path to the ChromaDB database directory.")
    parser.add_argument("--collection_name", default="outlook_emails", help="Name of the ChromaDB collection (default: outlook_emails).")
    parser.add_argument("--n_results", type=int, default=10, help="Number of search results to return (default: 10).")
    parser.add_argument("--use_ollama", action="store_true", help="Enable query parsing with Ollama (if available).")
    parser.add_argument("--ollama_model", default="llama3.1:latest", help="Ollama model name (default: llama3.1:latest).")
    parser.add_argument("--ollama_url", default="http://localhost:11434/api/generate", help="Ollama API URL (default: http://localhost:11434/api/generate).")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose (DEBUG level) logging output.")
            
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        for handler in logging.getLogger().handlers:
            handler.setLevel(logging.DEBUG)
        logging.debug("Verbose logging enabled.")

    try:
        logging.info(f"CLI search initiated with query: '{args.query}'")
        search_results_dict = perform_search_logic(
            query=args.query,
            db_path=args.db_path,
            collection_name=args.collection_name,
            use_ollama_parsing=args.use_ollama,
            ollama_model=args.ollama_model,
            ollama_url=args.ollama_url,
            n_results=args.n_results
        )
        # Output results as JSON to stdout
        print(json.dumps(search_results_dict, indent=2, ensure_ascii=False))
        logging.info("CLI search completed successfully.")

    except (ConnectionError, LookupError, Exception) as e: # Catch specific errors from logic + general
        logging.critical(f"An error occurred during search: {e}", exc_info=True)
        # Output a JSON error object to stderr
        print(json.dumps({"error": str(e), "query": args.query}, indent=2, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)