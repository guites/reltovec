import chromadb

client = chromadb.HttpClient(host="localhost", port=8000)

collections = client.list_collections()
for collection in collections:
    print("name", collection.name)
    print("metadata", collection.metadata)
    print("num documents", collection.count())
