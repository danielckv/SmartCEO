import json
import os
import re
from typing import Any, Dict, List, Union

import chromadb
import gradio as gr
import numpy as np
import pandas as pd
import requests

# Configuration
CHROMA_DB_PATH = './_data/chroma_db'  # Change this to your ChromaDB path

# Initialize ChromaDB client
def get_chroma_client():
    try:
        client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        return client
    except Exception as e:
        return f"Error connecting to ChromaDB: {str(e)}"


def semantic_search(query: str, n_results: int = 5) -> List[Dict[str, Any]]:
    """
    Perform semantic search on the email collection

    Args:
        query: Natural language query
        n_results: Number of results to return

    Returns:
        List of matching documents with metadata
    """

    results = []

    try:
        client = get_chroma_client()
        collections = client.list_collections()
        print(f"Available collections: {[col.name for col in collections]}")

        collection = client.get_collection(name="outlook_emails")
        print("Collection loaded successfully")

        results = collection.query(
            query_texts=[query],
            n_results=n_results
        )
    except Exception as e:
        print(f"Error: {e}")
        print("Please ensure the collection 'outlook_emails' exists and data is loaded")
        return []

    # Format the results
    formatted_results = []
    if results["metadatas"] and len(results["metadatas"]) > 0:
        for i, metadata in enumerate(results["metadatas"][0]):
            formatted_results.append({
                "id": results["ids"][0][i],
                "metadata": metadata,
                "distance": results["distances"][0][i] if "distances" in results else None
            })

    return formatted_results


def query_ollama(prompt, model=None):
    """
    Query the Ollama API with a given prompt

    Args:
        prompt: The prompt to send to Ollama
        model: The model to use (default: llama3)

    Returns:
        The response from Ollama or None if there was an error
    """
    # Use global model choice or fall back to default
    model_to_use = model or OLLAMA_MODEL or "llama3.1:latest"

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model_to_use,
                "prompt": prompt,
                "stream": False
            },
            timeout=10
        )

        if response.status_code == 200:
            return response.json().get("response", "")
        else:
            print(f"Error querying Ollama: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Exception when querying Ollama: {e}")
        return None


