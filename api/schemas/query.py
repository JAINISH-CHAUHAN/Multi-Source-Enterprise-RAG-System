from pydantic import BaseModel
from typing import List, Optional


class QueryRequest(BaseModel):
    query: str
    top_k: int = 3


class Source(BaseModel):
    source_file: str
    chunk_index: int


class QueryResponse(BaseModel):
    status: str
    query: str
    answer: str
    sources: List[Source] = []
    confidence: Optional[str] = "high"


class CitationDetail(BaseModel):
    source_file: str
    chunk_index: int

    content: str
    
    highlight_text: Optional[str] = None
    highlight_start: Optional[int] = None
    highlight_end: Optional[int] = None

    reason: Optional[str] = None
