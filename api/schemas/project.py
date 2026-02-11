from pydantic import BaseModel
from uuid import UUID
from typing import Optional

class ProjectCreateRequest(BaseModel):
    name: str

class ProjectResponse(BaseModel):
    id: UUID
    name: str
    
    # Error handling fields (populated only on failure)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
