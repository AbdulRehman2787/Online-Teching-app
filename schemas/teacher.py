from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

class TeacherCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=120)
    username: str = Field(..., min_length=3, max_length=60)
    email: EmailStr
    phone_number: Optional[str] = Field(None, max_length=30)
    password: str = Field(..., min_length=6, max_length=100)

class TeacherLogin(BaseModel):
    username_or_email: str
    password: str

class TeacherUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=120)
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = Field(None, min_length=6)

class TeacherResponse(BaseModel):
    id: int
    full_name: str
    username: str
    email: str
    phone_number: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