def parse_query_with_ollama(query: str) -> Dict[str, Any]:
    """
    Use Ollama to parse and understand the natural language query

    Args:
        query: The natural language query

    Returns:
        A dictionary with parsed query information
    """
    prompt = f"""
    Parse the following email search query and extract key information.
    Query: "{query}"

    Please provide a JSON response with the following structure:
    {{
        "is_count_query": true/false,  # Is the user asking for a count of emails?
        "subject_filter": "...",  # Any subject terms to filter by (null if none)
        "sender_filter": "...",  # Any sender terms to filter by (null if none)
        "folder_filter": "...",  # Any folder path to filter by (null if none)
        "body_filter": "...",  # Any email body content to filter by (null if none)
        "date_filter": "...",  # Any date range to filter by (null if none)
        "language_detection": "...",  # Detected language of the query
        "query_type": "count"/"search"  # The type of query
    }}

    Only include filters that are explicitly or implicitly mentioned in the query.
    """

    try:
        # Try to use Ollama for parsing
        response = query_ollama(prompt)

        if response:
            # Extract the JSON part from the response (handle potential non-JSON text)
            json_match = re.search(r'(\{.*\})', response.replace('\n', ' '), re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    print(f"Could not parse JSON from Ollama response: {json_str}")
    except Exception as e:
        print(f"Error using Ollama for query parsing: {e}")

    # Fallback to regex parsing if Ollama fails
    return {
        "is_count_query": any(re.search(pattern, query, re.IGNORECASE) for pattern in [
            r"how many emails?", r"count.*emails?", r"number of emails?", r"total emails?"
        ]),
        "subject_filter": re.search(r"subject\s+[\"\']?([^\"\',]+)[\"\']?", query, re.IGNORECASE).group(1)
        if re.search(r"subject\s+[\"\']?([^\"\',]+)[\"\']?", query, re.IGNORECASE) else None,
        "sender_filter": re.search(r"from\s+[\"\']?([^\"\',]+)[\"\']?", query, re.IGNORECASE).group(1)
        if re.search(r"from\s+[\"\']?([^\"\',]+)[\"\']?", query, re.IGNORECASE) else None,
        "folder_filter": re.search(r"in\s+folder\s+[\"\']?([^\"\',]+)[\"\']?", query, re.IGNORECASE).group(1)
        if re.search(r"in\s+folder\s+[\"\']?([^\"\',]+)[\"\']?", query, re.IGNORECASE) else None,
        "body_filter": None,
        "date_filter": None,
        "language_detection": "en",
        "query_type": "count" if any(re.search(pattern, query, re.IGNORECASE) for pattern in [
            r"how many emails?", r"count.*emails?", r"number of emails?", r"total emails?"
        ]) else "search"
    }

def format_text_for_html(text):
    """Convert newline characters (\r\n, \n, \r) to HTML <br> tags"""
    if text is None:
        return ""
    formatted_text = text.replace('\\r\\n\\r\\n', '<br>')
    formatted_text = formatted_text.replace('\\r\\n', '')
    return formatted_text

def process_query(query: str) -> Dict[str, Any]:
    """
    Process natural language query and extract information

    Args:
        query: Natural language query string

    Returns:
        Dictionary with search results and any computed metrics
    """
    # Get initial search results
    search_results = semantic_search(query, n_results=20)

    result = {
        "query": query,
        "search_results": search_results,
        "count": 0,
        "explanation": "",
        "query_type": "general",
        "parsed_query": {}
    }

    # Use Ollama to parse the query
    parsed_query = parse_query_with_ollama(query)
    result["parsed_query"] = parsed_query

    # Filter results based on a parsed query
    filtered_results = search_results

    if parsed_query.get("subject_filter"):
        subject_filter = parsed_query["subject_filter"].lower()
        filtered_results = [
            r for r in filtered_results
            if subject_filter in r["metadata"]["subject"].lower()
        ]
        result["explanation"] += f"Filtering for subject containing '{subject_filter}'. "

    if parsed_query.get("sender_filter"):
        sender_filter = parsed_query["sender_filter"].lower()
        filtered_results = [
            r for r in filtered_results
            if sender_filter in r["metadata"]["sender_name"].lower()
        ]
        result["explanation"] += f"Filtering for sender containing '{sender_filter}'. "

    if parsed_query.get("folder_filter"):
        folder_filter = parsed_query["folder_filter"].lower()
        filtered_results = [
            r for r in filtered_results
            if folder_filter in r["metadata"]["folder_path"].lower()
        ]
        result["explanation"] += f"Filtering for folder containing '{folder_filter}'. "

    if parsed_query.get("body_filter"):
        body_filter = parsed_query["body_filter"].lower()
        filtered_results = [
            r for r in filtered_results
            if body_filter in r["metadata"]["body"].lower()
        ]
        result["explanation"] += f"Filtering for body containing '{body_filter}'. "

    # Handle count queries
    if parsed_query.get("is_count_query") or parsed_query.get("query_type") == "count":
        result["count"] = len(filtered_results)
        result["query_type"] = "count"
        result["explanation"] += f"Found {result['count']} matching emails."


    result["search_results"] = filtered_results
    return result


def format_results_as_html(results):
    """Format the search results as HTML for display"""
    if not results["search_results"]:
        return "<p>No results found.</p>"

    html = ""

    # Display query understanding if available
    if "parsed_query" in results and results["parsed_query"]:
        # Create a summary of what was understood from the query
        parsed = results["parsed_query"]
        html += "<div style='background-color: #f5f5f5; padding: 10px; border-radius: 5px; margin-bottom: 15px;'>"
        html += "<h3>Query Understanding</h3>"
        html += "<ul>"

        query_type = parsed.get("query_type") or "search"
        html += f"<li><strong>Query Type:</strong> {query_type.capitalize()}</li>"

        if parsed.get("subject_filter"):
            html += f"<li><strong>Subject Filter:</strong> {parsed['subject_filter']}</li>"

        if parsed.get("sender_filter"):
            html += f"<li><strong>Sender Filter:</strong> {parsed['sender_filter']}</li>"

        if parsed.get("folder_filter"):
            html += f"<li><strong>Folder Filter:</strong> {parsed['folder_filter']}</li>"

        if parsed.get("body_filter"):
            html += f"<li><strong>Body Content Filter:</strong> {parsed['body_filter']}</li>"

        if parsed.get("language_detection") and parsed["language_detection"] != "en":
            html += f"<li><strong>Detected Language:</strong> {parsed['language_detection'].upper()}</li>"

        html += "</ul>"
        html += "</div>"

    # Add count information if it's a count query
    if results["query_type"] == "count":
        html += f"<h3>Count: {results['count']} emails</h3>"
        if results["explanation"]:
            html += f"<p><i>{results['explanation']}</i></p>"
        html += "<hr>"

    # Display each result
    for i, result in enumerate(results["search_results"]):
        metadata = result["metadata"]

        # Detect the language of the body text for display purposes
        body_preview = metadata['body'][:400] + ('...' if len(metadata['body']) > 400 else '')

        html += f"""
        <div style="margin-bottom: 15px; padding: 10px; border: 1px solid #ddd; border-radius: 5px;">
          <p><strong>Subject:</strong> {metadata['subject']}</p>
          <p><strong>From:</strong> {metadata['sender_name']}</p>
          <p><strong>Folder:</strong> {metadata['folder_path']}</p>
          <p><strong>Body:</strong> {format_text_for_html(body_preview).strip()}</p>
          <a href="javascript:void(0);" onclick="window.open('/email/{result['id']}', '_blank'); return false;">View Email</a>
          {f'<p><strong>Relevance Score:</strong> {round((1 - result.get("distance", 0)) * 100, 2)}%</p>' if result.get("distance") is not None else ''}
        </div>
        """

    return html


def search_emails(query, _ollama_model="llama3.1:latest", use_ollama=True):
    """Main function for the Gradio interface"""
    if not query.strip():
        return "Please enter a search query."

    # Configure the global Ollama model choice
    global OLLAMA_MODEL
    OLLAMA_MODEL = _ollama_model if use_ollama else None

    try:
        results = process_query(query)
        html_results = format_results_as_html(results)
        return html_results
    except Exception as e:
        import traceback
        error_message = f"""
        <div style="color: red; padding: 10px; border: 1px solid red; border-radius: 5px;">
            <h3>Error Occurred</h3>
            <p>{str(e)}</p>
            <details>
                <summary>Technical Details</summary>
                <pre>{traceback.format_exc()}</pre>
            </details>
        </div>
        """
        return error_message


# Initialize global Ollama model variable
OLLAMA_MODEL = "llama3.1:latest"


# Create Gradio interface
def check_ollama_status():
    """Check if Ollama is available and return status"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            models = response.json().get("models", [])
            model_names = [model.get("name") for model in models]
            return f"✅ Ollama is running. Available models: {', '.join(model_names) or 'None'}"
        else:
            return "❌ Ollama is running but returned an unexpected response"
    except Exception as e:
        return f"❌ Ollama is not available: {str(e)}"


with gr.Blocks(title="Semantic Email Search") as app:
    gr.Markdown("# Multilingual Semantic Email Search")

    with gr.Row():
        # Ollama status indicator
        ollama_status = gr.Textbox(label="Ollama Status", value="Checking Ollama status...")

    with gr.Row():
        query_input = gr.Textbox(
            label="Search Query",
            placeholder="Enter your search query in any language...",
            lines=2
        )

    search_button = gr.Button("Search")

    # Advanced options
    with gr.Accordion("Advanced Options", open=False):
        with gr.Row():
            ollama_model = gr.Dropdown(
                label="Ollama Model",
                choices=["llama3.1:latest", "llama3.2:latest", "deepseek-r1:8b"],
                value="llama3.1:latest"
            )
            use_ollama = gr.Checkbox(label="Use Ollama for query understanding", value=True)

    results_html = gr.HTML(label="Results")

    # Add sample data button (for demo purposes)
    with gr.Row():
        refresh_ollama = gr.Button("Refresh Ollama Status")

    sample_output = gr.Textbox(label="Sample Data Status")

    # Set up event handlers
    search_button.click(fn=search_emails, inputs=[query_input, ollama_model, use_ollama], outputs=results_html)
    refresh_ollama.click(fn=check_ollama_status, inputs=None, outputs=ollama_status)

    # Update Ollama status on page load
    app.load(fn=check_ollama_status, inputs=None, outputs=ollama_status)

    # Example queries
    gr.Examples(
        examples=[
            "find all emails that contains UAE",
            "Find emails from Aviel",
            "Show me emails in the Trash or Junk folder",
        ],
        inputs=query_input
    )

# Launch the app
if __name__ == "__main__":
    app.launch(debug=True)