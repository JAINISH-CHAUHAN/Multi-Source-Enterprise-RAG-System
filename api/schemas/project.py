from pydantic import BaseModel
from uuid import UUID

class ProjectCreateRequest(BaseModel):
    name: str

class ProjectResponse(BaseModel):
    id: UUID
    name: str
