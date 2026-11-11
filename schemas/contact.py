from pydantic import BaseModel
from typing import Optional

class ContactSettingsUpdate(BaseModel):
    institute_name: Optional[str] = None
    teacher_name: Optional[str] = None
    whatsapp_number: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    welcome_quote: Optional[str] = None
