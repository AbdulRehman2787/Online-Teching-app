from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class StudentJoinRequest(BaseModel):
    student_name: str = Field(..., min_length=2, max_length=50)
    class_password: str = Field(..., min_length=1)

class LiveKitTokenResponse(BaseModel):
    token: str
    livekit_url: str
    room_name: str
    participant_name: str
    participant_identity: str
    is_teacher: bool

class StudentRegisterRequest(BaseModel):
    student_name: str = Field(..., min_length=2, max_length=120)
    parent_name: str = Field(..., min_length=2, max_length=120)
    whatsapp_number: str = Field(..., min_length=7, max_length=30)
    country: str = Field(default="Pakistan", max_length=80)
    age: Optional[int] = Field(None, ge=3, le=100)
    email: Optional[str] = Field(None, max_length=120)
    requested_course: Optional[str] = Field(default="نورانی قاعدہ مع تجوید", max_length=150)

class StudentLoginRequest(BaseModel):
    login_identifier: str = Field(..., min_length=2, max_length=100) # Student ID or WhatsApp
    password: str = Field(..., min_length=3)

class StudentApproveRequest(BaseModel):
    custom_password: Optional[str] = None

class StudentEditRequest(BaseModel):
    full_name: Optional[str] = None
    parent_name: Optional[str] = None
    whatsapp_number: Optional[str] = None
    country: Optional[str] = None
    age: Optional[int] = None
    email: Optional[str] = None
    requested_course: Optional[str] = None
    notes: Optional[str] = None

class StudentResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=4)
