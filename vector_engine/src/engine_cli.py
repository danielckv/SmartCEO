import argparse
import sys
import json
import logging
import os

# Add the script's directory to Python's path to find sibling modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    import pst_processor
    import data_loader
    import db_explorer
except ImportError as e:
    # This initial check helps diagnose import issues early, especially when running with PyInstaller
    logging.basicConfig(level=logging.CRITICAL, stream=sys.stderr) # Basic config for this specific error
    logging.critical(f"Failed to import core modules. Ensure they are in the same directory or PYTHONPATH is set correctly. Error: {e}")
    sys.exit(10) # Specific exit code for import failure

# Setup basic logging to stderr
# Configure to not interfere with stdout for command results (e.g., JSON output from search)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s', stream=sys.stderr)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Vector Engine CLI for email processing and search.", prog="engine_cli")
    # Adding a general verbose flag
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose (DEBUG level) logging output to stderr.")

    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    # --- process-pst command ---
    process_parser = subparsers.add_parser("process-pst", help="Process a PST file and convert it to JSONL.")
    process_parser.add_argument("--pst_path", required=True, help="Path to the input PST file.")
    process_parser.add_argument("--jsonl_path", required=True, help="Path to the output JSONL file.")

    # --- load-data command ---
    load_parser = subparsers.add_parser("load-data", help="Load data from JSONL, generate embeddings, and store in ChromaDB.")
    load_parser.add_argument("--jsonl_path", required=True, help="Path to the input JSONL file.")
    load_parser.add_argument("--db_path", required=True, help="Path to the ChromaDB storage directory.")
    load_parser.add_argument("--collection_name", default="outlook_emails", help="Name of the collection in ChromaDB (default: outlook_emails).")
    load_parser.add_argument("--model_name", default="paraphrase-multilingual-MiniLM-L12-v2", help="Sentence transformer model name (default: paraphrase-multilingual-MiniLM-L12-v2).")

    # --- search command ---
    search_parser = subparsers.add_parser("search", help="Search emails in the ChromaDB.")
    search_parser.add_argument("--query", required=True, help="Search query string.")
    search_parser.add_argument("--db_path", required=True, help="Path to the ChromaDB storage directory.")
    search_parser.add_argument("--collection_name", default="outlook_emails", help="ChromaDB collection name (default: outlook_emails).")
    search_parser.add_argument("--n_results", type=int, default=10, help="Number of search results to return (default: 10).")
    search_parser.add_argument("--no_ollama", action="store_true", help="Disable Ollama for query parsing.")
    search_parser.add_argument("--ollama_model", default="llama3.1:latest", help="Ollama model name (default: llama3.1:latest).")
    search_parser.add_argument("--ollama_url", default="http://localhost:11434/api/generate", help="Ollama API URL (default: http://localhost:11434/api/generate).")

    args = parser.parse_args()

    # Adjust logging level if verbose flag is set
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG) # Set root logger level
        for handler in logging.getLogger().handlers: # Ensure all handlers are updated
            handler.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled.")


    try:
        if args.command == "process-pst":
            logger.info(f"Processing PST file: '{args.pst_path}' to '{args.jsonl_path}'")
            if pst_processor.pst_to_jsonl(args.pst_path, args.jsonl_path):
                # pst_to_jsonl now logs its own success, this is for CLI stdout confirmation
                print(f"Successfully processed '{args.pst_path}' to '{args.jsonl_path}'", file=sys.stdout)
                sys.exit(0)
            else:
                # This case should ideally not be reached if pst_to_jsonl always raises an exception on failure.
                # However, keeping it as a fallback.
                logger.error(f"PST processing from '{args.pst_path}' to '{args.jsonl_path}' failed with no specific exception.")
                print(f"Error: PST processing failed for '{args.pst_path}'. Check logs for details.", file=sys.stderr)
                sys.exit(1)

        elif args.command == "load-data":
            logger.info(f"Loading data from '{args.jsonl_path}' into ChromaDB at '{args.db_path}' (collection: '{args.collection_name}', model: '{args.model_name}')")
            if data_loader.main_load_process(args.jsonl_path, args.db_path, args.collection_name, args.model_name):
                print(f"Successfully loaded data from '{args.jsonl_path}' into ChromaDB collection '{args.collection_name}'.", file=sys.stdout)
                sys.exit(0)
            else:
                # Similar to process-pst, main_load_process should raise on failure.
                logger.error(f"Data loading from '{args.jsonl_path}' failed with no specific exception.")
                print(f"Error: Data loading failed for '{args.jsonl_path}'. Check logs for details.", file=sys.stderr)
                sys.exit(1)

        elif args.command == "search":
            logger.info(f"Searching in ChromaDB ('{args.db_path}', collection: '{args.collection_name}') with query: '{args.query}'")
            results = db_explorer.perform_search_logic(
                query=args.query,
                db_path=args.db_path,
                collection_name=args.collection_name,
                use_ollama_parsing=not args.no_ollama,
                ollama_model=args.ollama_model,
                ollama_url=args.ollama_url,
                n_results=args.n_results
            )
            # Output JSON to stdout - this is the success confirmation for search
            print(json.dumps(results, indent=2, ensure_ascii=False), file=sys.stdout)
            sys.exit(0)

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        print(f"Error: File not found - {e}", file=sys.stderr)
        sys.exit(2) # Specific exit code for file not found
    except ConnectionError as e: # For Ollama or DB connection issues
        logger.error(f"Connection error: {e}")
        print(f"Error: Connection issue - {e}", file=sys.stderr)
        sys.exit(3) # Specific exit code for connection errors
    except LookupError as e: # For errors like collection not found
        logger.error(f"Lookup error: {e}")
        print(f"Error: Lookup failed - {e}", file=sys.stderr)
        sys.exit(4) # Specific exit code for lookup errors
    except ValueError as e: # For value errors from functions (e.g. empty dataframe)
        logger.error(f"Value error: {e}")
        print(f"Error: Invalid value or input - {e}", file=sys.stderr)
        sys.exit(5) # Specific exit code for value errors
    except Exception as e:
        # Log the full traceback for unexpected errors
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        print(f"An unexpected error occurred: {e}. Check logs for detailed traceback.", file=sys.stderr)
        sys.exit(1) # General error exit code

if __name__ == "__main__":
    # This initial sys.path.append is crucial, especially if this script
    # is run directly and the vector_engine package isn't installed in a way
    # that makes its modules automatically discoverable.
    # For PyInstaller, this helps it find modules when it analyzes imports,
    # but hooks and --paths might still be needed for complex cases.
    if __package__ is None and not hasattr(sys, 'frozen'):
        # direct execution: add parent
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if parent_dir not in sys.path:
             sys.path.insert(0, parent_dir)
        # Try to make it act like a module for relative imports if possible
        # This is more for development; PyInstaller handles packaging differently.
        # current_dir = os.path.dirname(os.path.abspath(__file__))
        # if current_dir not in sys.path:
        #    sys.path.insert(0, current_dir)


    # Re-import with potentially updated path (less critical here as imports are at top)
    # but good practice if modules were in subdirectories relative to this script.
    # No, this is not needed as imports are already successful or failed by now.

    main()
