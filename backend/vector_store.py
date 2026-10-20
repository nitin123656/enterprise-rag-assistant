from functools import lru_cache
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from backend.config import settings

@lru_cache(maxsize=1)
def get_collection():
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(settings.data_dir))
    embedding_fn = SentenceTransformerEmbeddingFunction(model_name=settings.embedding_model)
    return client.get_or_create_collection(
        name=settings.collection_name,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )

def upsert_chunks(document_name: str, chunks: list[str]) -> int:
    collection = get_collection()
    # Re-uploading a document replaces its prior chunks, preventing stale duplicates.
    old = collection.get(where={"document_name": document_name}, include=[])
    if old["ids"]:
        collection.delete(ids=old["ids"])
    ids = [f"{document_name}::{i}" for i in range(len(chunks))]
    metadatas = [{"document_name": document_name, "chunk_index": i} for i in range(len(chunks))]
    collection.add(ids=ids, documents=chunks, metadatas=metadatas)
    return len(chunks)

def retrieve(question: str, top_k: int = 3, document_name: str | None = None) -> list[dict]:
    collection = get_collection()
    if collection.count() == 0:
        return []
    kwargs = {"query_texts": [question], "n_results": min(top_k, collection.count()),
              "include": ["documents", "metadatas", "distances"]}
    if document_name:
        kwargs["where"] = {"document_name": document_name}
    result = collection.query(**kwargs)
    rows = []
    for doc, meta, distance in zip(
        result["documents"][0], result["metadatas"][0], result["distances"][0]
    ):
        rows.append({"text": doc, "metadata": meta, "distance": float(distance)})
    return rows

def list_documents() -> list[dict]:
    collection = get_collection()
    result = collection.get(include=["metadatas"])
    docs = {}
    for meta in result["metadatas"]:
        name = meta["document_name"]
        docs[name] = docs.get(name, 0) + 1
    return [{"document_name": name, "chunk_count": count} for name, count in sorted(docs.items())]

def delete_document(document_name: str) -> bool:
    collection = get_collection()
    old = collection.get(where={"document_name": document_name}, include=[])
    if not old["ids"]:
        return False
    collection.delete(ids=old["ids"])
    return True
