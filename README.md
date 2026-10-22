# Enterprise Document Knowledge Assistant (RAG)

A full-stack proof of concept: React + Vite frontend, FastAPI backend, persistent ChromaDB vector storage, local Sentence Transformers embeddings, and Gemini answer generation.

## Features

- Upload PDF and UTF-8 TXT documents. Scanned PDF pages are processed with local English OCR.
- Extract text and split it into 1,200-character chunks with 100-character overlap. Markdown heading context is included in each chunk.
- Generate embeddings locally and persist vectors in ChromaDB.
- Retrieve up to three relevant chunks using cosine distance.
- Generate grounded answers with source labels and source excerpts.
- Reject weak retrieval matches using a configurable distance threshold.
- List and delete indexed documents; re-uploading the same filename replaces its previous chunks.
- Basic API tests and document-processing tests.

## Requirements

- Windows 10/11
- Python 3.11 recommended
- Node.js 20 or newer
- Tesseract OCR 5 with English language data, installed and available on `PATH`
- Gemini API key for answer generation
- Internet access for initial package/model downloads and Gemini requests

## Windows setup (PowerShell)

Open PowerShell in the project root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
winget install --id UB-Mannheim.TesseractOCR --exact
Copy-Item .env.example .env
notepad .env
```

If Tesseract was installed after opening PowerShell, open a new terminal so its PATH update is picked up.
Add your Gemini API key to `.env`. Keep this file private and do not commit it to Git.
The backend retries temporary Gemini errors and then tries `GEMINI_FALLBACK_MODEL`
(`gemini-3.5-flash` by default). If both models remain unavailable, the API returns HTTP 503
with a message the frontend can display.

If PowerShell blocks activation, use this for the current terminal only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Start the backend

From the project root, with the virtual environment active:

```powershell
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Open API docs at http://127.0.0.1:8000/docs.

The first request that initializes embeddings may download the model and PyTorch dependencies; allow extra time.

### Start the frontend

Open a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

## Deploy publicly (Azure backend + Vercel frontend)

The API needs persistent local storage for ChromaDB, so deploy it as an Azure App Service
custom Linux container with persistent `/home` storage. Deploy the React app separately to
Vercel.

### Deploy the backend to Azure

1. Create an Azure Linux Web App using the repository's root `Dockerfile`. Choose an App
   Service plan with enough memory for PyTorch and the sentence-transformer model.
2. Enable persistent container storage with `WEBSITES_ENABLE_APP_SERVICE_STORAGE=true`.
   Set `WEBSITES_PORT=8000` and `CHROMA_PATH=/home/chroma`.
3. Configure these application settings in Azure:
   - `GEMINI_API_KEY`: your private Gemini key (store it as an Azure app setting; never commit it)
   - `GEMINI_MODEL=gemini-3.8-flash`
   - `GEMINI_FALLBACK_MODEL=gemini-3.5-flash`
   - `CORS_ORIGINS`: the exact Vercel site origin, for example `https://your-project.vercel.app`
4. Start the Web App and verify `https://<your-api-host>/health` returns
   `{"status":"healthy"}`.

Uploaded files and their extracted text are stored in ChromaDB on the persistent `/home`
volume. Back up that volume if the indexed data matters; the app does not configure automated
backups or authentication.

### Deploy the frontend to Vercel

1. Import this GitHub repository into Vercel and set the project root directory to `frontend`.
2. Add the `VITE_API_URL` environment variable with the Azure API origin, for example
   `https://your-api-host.azurewebsites.net` (no trailing slash). The `frontend/.env.production`
   file supplies the current Render API origin unless a Vercel environment variable overrides it.
3. Deploy, then add the exact Vercel site origin to the backend `CORS_ORIGINS` setting and
   restart or redeploy the API.

Deploying publicly exposes document upload, querying, listing, and deletion to visitors. Add
authentication and access controls before using it with private or sensitive documents.

## API reference

### `GET /health`
Returns `200 OK` with:

```json
{
  "status": "healthy"
}
```

