# Prompts

devlog recording openspec usage, experience and pointers.

## project baseline

First change was done using this prompt:

```plaintext
$openspec-propose Create an application that reads documents from a relational database, creates embeddings from these documents and saves them to a local vector database. I should be able to query
      embeddings based on the relational database identifier; I should be able to create multiple embeddings for each document using different embedding models. The embedding strategy should be done
  using
    the OpenAI batch processing API (https://developers.openai.com/api/docs/guides/batch). Use python 3.12. Assume the relational
      database is sqlite3. The vector database should be chromadb running in docker. Implementation should focus on simplicity (as in low complexity), maintainability and testability.
```

which generated the `sqlite-batch-embedding-pipeline` change.

Pointers: I didn't specify project defaults such as `git` and `uv`, linting, etc. The model
defaulted to `uv` and I then manually added ruff as a dev dependency.

## incrementally index documents

My goal is to run the `index` command on a subset of data, mainly for testing with limited expenses,
but also to confidently run `index` again on unexpected errors.

```plaintext
$openspec-propose The "index" cli command should work incrementally. Implement a validation to prevent multiple calls to "index" from batching documents that were already indexed, regardless of their
  batch current status. The index command should also accept an argument that specifies how many documents should be indexed in that specific call, which is not the same as the max_batch_size. This means
  that the user should be able to call index multiple times, for example `index --limit 5000`, and each time a new selection of 5000 documents should be indexed
```

which generated the `incremental-index-command` change.

Pointers: I used "documents" when I actually meant "document/model combinations",
but the model picked up on that and proposed keying on `custom_id` which is in
the format `f"doc:{encoded_document_id}|model:{encoded_model}"`.

## chromadb embedding insertion

I need to further understand how and when documents from processed batches
are inserted into the chromadb collection.

## status command should update current batch status

Currently it seems that the command only queries the database. In order to update
existing status we need to call a new `index` command.

## query registered embeddings

Expose a cli command to allow querying collections
by embedding the query text via OpenAPI sync embedding endpoint and
passing the query over to chromadb. see
<https://docs.trychroma.com/docs/querying-collections/query-and-get>.

## logging

I need thorough logging of command execution steps in order to better
understand the application logic and state changes.
