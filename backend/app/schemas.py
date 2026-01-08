from pydantic import BaseModel, Field
from uuid import UUID

class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)

class ProjectOut(BaseModel):
    id: UUID
    name: str

class SessionCreate(BaseModel):
    project_id: UUID
    created_by: UUID | None = None

class SessionOut(BaseModel):
    id: UUID
    project_id: UUID

