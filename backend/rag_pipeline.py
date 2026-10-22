import logging
import time

from google import genai
from google.genai.errors import APIError
from google.genai import types
from backend.config import settings
from backend.prompts import SYSTEM_PROMPT, FALLBACK_ANSWER
from backend.vector_store import retrieve

GEMINI_MAX_ATTEMPTS = 3
GEMINI_RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
logger = logging.getLogger(__name__)


def answer_question(question: str, document_name: str | None = None) -> dict:
    matches = retrieve(question, top_k=settings.top_k, document_name=document_name)
    matches = [
        row for row in matches
        if row["distance"] <= settings.max_cosine_distance
    ]
    if not matches:
        return {"answer": FALLBACK_ANSWER, "sources": [], "grounded": False}

    context_parts, sources = [], []
    for row in matches:
        meta = row["metadata"]
        label = f'[Doc: {meta["document_name"]}, Chunk: {meta["chunk_index"]}]'
        context_parts.append(f"{label}\n{row['text']}")
        sources.append({
            "document_name": meta["document_name"],
            "chunk_index": int(meta["chunk_index"]),
            "excerpt": row["text"][:350],
            "distance": row["distance"],
        })

    prompt = SYSTEM_PROMPT.format(context="\n\n---\n\n".join(context_parts), question=question)
    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY or GOOGLE_API_KEY is not configured. Add one to your environment."
        )

    client = genai.Client(api_key=settings.gemini_api_key)
    models = list(dict.fromkeys(
        model for model in (settings.gemini_model, settings.gemini_fallback_model) if model
    ))
    response = None
    last_error = None
    for model in models:
        for attempt in range(GEMINI_MAX_ATTEMPTS):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.1),
                )
                break
            except APIError as exc:
                last_error = exc
                if (
                    exc.code in GEMINI_RETRYABLE_STATUS_CODES
                    and attempt < GEMINI_MAX_ATTEMPTS - 1
                ):
                    time.sleep(2**attempt)
                    continue
                if exc.code in GEMINI_RETRYABLE_STATUS_CODES or exc.code == 404:
                    logger.warning(
                        "Gemini model %s failed with HTTP %s; trying the next configured model.",
                        model,
                        exc.code,
                    )
                    break
                if exc.code == 401 or exc.code == 403:
                    detail = "Gemini rejected the API credentials. Check GEMINI_API_KEY and API access."
                else:
                    detail = f"Gemini rejected the request (HTTP {exc.code}): {exc.message}"
                raise RuntimeError(detail) from exc
        if response is not None:
            break

    if response is None:
        if last_error is not None and last_error.code == 404:
            detail = "No configured Gemini model is available. Check GEMINI_MODEL and GEMINI_FALLBACK_MODEL."
        else:
            detail = "Gemini is temporarily unavailable after retrying the configured models. Please try again."
        raise RuntimeError(detail) from last_error

    answer = (response.text or "").strip()
    if not answer:
        answer = FALLBACK_ANSWER

    # Sources returned to the UI are always derived from retrieved database metadata.
    # The model's prose citations are instructed to use the same labels.
    grounded = answer != FALLBACK_ANSWER
    return {"answer": answer, "sources": sources if grounded else [], "grounded": grounded}
