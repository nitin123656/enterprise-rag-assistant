from pathlib import Path
import traceback

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from backend.config import settings
from backend.document_processor import extract_text, chunk_text
from backend.schemas import QueryRequest, QueryResponse
from backend.vector_store import upsert_chunks, list_documents, delete_document
from backend.rag_pipeline import answer_question

app = FastAPI(title=settings.app_name, version="1.0.0",
              description="Upload PDFs/TXT files and ask grounded questions with source citations.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    filename = Path(file.filename or "").name
    if not filename or Path(filename).suffix.lower() not in {".pdf", ".txt"}:
        raise HTTPException(status_code=400, detail="Only PDF and TXT files are supported.")
    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Maximum upload size is {settings.max_upload_mb} MB.")
    try:
        text = extract_text(filename, content)
        chunks = chunk_text(text, settings.chunk_size, settings.chunk_overlap)
        if not chunks:
            raise ValueError("No usable text chunks were produced.")
        count = upsert_chunks(filename, chunks)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Document processing failed.") from exc
    return {"message": "Document indexed successfully.", "document_name": filename,
            "chunk_count": count}

@app.post("/query", response_model=QueryResponse)
def query_document(request: QueryRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question must not be blank.")
    try:
        return answer_question(question, request.document_name)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Query processing failed.") from exc

@app.get("/documents")
def documents():
    return {"documents": list_documents()}

@app.delete("/documents/{document_name}")
def remove_document(document_name: str):
    if not delete_document(document_name):
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"message": f"Deleted {document_name}."}
