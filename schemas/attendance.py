from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class AttendanceResponse(BaseModel):
    id: int
    classroom_id: int
    student_name: str
    session_id: str
    join_time: datetime
    leave_time: Optional[datetime]
    ip_address: Optional[str]
    status: str

    class Config:
        from_attributes = True
