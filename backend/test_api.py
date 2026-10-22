from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_production_frontend_is_allowed_by_cors():
    origin = "https://enterprise-rag-assistant-six.vercel.app"

    response = client.options(
        "/documents",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin

def test_upload_rejects_unsupported_file():
    response = client.post("/upload", files={"file": ("bad.png", b"x", "image/png")})
    assert response.status_code == 400

def test_upload_logs_processing_exception_without_exposing_details(monkeypatch):
    traceback_calls = []

    def raise_processing_error(*args, **kwargs):
        raise Exception("internal path or service credential details")

    monkeypatch.setattr("backend.main.extract_text", raise_processing_error)
    monkeypatch.setattr(
        "backend.main.traceback.print_exc",
        lambda: traceback_calls.append(True),
    )

    response = client.post(
        "/upload",
        files={"file": ("facts.txt", b"company facts", "text/plain")},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Document processing failed."}
    assert traceback_calls == [True]

def test_blank_query_rejected():
    response = client.post("/query", json={"question": "   "})
    assert response.status_code == 422

def test_gemini_unavailable_returns_service_unavailable(monkeypatch):
    def raise_gemini_error(question, document_name=None):
        raise RuntimeError("Gemini is temporarily unavailable after multiple attempts. Please try again.")

    monkeypatch.setattr("backend.main.answer_question", raise_gemini_error)

    response = client.post("/query", json={"question": "Where is the office?"})

    assert response.status_code == 503
    assert "Gemini is temporarily unavailable" in response.json()["detail"]
