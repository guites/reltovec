# Prompts

First change was done using this prompt:

```plaintext
$openspec-propose Create an application that reads documents from a relational database, creates embeddings from these documents and saves them to a local vector database. I should be able to query
      embeddings based on the relational database identifier; I should be able to create multiple embeddings for each document using different embedding models. The embedding strategy should be done
  using
    the OpenAI batch processing API (https://developers.openai.com/api/docs/guides/batch). Use python 3.12. Assume the relational
      database is sqlite3. The vector database should be chromadb running in docker. Implementation should focus on simplicity (as in low complexity), maintainability and testability.
```

which generated the `sqlite-batch-embedding-pipeline` change.
