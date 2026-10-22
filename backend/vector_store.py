from functools import lru_cache

import chromadb
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from backend.config import settings

EMBEDDING_DIMENSIONS = 768


@lru_cache(maxsize=1)
def get_collection() -> Chroma:
    api_key = settings.gemini_api_key
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY or GOOGLE_API_KEY is required for document embeddings."
        )

    settings.data_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(settings.data_dir))
    embeddings = GoogleGenerativeAIEmbeddings(
        model=settings.embedding_model,
        google_api_key=api_key,
        output_dimensionality=EMBEDDING_DIMENSIONS,
    )
    return Chroma(
        client=client,
        collection_name=settings.collection_name,
        embedding_function=embeddings,
        collection_metadata={"hnsw:space": "cosine"},
    )


def upsert_chunks(document_name: str, chunks: list[str]) -> int:
    collection = get_collection()
    where = {"document_name": document_name}
    old = collection.get(where=where, include=[])
    if old["ids"]:
        collection.delete(ids=old["ids"])
    ids = [f"{document_name}::{i}" for i in range(len(chunks))]
    metadatas = [
        {"document_name": document_name, "chunk_index": i}
        for i in range(len(chunks))
    ]
    collection.add_texts(texts=chunks, metadatas=metadatas, ids=ids)
    return len(chunks)


def retrieve(
    question: str,
    top_k: int = 3,
    document_name: str | None = None,
) -> list[dict]:
    collection = get_collection()
    where = {"document_name": document_name} if document_name else None
    existing = collection.get(where=where, include=[]) if where else collection.get(include=[])
    count = len(existing["ids"])
    if count == 0 or top_k <= 0:
        return []

    search_options = {"k": min(top_k, count)}
    if where:
        search_options["filter"] = where
    matches = collection.similarity_search_with_score(question, **search_options)
    return [
        {
            "text": document.page_content,
            "metadata": document.metadata,
            "distance": float(distance),
        }
        for document, distance in matches
    ]


def list_documents() -> list[dict]:
    collection = get_collection()
    result = collection.get(include=["metadatas"])
    docs = {}
    for metadata in result["metadatas"]:
        name = metadata["document_name"]
        docs[name] = docs.get(name, 0) + 1
    return [
        {"document_name": name, "chunk_count": count}
        for name, count in sorted(docs.items())
    ]


def delete_document(document_name: str) -> bool:
    collection = get_collection()
    old = collection.get(where={"document_name": document_name}, include=[])
    if not old["ids"]:
        return False
    collection.delete(ids=old["ids"])
    return True
