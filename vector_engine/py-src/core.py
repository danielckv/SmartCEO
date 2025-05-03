import json

from hyperdb import HyperDB

# Load documents from the JSONL file
documents = []

with open("demo/pokemon.jsonl", "r") as f:
    for line in f:
        documents.append(json.loads(line))

# Instantiate HyperDB with the list of documents
db = HyperDB(documents, key="info.description")

# Save the HyperDB instance to a file
db.save("demo/email.pickle.gz")

# Load the HyperDB instance from the save file
db.load("demo/email.pickle.gz")

# Query the HyperDB instance with a text input
results = db.query("Likes to sleep.", top_k=5)