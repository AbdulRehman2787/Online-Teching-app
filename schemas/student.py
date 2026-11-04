from pydantic import BaseModel, Field

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
