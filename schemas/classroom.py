from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class ClassroomUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=120)
    max_students: Optional[int] = Field(None, ge=1, le=20)

class ClassPasswordUpdate(BaseModel):
    new_password: str = Field(..., min_length=4, max_length=50)

class ClassroomResponse(BaseModel):
    id: int
    permanent_id: str
    name: str
    password: str
    max_students: int
    is_live: bool
    current_session_id: Optional[str]
    active_book_id: Optional[int]
    active_page: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
