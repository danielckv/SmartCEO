import gradio as gr
from db_explorer import perform_search_logic
import argparse
import logging
import json
import pandas as pd

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def search_emails_gradio(query_str: str, db_path_str: str, collection_name_str: str):
    """
    Performs a search using the provided query, ChromaDB path, and collection name,
    and returns the results formatted for display in a Gradio DataFrame.
    """
    logging.info(
        f"Performing search with query: '{query_str}', DB path: '{db_path_str}', collection: '{collection_name_str}'")
    try:
        # For simplicity, use_ollama_parsing is False, and ollama_model/ollama_url use defaults from db_explorer
        # n_results is fixed at 10
        results = perform_search_logic(
            query=query_str,
            db_path=db_path_str,
            collection_name=collection_name_str,
            use_ollama_parsing=True,
            # ollama_model and ollama_url will use defaults from perform_search_logic
            n_results=10
        )
        logging.info(f"Search successful. Found {len(results.get('ids', [[]])[0])} results.")

        # Convert results to DataFrame format
        if 'ids' in results and results['ids'] and len(results['ids'][0]) > 0:
            # Extract data from the results structure
            ids = results['ids'][0] if results.get('ids') else []
            documents = results['documents'][0] if results.get('documents') else []
            metadatas = results['metadatas'][0] if results.get('metadatas') else []
            distances = results['distances'][0] if results.get('distances') else []

            # Create a list of dictionaries for the DataFrame
            rows = []
            for i in range(len(ids)):
                row = {
                    'ID': ids[i] if i < len(ids) else '',
                    'Distance': f"{distances[i]:.4f}" if i < len(distances) else '',
                    'Document': documents[i][:200] + "..." if i < len(documents) and len(documents[i]) > 200 else (
                        documents[i] if i < len(documents) else ''),
                }

                # Add metadata fields if available
                if i < len(metadatas) and metadatas[i]:
                    metadata = metadatas[i]
                    row.update({
                        'Subject': metadata.get('subject', ''),
                        'From': metadata.get('from', ''),
                        'To': metadata.get('to', ''),
                        'Date': metadata.get('date', ''),
                        'Folder': metadata.get('folder', ''),
                    })

                rows.append(row)

            # Create DataFrame
            df = pd.DataFrame(rows)

            # Also return JSON for debugging/copying
            json_results = json.dumps(results, indent=2, ensure_ascii=False)

            return df, json_results, f"Found {len(rows)} results"
        else:
            empty_df = pd.DataFrame({"Message": ["No results found"]})
            return empty_df, json.dumps({"message": "No results found"}), "No results found"

    except ConnectionError as ce:
        error_msg = f"Error connecting to ChromaDB: {ce}"
        logging.error(error_msg)
        error_df = pd.DataFrame({"Error": [error_msg]})
        return error_df, json.dumps({"error": error_msg}), error_msg
    except LookupError as le:
        error_msg = f"Error finding collection or data: {le}"
        logging.error(error_msg)
        error_df = pd.DataFrame({"Error": [error_msg]})
        return error_df, json.dumps({"error": error_msg}), error_msg
    except Exception as e:
        error_msg = f"An unexpected error occurred: {e}"
        logging.error(error_msg, exc_info=True)  # Log stack trace for general exceptions
        error_df = pd.DataFrame({"Error": [error_msg]})
        return error_df, json.dumps({"error": error_msg}), error_msg


with gr.Blocks(theme=gr.themes.Soft()) as iface:
    gr.Markdown("# 🔍 Vector Engine Search Interface")
    gr.Markdown("Search through your email collection using semantic vector search.")

    with gr.Row():
        query_input = gr.Textbox(
            label="Search Query",
            placeholder="Enter your search query here...",
            lines=2,
            scale=3
        )

    with gr.Row():
        with gr.Column(scale=1):
            db_path_input = gr.Textbox(
                label="ChromaDB Path",
                value="_data/chroma_db",
                placeholder="Path to ChromaDB directory"
            )
        with gr.Column(scale=1):
            collection_name_input = gr.Textbox(
                label="Collection Name",
                value="outlook_emails",
                placeholder="Name of the collection"
            )

    with gr.Row():
        search_button = gr.Button("🔍 Search", variant="primary", size="lg")
        clear_button = gr.Button("🗑️ Clear", variant="secondary")

    # Status message
    status_output = gr.Textbox(label="Status", interactive=False, max_lines=1)

    # Results table
    with gr.Tab("📊 Results Table"):
        results_dataframe = gr.Dataframe(
            label="Search Results",
            interactive=False,
            wrap=True,
            max_height=400,
            column_widths=["10%", "10%", "40%", "15%", "15%", "10%"]
        )

    # Raw JSON results (collapsible)
    with gr.Tab("📋 Raw JSON"):
        json_output = gr.Code(
            label="Raw JSON Results",
            language="json",
            interactive=False,
            lines=10
        )

    # Link the search function to the Gradio interface
    search_button.click(
        fn=search_emails_gradio,
        inputs=[query_input, db_path_input, collection_name_input],
        outputs=[results_dataframe, json_output, status_output]
    )


    # Clear function
    def clear_all():
        return "", pd.DataFrame(), "", ""


    clear_button.click(
        fn=clear_all,
        outputs=[query_input, results_dataframe, json_output, status_output]
    )

if __name__ == "__main__":
    # Configure basic logging (already configured at the top, but good practice to ensure it's set if run as script)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    parser = argparse.ArgumentParser(description="Launch the Vector Engine Gradio UI.")
    parser.add_argument("--db_path", type=str, default="_data/chroma_db", help="Path to the ChromaDB directory.")
    parser.add_argument("--collection_name", type=str, default="outlook_emails",
                        help="Name of the ChromaDB collection.")
    parser.add_argument("--server_name", type=str, default="0.0.0.0",
                        help="Gradio server name (e.g., '127.0.0.1' or '0.0.0.0').")
    parser.add_argument("--server_port", type=int, default=7860, help="Gradio server port.")
    parser.add_argument("--share", action="store_true", help="Enable Gradio sharing link.")

    args = parser.parse_args()

    # Update Gradio input components with values from command-line arguments
    db_path_input.value = args.db_path
    collection_name_input.value = args.collection_name

    logging.info(f"Launching Gradio app on {args.server_name}:{args.server_port}")
    if args.share:
        logging.info("Gradio share link will be enabled.")

    iface.launch(server_name=args.server_name, server_port=args.server_port, share=args.share)