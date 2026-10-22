from types import SimpleNamespace

import pytest
from langchain_core.embeddings import Embeddings

from backend import vector_store


class FakeCollection:
    def __init__(self):
        self.get_calls = []
        self.delete_calls = []
        self.add_calls = []
        self.search_calls = []

    def get(self, **kwargs):
        self.get_calls.append(kwargs)
        if kwargs.get("include") == ["metadatas"]:
            return {
                "metadatas": [
                    {"document_name": "facts.txt", "chunk_index": 0},
                    {"document_name": "facts.txt", "chunk_index": 1},
                ]
            }
        if kwargs.get("where", {}).get("document_name") == "missing.txt":
            return {"ids": []}
        return {"ids": ["facts.txt::0", "facts.txt::1"]}

    def delete(self, **kwargs):
        self.delete_calls.append(kwargs)

    def add_texts(self, **kwargs):
        self.add_calls.append(kwargs)

    def similarity_search_with_score(self, query, **kwargs):
        self.search_calls.append((query, kwargs))
        return [
            (
                SimpleNamespace(
                    page_content="The company is based in Bengaluru.",
                    metadata={"document_name": "facts.txt", "chunk_index": 0},
                ),
                0.2,
            )
        ]


def test_collection_uses_gemini_embedding_and_versioned_collection(monkeypatch, tmp_path):
    vector_store.get_collection.cache_clear()
    monkeypatch.setattr(vector_store.settings, "gemini_api_key", "test-api-key")
    monkeypatch.setattr(vector_store.settings, "data_dir", tmp_path)
    monkeypatch.setattr(vector_store.settings, "collection_name", "enterprise_kb_v2")
    monkeypatch.setattr(vector_store.settings, "embedding_model", "gemini-embedding-001")

    client = object()
    monkeypatch.setattr(
        vector_store.chromadb,
        "PersistentClient",
        lambda path: client,
    )
    embedding_options = {}

    def create_embeddings(**kwargs):
        embedding_options.update(kwargs)
        return object()

    monkeypatch.setattr(
        vector_store,
        "GoogleGenerativeAIEmbeddings",
        create_embeddings,
    )
    collection_options = {}

    def create_collection(**kwargs):
        collection_options.update(kwargs)
        return object()

    monkeypatch.setattr(vector_store, "Chroma", create_collection)

    try:
        vector_store.get_collection()
    finally:
        vector_store.get_collection.cache_clear()

    assert embedding_options == {
        "model": "gemini-embedding-001",
        "google_api_key": "test-api-key",
        "output_dimensionality": 768,
    }
    assert collection_options["client"] is client
    assert collection_options["collection_name"] == "enterprise_kb_v2"
    assert collection_options["collection_metadata"] == {"hnsw:space": "cosine"}


def test_collection_requires_google_api_key(monkeypatch):
    vector_store.get_collection.cache_clear()
    monkeypatch.setattr(vector_store.settings, "gemini_api_key", "")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY or GOOGLE_API_KEY"):
        vector_store.get_collection()


def test_chroma_adapter_indexes_and_retrieves_with_768_dimensional_embeddings(
    monkeypatch,
    tmp_path,
):
    class TestEmbeddings(Embeddings):
        def embed_documents(self, texts):
            return [[1.0] + [0.0] * 767 for _ in texts]

        def embed_query(self, text):
            return [1.0] + [0.0] * 767

    vector_store.get_collection.cache_clear()
    monkeypatch.setattr(vector_store.settings, "gemini_api_key", "test-api-key")
    monkeypatch.setattr(vector_store.settings, "data_dir", tmp_path)
    monkeypatch.setattr(vector_store.settings, "collection_name", "test_enterprise_kb_v2")
    monkeypatch.setattr(
        vector_store,
        "GoogleGenerativeAIEmbeddings",
        lambda **kwargs: TestEmbeddings(),
    )

    try:
        count = vector_store.upsert_chunks(
            "facts.txt",
            ["The company is based in Bengaluru."],
        )
        matches = vector_store.retrieve(
            "Where is the company based?",
            document_name="facts.txt",
        )
    finally:
        vector_store.get_collection.cache_clear()

    assert count == 1
    assert len(matches) == 1
    assert matches[0]["text"] == "The company is based in Bengaluru."
    assert matches[0]["metadata"] == {"document_name": "facts.txt", "chunk_index": 0}
    assert isinstance(matches[0]["distance"], float)


def test_upsert_replaces_document_chunks(monkeypatch):
    collection = FakeCollection()
    monkeypatch.setattr(vector_store, "get_collection", lambda: collection)

    count = vector_store.upsert_chunks("facts.txt", ["first", "second"])

    assert count == 2
    assert collection.get_calls == [
        {"where": {"document_name": "facts.txt"}, "include": []}
    ]
    assert collection.delete_calls == [{"ids": ["facts.txt::0", "facts.txt::1"]}]
    assert collection.add_calls[0]["ids"] == ["facts.txt::0", "facts.txt::1"]
    assert collection.add_calls[0]["metadatas"] == [
        {"document_name": "facts.txt", "chunk_index": 0},
        {"document_name": "facts.txt", "chunk_index": 1},
    ]


def test_retrieve_returns_scores_and_filters_document(monkeypatch):
    collection = FakeCollection()
    monkeypatch.setattr(vector_store, "get_collection", lambda: collection)

    matches = vector_store.retrieve("Where is the company?", document_name="facts.txt")

    assert matches == [
        {
            "text": "The company is based in Bengaluru.",
            "metadata": {"document_name": "facts.txt", "chunk_index": 0},
            "distance": 0.2,
        }
    ]
    assert collection.search_calls == [
        ("Where is the company?", {"k": 2, "filter": {"document_name": "facts.txt"}})
    ]


def test_list_and_delete_documents(monkeypatch):
    collection = FakeCollection()
    monkeypatch.setattr(vector_store, "get_collection", lambda: collection)

    assert vector_store.list_documents() == [
        {"document_name": "facts.txt", "chunk_count": 2}
    ]
    assert vector_store.delete_document("facts.txt") is True
    assert vector_store.delete_document("missing.txt") is False
    assert collection.delete_calls == [
        {"ids": ["facts.txt::0", "facts.txt::1"]},
    ]
