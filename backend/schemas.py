from pydantic import BaseModel, Field

class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    document_name: str | None = Field(default=None, max_length=255)

class SourceCitation(BaseModel):
    document_name: str
    chunk_index: int
    excerpt: str
    distance: float | None = None

class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceCitation]
    grounded: bool
