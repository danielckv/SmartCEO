import gradio as gr
from db_explorer import perform_search_logic
import argparse
import logging
import json

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def search_emails_gradio(query_str: str, db_path_str: str, collection_name_str: str) -> str:
    """
    Performs a search using the provided query, ChromaDB path, and collection name,
    and returns the results or an error message as a JSON string.
    """
    logging.info(f"Performing search with query: '{query_str}', DB path: '{db_path_str}', collection: '{collection_name_str}'")
    try:
        # For simplicity, use_ollama_parsing is False, and ollama_model/ollama_url use defaults from db_explorer
        # n_results is fixed at 10
        results = perform_search_logic(
            query=query_str,
            db_path=db_path_str,
            collection_name=collection_name_str,
            use_ollama_parsing=False, 
            # ollama_model and ollama_url will use defaults from perform_search_logic
            n_results=10 
        )
        logging.info(f"Search successful. Found {len(results.get('ids', [[]])[0])} results.")
        return json.dumps(results, indent=2, ensure_ascii=False)
    except ConnectionError as ce:
        error_msg = f"Error connecting to ChromaDB: {ce}"
        logging.error(error_msg)
        return json.dumps({"error": error_msg})
    except LookupError as le:
        error_msg = f"Error finding collection or data: {le}"
        logging.error(error_msg)
        return json.dumps({"error": error_msg})
    except Exception as e:
        error_msg = f"An unexpected error occurred: {e}"
        logging.error(error_msg, exc_info=True) # Log stack trace for general exceptions
        return json.dumps({"error": error_msg})

with gr.Blocks() as iface:
    gr.Markdown("## Vector Engine Search Interface")
    with gr.Row():
        query_input = gr.Textbox(label="Search Query", placeholder="Enter your search query here...")
    with gr.Row():
        db_path_input = gr.Textbox(label="ChromaDB Path", value="_data/chroma_db")
        collection_name_input = gr.Textbox(label="Collection Name", value="outlook_emails")
    with gr.Row():
        search_button = gr.Button("Search")
    with gr.Row():
        results_output = gr.Textbox(label="Results", lines=10, interactive=False, show_copy_button=True)

    # Link the search function to the Gradio interface
    search_button.click(
        fn=search_emails_gradio,
        inputs=[query_input, db_path_input, collection_name_input],
        outputs=results_output
    )

if __name__ == "__main__":
    # Configure basic logging (already configured at the top, but good practice to ensure it's set if run as script)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    parser = argparse.ArgumentParser(description="Launch the Vector Engine Gradio UI.")
    parser.add_argument("--db_path", type=str, default="_data/chroma_db", help="Path to the ChromaDB directory.")
    parser.add_argument("--collection_name", type=str, default="outlook_emails", help="Name of the ChromaDB collection.")
    parser.add_argument("--server_name", type=str, default="0.0.0.0", help="Gradio server name (e.g., '127.0.0.1' or '0.0.0.0').")
    parser.add_argument("--server_port", type=int, default=7860, help="Gradio server port.")
    parser.add_argument("--share", action="store_true", help="Enable Gradio sharing link.")
    
    args = parser.parse_args()

    # Update Gradio input components with values from command-line arguments
    # Assuming 'iface' and its components like 'db_path_input' and 'collection_name_input' are globally accessible
    # or accessible through the 'iface' object.
    # Gradio components are typically accessed via their variable names defined in the `with gr.Blocks() as iface:` context.
    # To update their initial values, we need to modify them before launch.
    # However, Gradio's `Textbox` value is set at instantiation. A direct update post-instantiation for the *default displayed value*
    # before `launch()` isn't the standard way. The `value` parameter in `gr.Textbox` sets the initial default.
    # The best practice here is to use these args when *defining* the interface, or if we must update post-definition,
    # it implies a more complex setup (e.g. iface as a class).
    # For this subtask, we will re-set the default values directly in the global scope for simplicity,
    # assuming the Gradio components `db_path_input` and `collection_name_input` are defined in the global scope.
    # This is a simplification; a more robust app might have these components as part of a class
    # or the launch script might re-create the interface with new defaults.

    # Let's try to update the components. If they are not directly updatable this way,
    # the alternative is that the launch script should pass these defaults into the interface creation function.
    # For now, we will assume they can be updated.
    # If `db_path_input` and `collection_name_input` are the actual component objects:
    db_path_input.value = args.db_path
    collection_name_input.value = args.collection_name
    
    logging.info(f"Launching Gradio app on {args.server_name}:{args.server_port}")
    if args.share:
        logging.info("Gradio share link will be enabled.")
        
    iface.launch(server_name=args.server_name, server_port=args.server_port, share=args.share)
