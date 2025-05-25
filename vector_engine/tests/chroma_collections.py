import chromadb

client = chromadb.PersistentClient(path="./_data/chroma_db")

collections = client.list_collections()
print(collections)

for collection in collections:
    print(collection.name)