### `POST /upload`
Multipart form field: `file`. Accepts `.pdf` and `.txt`, up to 15 MB by default. PDF pages without
an embedded text layer are rendered locally and OCR-processed in English. If OCR is needed but
Tesseract is unavailable, the endpoint returns HTTP 503 with installation guidance.

Example response:

```json
{
  "message": "Document indexed successfully.",
  "document_name": "handbook.pdf",
  "chunk_count": 14
}
```

### `POST /query`
Request:

```json
{
  "question": "How many vacation days are provided?",
  "document_name": "handbook.pdf"
}
```

`document_name` is optional. When omitted, search all indexed documents.

Response shape:

```json
{
  "answer": "The handbook provides ... [Doc: handbook.pdf, Chunk: 2]",
  "sources": [
    {
      "document_name": "handbook.pdf",
      "chunk_index": 2,
      "excerpt": "Employees are eligible for ...",
      "distance": 0.23
    }
  ],
  "grounded": true
}
```

If no matching context passes the configured retrieval threshold, the answer is:

`I am sorry, but the provided documents do not contain enough information to answer this question.`

### `GET /documents`
Lists indexed document names and chunk counts.

### `DELETE /documents/{document_name}`
Deletes all indexed chunks for a document. URL-encode document names containing reserved characters.

## Run tests

```powershell
pytest -q
```

Tests cover extraction, chunk validation, API health, unsupported uploads and blank questions. They do not call Gemini or require the embedding model. Some API tests may initialize the vector collection indirectly only if the application code is changed to do so.

## How RAG works

1. **Ingestion:** extract text from a PDF/TXT file.
2. **Chunking:** recursive character splitting preserves useful boundaries and overlaps adjacent chunks.
3. **Embedding:** a local Sentence Transformers model maps each chunk into a dense vector.
4. **Indexing:** ChromaDB persists the vector, chunk text, filename and chunk index.
5. **Retrieval:** the question is embedded and ChromaDB returns up to three nearest chunks using cosine distance.
6. **Grounding:** weak matches are rejected; otherwise retrieved context is inserted into the prompt.
7. **Generation:** Gemini answers from the context and is instructed to cite its chunk labels.
8. **Evidence UI:** the API returns source metadata and excerpts from the database, not metadata invented by the model.

## Design decisions and limitations

- `chunk_size=1200` and `chunk_overlap=100` are **characters**, not tokens. Markdown heading context is prepended to each chunk to retain its section hierarchy. Tune these values using representative documents and questions.
- ChromaDB cosine **distance** is lower for closer matches. The `MAX_COSINE_DISTANCE` threshold is a heuristic, not a calibrated confidence score; evaluate it with an in-domain validation set.
- Source excerpts come from retrieved chunks. Model-generated citation strings are not independently verified at claim level in this PoC.
- Prompt instructions reduce but cannot eliminate hallucinations or prompt injection. Retrieved document text is explicitly treated as untrusted context.
- Local persistent ChromaDB is appropriate for a single-user demo, not a multi-tenant production deployment.
- Production hardening would include authentication, per-user document isolation, rate limits, malware scanning, stricter CORS, structured citation validation, OCR, monitoring and evaluation.

## Interview explanation (60–90 seconds)

“I built a Retrieval-Augmented Generation application for querying enterprise documents. The ingestion pipeline extracts PDF/TXT text, splits it into overlapping chunks, embeds them with Sentence Transformers, and stores the embeddings with source metadata in persistent ChromaDB. When a user asks a question, the backend retrieves the top three chunks by cosine distance, rejects weak matches using a configurable threshold, and sends the remaining context to Gemini with strict grounding and citation instructions. The UI displays the answer alongside the retrieved source excerpts, so users can verify the evidence. I separated ingestion, storage, retrieval, generation and UI code to make the pipeline testable and maintainable.”

## Suggested next improvements

1. Add a document-level and page-number filter.
2. Add a small evaluation set and measure retrieval precision/recall.
3. Validate each citation against retrieved chunk IDs and flag unsupported claims.
4. Add OCR for scanned PDFs.
5. Add authentication and tenant-level isolation before handling confidential documents.
