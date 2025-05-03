import json
import re

import chromadb
import pandas as pd
from sentence_transformers import SentenceTransformer

# --- Configuration ---
JSONL_FILE_PATH = './_data/aviel_emails.jsonl'
EMBEDDING_MODEL_NAME = 'paraphrase-multilingual-MiniLM-L12-v2' # Recommended multilingual model
CHROMA_DB_PATH = './_data/chroma_db'
COLLECTION_NAME = 'outlook_emails'

# --- Step 1 & 2: Load Data and Prepare Text ---
def load_and_prepare_data(file_path):
    """Loads JSONL, extracts data, and prepares text for embedding based on the provided sample."""
    emails_data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                email_json = json.loads(line)

                # Extract available fields based on your JSON structure
                subject = email_json.get('subject', '')
                sender_name = email_json.get('sender_name', '')
                email_type = email_json.get('type', '')
                folder_path = email_json.get('folder_path', '')
                # We will ignore 'extraction_error' for embedding/metadata
                body = email_json.get('body', '')

                clean_text = ""
                if body is not None:
                    # Basic cleaning (mainly for subject/sender name now)
                    clean_text = re.sub('\s+', ' ', body).strip() # Normalize whitespace

                document_email = {
                    # id will be added after creating DataFrame
                    'type': email_type,
                    'subject': subject,
                    'sender_name': sender_name,
                    'folder_path': folder_path,
                    'body': body,
                    'embedding_text': clean_text # Text used for embedding
                }

                emails_data.append(document_email)
            except json.JSONDecodeError as e:
                print(f"Skipping invalid JSON line: {line[:100]}... Error: {e}")
            except Exception as e:
                 # Handle potential errors during processing
                 print(f"Error processing line: {line[:100]}... Error: {e}")


    # Convert to DataFrame for easier handling
    df = pd.DataFrame(emails_data)
    # Generate a simple index-based ID
    df['id'] = [f"email_{i}" for i in range(len(df))]
    return df

# --- Step 3 & 4: Load Model and Generate Embeddings ---
def generate_embeddings(df, model_name):
    """Generates embeddings for the prepared text."""
    print(f"Loading embedding model: {model_name}")
    model = SentenceTransformer(model_name)

    print(f"Generating embeddings for {len(df)} emails...")
    # Embed in batches if you have a very large number of emails
    embeddings = model.encode(df['embedding_text'].tolist(), show_progress_bar=True)
    df['embedding'] = list(embeddings)
    print("Embedding generation complete.")
    return df

# --- Step 5 & 6: Set up ChromaDB and Store Data ---
def store_in_chromadb(df, db_path, collection_name):
    """Initializes ChromaDB and stores embeddings and metadata based on adapted structure."""
    print(f"Initializing ChromaDB client at: {db_path}")
    client = chromadb.PersistentClient(path=db_path)

    print(f"Getting or creating collection: {collection_name}")
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"}
    )

    print(f"Adding {len(df)} documents to ChromaDB...")

    ids = df['id'].tolist()
    embeddings = df['embedding'].tolist()

    # Prepare metadata - exclude 'embedding', 'embedding_text', and 'extraction_error'
    # Include 'type', 'subject', 'sender_name', 'folder_path'
    metadata_cols = ['type', 'subject', 'sender_name', 'folder_path', 'body']
    metadatas = df[metadata_cols].to_dict('records') # Convert DataFrame rows to list of dicts

    # Add data in batches
    batch_size = 100
    for i in range(0, len(ids), batch_size):
        try:
            batch_ids = ids[i:i + batch_size]
            batch_embeddings = embeddings[i:i + batch_size]
            batch_metadatas = metadatas[i:i + batch_size]

            # Ensure metadata values are serializable (ChromaDB requires JSON serializable)
            cleaned_metadatas = []
            for meta in batch_metadatas:
                cleaned_meta = {}
                for k, v in meta.items():
                    # Basic handling for None/NaN values if they appear
                    if pd.isna(v):
                         cleaned_meta[k] = None
                    else:
                        cleaned_meta[k] = v
                cleaned_metadatas.append(cleaned_meta)


            collection.add(
                embeddings=batch_embeddings,
                metadatas=cleaned_metadatas,
                ids=batch_ids
            )
            print(f"Added batch {int(i/batch_size) + 1}...")
        except Exception as e:
            print(f"Error adding batch {int(i/batch_size) + 1}: {e}")
            continue

    print("Data storage in ChromaDB complete.")
    return collection

# --- Main Execution ---
if __name__ == "__main__":
    # 1 & 2: Load and Prepare Data
    emails_df = load_and_prepare_data(JSONL_FILE_PATH)
    print(f"Loaded and prepared {len(emails_df)} emails.")
    print(emails_df.head()) # Show the first few rows

    if not emails_df.empty:
        # 3 & 4: Generate Embeddings
        emails_df_with_embeddings = generate_embeddings(emails_df, EMBEDDING_MODEL_NAME)

        # 5 & 6: Store in ChromaDB
        email_collection = store_in_chromadb(emails_df_with_embeddings, CHROMA_DB_PATH, COLLECTION_NAME)

        print("\nProcess complete. Your email data is now vectorized and stored in ChromaDB.")
        print(f"You can now use the '{COLLECTION_NAME}' collection in '{CHROMA_DB_PATH}' for similarity search.")

    else:
        print("No data loaded from the JSONL file.")