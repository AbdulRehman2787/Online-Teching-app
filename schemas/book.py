from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class BookCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = Field(None, max_length=500)

class BookUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = Field(None, max_length=500)

class BookResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    filename: str
    file_path: str
    file_size: int
    total_pages: int
    uploaded_at: datetime

    class Config:
        from_attributes = True
