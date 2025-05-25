import json
import re
import os # Added
import sys # Added
import argparse # Added
import logging # Added

import chromadb
import pandas as pd
from sentence_transformers import SentenceTransformer

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def load_and_prepare_data(file_path: str) -> pd.DataFrame:
    """Loads JSONL, extracts data, and prepares text for embedding."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Error: JSONL file not found at '{file_path}'")

    emails_data = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                try:
                    email_json = json.loads(line)

                    subject = email_json.get('subject', '')
                    sender_name = email_json.get('sender_name', '')
                    email_type = email_json.get('type', '') # Often 'message'
                    folder_path = email_json.get('folder_path', '')
                    body = email_json.get('body', '') # Plain text body

                    # Basic cleaning for body text to be used in embedding
                    clean_text = ""
                    if body is not None:
                        clean_text = re.sub(r'\s+', ' ', body).strip() # Normalize whitespace

                    # Ensure essential fields for metadata are present, even if empty
                    document_email = {
                        'type': email_type or 'Unknown',
                        'subject': subject or '',
                        'sender_name': sender_name or '',
                        'folder_path': folder_path or '',
                        'body': body or '', # Store original body for metadata
                        'embedding_text': clean_text # Text specifically prepared for embedding
                    }
                    emails_data.append(document_email)
                except json.JSONDecodeError as e:
                    logging.warning(f"Skipping invalid JSON line {i+1} in '{file_path}': {line[:100]}... Error: {e}")
                except Exception as e:
                    logging.warning(f"Error processing line {i+1} in '{file_path}': {line[:100]}... Error: {e}")
    except FileNotFoundError: # Already handled above, but good practice in case of race conditions
        raise
    except Exception as e:
        raise Exception(f"Failed to read or process file '{file_path}': {e}")


    if not emails_data:
        # If no valid data was loaded, return an empty DataFrame with expected columns
        # This helps downstream functions handle empty dataframes gracefully.
        return pd.DataFrame(columns=['id', 'type', 'subject', 'sender_name', 'folder_path', 'body', 'embedding_text'])

    df = pd.DataFrame(emails_data)
    df['id'] = [f"email_{i}" for i in range(len(df))] # Generate unique IDs
    
    # Validate essential columns for embedding and storage
    if 'embedding_text' not in df.columns:
        # This case should ideally not happen if emails_data is populated correctly
        logging.error("Critical error: 'embedding_text' column is missing after data preparation.")
        raise ValueError("DataFrame missing 'embedding_text' column after preparation.")
        
    return df

def generate_embeddings(df: pd.DataFrame, model_name: str) -> pd.DataFrame:
    """Generates embeddings for the 'embedding_text' column in the DataFrame."""
    if df.empty:
        logging.warning("Input DataFrame is empty. No embeddings to generate.")
        # Return DataFrame with an empty 'embedding' column if it's missing
        if 'embedding' not in df.columns:
             df['embedding'] = pd.Series(dtype='object')
        return df
    
    if 'embedding_text' not in df.columns:
        raise ValueError("DataFrame must contain an 'embedding_text' column.")

    try:
        logging.info(f"Loading embedding model: {model_name}")
        model = SentenceTransformer(model_name)

        logging.info(f"Generating embeddings for {len(df)} emails...")
        # Ensure 'embedding_text' is a list of strings, handle potential NaN/None values
        texts_to_embed = df['embedding_text'].fillna('').tolist()
        embeddings = model.encode(texts_to_embed, show_progress_bar=True)
        df['embedding'] = list(embeddings)
        logging.info("Embedding generation complete.")
    except Exception as e:
        logging.error(f"Error during embedding generation with model '{model_name}': {e}", exc_info=True)
        raise Exception(f"Failed to generate embeddings: {e}")
    return df

def store_in_chromadb(df: pd.DataFrame, db_path: str, collection_name: str):
    """Initializes ChromaDB and stores embeddings and metadata."""
    if df.empty:
        logging.warning("Input DataFrame is empty. Nothing to store in ChromaDB.")
        return None # Or raise ValueError("Cannot store empty DataFrame") depending on desired strictness
    
    if 'id' not in df.columns or 'embedding' not in df.columns:
        raise ValueError("DataFrame must contain 'id' and 'embedding' columns for ChromaDB storage.")

    try:
        logging.info(f"Initializing ChromaDB client at: {db_path}")
        client = chromadb.PersistentClient(path=db_path)

        logging.info(f"Getting or creating collection: {collection_name}")
        collection = client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"} # Using cosine similarity
        )

        logging.info(f"Preparing {len(df)} documents for ChromaDB...")

        ids = df['id'].tolist()
        embeddings = df['embedding'].tolist() # Assumes this is already a list of lists/arrays

        # Prepare metadata: exclude 'embedding' and 'embedding_text'. Include other relevant fields.
        # Original code used: ['type', 'subject', 'sender_name', 'folder_path', 'body']
        # Ensure these columns exist, or handle missing ones gracefully.
        metadata_cols = [col for col in ['type', 'subject', 'sender_name', 'folder_path', 'body'] if col in df.columns]
        if not metadata_cols:
            logging.warning("No standard metadata columns found in DataFrame. Using empty metadata.")
            metadatas = [{} for _ in range(len(df))]
        else:
            metadatas = df[metadata_cols].to_dict('records')

        # Add data in batches
        batch_size = 100 # As in original
        for i in range(0, len(ids), batch_size):
            try:
                batch_ids = ids[i:i + batch_size]
                batch_embeddings = embeddings[i:i + batch_size]
                batch_metadatas = metadatas[i:i + batch_size]

                # Clean metadata for ChromaDB (must be JSON serializable, handle NaNs)
                cleaned_metadatas_batch = []
                for meta_record in batch_metadatas:
                    cleaned_record = {}
                    for k, v in meta_record.items():
                        if pd.isna(v):
                            cleaned_record[k] = None # Or an empty string, depending on preference
                        elif isinstance(v, (dict, list)): # ChromaDB might handle nested structures
                            cleaned_record[k] = v 
                        else:
                            cleaned_record[k] = str(v) # Ensure all values are basic types
                    cleaned_metadatas_batch.append(cleaned_record)

                collection.add(
                    embeddings=batch_embeddings,
                    metadatas=cleaned_metadatas_batch,
                    ids=batch_ids
                )
                logging.info(f"Added batch {int(i/batch_size) + 1} of {int(len(ids)/batch_size) +1} to collection '{collection_name}'.")
            except Exception as e:
                logging.error(f"Error adding batch {int(i/batch_size) + 1} to ChromaDB: {e}", exc_info=True)
                # Decide if to continue or raise. For now, log and continue.
                # raise Exception(f"Failed to add batch to ChromaDB: {e}")
        
        logging.info("Data storage in ChromaDB complete.")
        return collection
    except Exception as e:
        logging.error(f"Error during ChromaDB operations: {e}", exc_info=True)
        raise Exception(f"Failed to store data in ChromaDB: {e}")

def main_load_process(jsonl_file_path: str, chroma_db_path: str, collection_name: str, embedding_model_name: str) -> bool:
    """
    Main process to load data from JSONL, generate embeddings, and store in ChromaDB.
    Returns True on success. Raises exceptions on failure.
    """
    logging.info(f"Starting data loading and embedding process...")
    logging.info(f"  JSONL file: {jsonl_file_path}")
    logging.info(f"  ChromaDB path: {chroma_db_path}")
    logging.info(f"  Collection name: {collection_name}")
    logging.info(f"  Embedding model: {embedding_model_name}")

    # 1 & 2: Load and Prepare Data
    emails_df = load_and_prepare_data(jsonl_file_path)
    logging.info(f"Loaded and prepared {len(emails_df)} emails.")
    
    if emails_df.empty and not os.path.exists(jsonl_file_path): # Check if file existed but was empty vs file not found
         logging.warning(f"JSONL file at '{jsonl_file_path}' was not found or is empty. No data to process.")
         return False # Or raise specific error
    elif emails_df.empty:
         logging.warning(f"No valid data loaded from '{jsonl_file_path}'. Ensure file contains valid JSONL content.")
         return False # Or raise

    # 3 & 4: Generate Embeddings
    emails_df_with_embeddings = generate_embeddings(emails_df, embedding_model_name)
    if 'embedding' not in emails_df_with_embeddings.columns or emails_df_with_embeddings['embedding'].isnull().all():
        logging.error("Embeddings were not generated successfully.")
        # No need to proceed to storage if embeddings failed and df is empty or embeddings are all null
        if emails_df_with_embeddings.empty:
             raise ValueError("Embedding generation resulted in an empty DataFrame.")
        # If embeddings are null but df is not empty, it means model.encode failed or returned unexpected.
        # generate_embeddings should ideally raise an error in such cases.

    # 5 & 6: Store in ChromaDB
    store_in_chromadb(emails_df_with_embeddings, chroma_db_path, collection_name)
    
    logging.info("Process complete. Email data vectorized and stored in ChromaDB.")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load email data from JSONL, generate embeddings, and store in ChromaDB.")
    parser.add_argument("--jsonl_file", help="Path to the input JSONL file (e.g., _data/aviel_emails.jsonl).")
    parser.add_argument("--chroma_db_path", default="./_data/chroma_db", help="Path to the ChromaDB storage directory (e.g., _data/chroma_db).")
    parser.add_argument("--collection_name", default="outlook_emails", help="Name of the collection in ChromaDB (default: outlook_emails).")
    parser.add_argument("--embedding_model", default="paraphrase-multilingual-MiniLM-L12-v2", help="Name of the sentence-transformer model (default: paraphrase-multilingual-MiniLM-L12-v2).")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose (DEBUG level) logging output.")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        for handler in logging.getLogger().handlers:
            handler.setLevel(logging.DEBUG)
        logging.debug("Verbose logging enabled.")

    try:
        if main_load_process(args.jsonl_file, args.chroma_db_path, args.collection_name, args.embedding_model):
            print(f"Successfully loaded, embedded, and stored data from '{args.jsonl_file}' to ChromaDB collection '{args.collection_name}'.")
        else:
            # This 'else' case might be less common if main_load_process raises exceptions for most failures.
            # It could be reached if, for example, the JSONL file is empty but valid.
            print(f"Data loading and embedding process completed, but may not have processed any data (e.g., empty input file). Check logs for details.")
            # sys.exit(0) or sys.exit(1) depending on if "empty but successful" is a failure.
            # For now, assume if it returns False, it's a situation that warrants a non-zero exit.
            sys.exit(1) 
            
    except FileNotFoundError as fnf_error:
        logging.error(f"File not found: {fnf_error}")
        print(f"Error: {fnf_error}", file=sys.stderr)
        sys.exit(1)
    except ValueError as val_error: # Catch specific ValueErrors from functions
        logging.error(f"Validation error: {val_error}")
        print(f"Error: {val_error}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        logging.error(f"An critical error occurred during data loading: {e}", exc_info=True)
        print(f"An error occurred: {e}", file=sys.stderr)
        sys.exit(1)