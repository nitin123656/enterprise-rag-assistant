from types import SimpleNamespace

from backend import rag_pipeline
from backend.prompts import FALLBACK_ANSWER
from google.genai.errors import ServerError


def _match(document_name: str, chunk_index: int, distance: float, text: str) -> dict:
    return {
        "metadata": {
            "document_name": document_name,
            "chunk_index": chunk_index,
        },
        "distance": distance,
        "text": text,
    }


def test_relevant_match_within_configured_distance_reaches_model(monkeypatch):
    facts = "Main product: Enterprise document automation software"
    irrelevant = "Synopsis about a different project"
    monkeypatch.setattr(rag_pipeline.settings, "max_cosine_distance", 0.85)
    monkeypatch.setattr(rag_pipeline.settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(
        rag_pipeline,
        "retrieve",
        lambda *args, **kwargs: [
            _match("company_facts.txt", 0, 0.8005, facts),
            _match("final_synopsis.pdf", 2, 0.8529, irrelevant),
        ],
    )
    generate_content = SimpleNamespace(
        text="The main product is enterprise document automation software."
    )
    generate_call = SimpleNamespace(
        generate_content=lambda **kwargs: generate_content
    )
    monkeypatch.setattr(
        rag_pipeline.genai,
        "Client",
        lambda **kwargs: SimpleNamespace(models=generate_call),
    )

    result = rag_pipeline.answer_question("What is the main product?")

    assert result["grounded"] is True
    assert [source["document_name"] for source in result["sources"]] == [
        "company_facts.txt"
    ]


def test_no_match_within_distance_returns_fallback_without_model_call(monkeypatch):
    monkeypatch.setattr(rag_pipeline.settings, "max_cosine_distance", 0.85)
    monkeypatch.setattr(
        rag_pipeline,
        "retrieve",
        lambda *args, **kwargs: [
            _match("final_synopsis.pdf", 0, 0.93, "Unrelated document content")
        ],
    )
    monkeypatch.setattr(
        rag_pipeline.genai,
        "Client",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("model should not run")),
    )

    result = rag_pipeline.answer_question("Where is NovaTech headquartered?")

    assert result == {"answer": FALLBACK_ANSWER, "sources": [], "grounded": False}


def test_model_fallback_is_returned_without_source_citations(monkeypatch):
    monkeypatch.setattr(rag_pipeline.settings, "max_cosine_distance", 0.85)
    monkeypatch.setattr(rag_pipeline.settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(
        rag_pipeline,
        "retrieve",
        lambda *args, **kwargs: [
            _match(
                "company_facts.txt",
                0,
                0.4544,
                "Company: NovaTech Solutions\nHeadquarters: Bengaluru, India",
            )
        ],
    )
    monkeypatch.setattr(
        rag_pipeline,
        "genai",
        SimpleNamespace(
            Client=lambda **kwargs: SimpleNamespace(
                models=SimpleNamespace(
                    generate_content=lambda **kwargs: SimpleNamespace(text=FALLBACK_ANSWER)
                )
            )
        ),
    )

    result = rag_pipeline.answer_question(
        "Who is the Chief Financial Officer (CFO) of NovaTech Solutions?"
    )

    assert result == {"answer": FALLBACK_ANSWER, "sources": [], "grounded": False}


def test_transient_gemini_error_retries_and_returns_answer(monkeypatch):
    monkeypatch.setattr(rag_pipeline.settings, "max_cosine_distance", 0.85)
    monkeypatch.setattr(rag_pipeline.settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(
        rag_pipeline,
        "retrieve",
        lambda *args, **kwargs: [
            _match("company_facts.txt", 0, 0.2, "Headquarters: Bengaluru, India")
        ],
    )
    responses = iter([
        ServerError(503, {"error": {"message": "temporarily unavailable"}}),
        SimpleNamespace(text="Bengaluru, India [Doc: company_facts.txt, Chunk: 0]"),
    ])
    def generate_content(**kwargs):
        result = next(responses)
        if isinstance(result, Exception):
            raise result
        return result
    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    monkeypatch.setattr(rag_pipeline.genai, "Client", lambda **kwargs: client)
    sleeps = []
    monkeypatch.setattr(rag_pipeline.time, "sleep", sleeps.append)

    result = rag_pipeline.answer_question("Where is the company headquartered?")

    assert result["grounded"] is True
    assert "Bengaluru" in result["answer"]
    assert sleeps == [1]

def test_unavailable_primary_model_uses_configured_fallback(monkeypatch):
    monkeypatch.setattr(rag_pipeline.settings, "max_cosine_distance", 0.85)
    monkeypatch.setattr(rag_pipeline.settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(rag_pipeline.settings, "gemini_model", "primary-model")
    monkeypatch.setattr(rag_pipeline.settings, "gemini_fallback_model", "fallback-model")
    monkeypatch.setattr(
        rag_pipeline,
        "retrieve",
        lambda *args, **kwargs: [
            _match("company_facts.txt", 0, 0.2, "Headquarters: Bengaluru, India")
        ],
    )
    used_models = []
    def generate_content(**kwargs):
        used_models.append(kwargs["model"])
        if kwargs["model"] == "primary-model":
            raise ServerError(503, {"error": {"message": "temporarily unavailable"}})
        return SimpleNamespace(text="Bengaluru, India [Doc: company_facts.txt, Chunk: 0]")

    monkeypatch.setattr(
        rag_pipeline.genai,
        "Client",
        lambda **kwargs: SimpleNamespace(
            models=SimpleNamespace(generate_content=generate_content)
        ),
    )
    monkeypatch.setattr(rag_pipeline.time, "sleep", lambda _: None)

    result = rag_pipeline.answer_question("Where is the company headquartered?")

    assert result["grounded"] is True
    assert used_models == [
        "primary-model",
        "primary-model",
        "primary-model",
        "fallback-model",
    ]

def test_exhausted_gemini_outage_has_actionable_error(monkeypatch):
    monkeypatch.setattr(rag_pipeline.settings, "max_cosine_distance", 0.85)
    monkeypatch.setattr(rag_pipeline.settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(
        rag_pipeline,
        "retrieve",
        lambda *args, **kwargs: [
            _match("company_facts.txt", 0, 0.2, "Headquarters: Bengaluru, India")
        ],
    )
    monkeypatch.setattr(
        rag_pipeline.genai,
        "Client",
        lambda **kwargs: SimpleNamespace(
            models=SimpleNamespace(
                generate_content=lambda **kwargs: (_ for _ in ()).throw(
                    ServerError(503, {"error": {"message": "temporarily unavailable"}})
                )
            )
        ),
    )
    sleeps = []
    monkeypatch.setattr(rag_pipeline.time, "sleep", sleeps.append)

    try:
        rag_pipeline.answer_question("Where is the company headquartered?")
    except RuntimeError as exc:
        assert "temporarily unavailable" in str(exc)
    else:
        raise AssertionError("Expected an actionable Gemini availability error")

    assert sleeps == [1, 2, 1, 2]
