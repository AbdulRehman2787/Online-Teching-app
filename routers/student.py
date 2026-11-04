import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session
from database import get_db
from models.classroom import Classroom
from models.attendance import Attendance
from schemas.student import StudentJoinRequest
from services.auth_service import AuthService
from services.livekit_service import LiveKitService
from services.classroom_service import classroom_manager
from config import settings

router = APIRouter(prefix="/api/student", tags=["Student"])

@router.post("/verify-join")
def student_join(
    req: StudentJoinRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    room = db.query(Classroom).filter(Classroom.permanent_id == settings.PERMANENT_CLASS_ID).first()
    if not room:
        raise HTTPException(status_code=404, detail="Classroom does not exist.")

    # 1. Check if class is live
    if not room.is_live:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Class has not started yet. Please wait for the teacher to start the session."
        )

    # 2. Check class password
    if req.class_password.strip() != room.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect class password. Please enter the valid class password provided by the teacher."
        )

    # 3. Check max student limit
    if not classroom_manager.can_student_join():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Classroom is full! Maximum limit of {settings.MAX_STUDENTS_LIMIT} students reached."
        )

    # Generate unique student session
    student_clean_name = req.student_name.strip()
    session_id = f"stud_{uuid.uuid4().hex[:8]}"
    identity = f"student_{session_id}"

    # Log attendance
    client_ip = request.client.host if request.client else "unknown"
    attendance_entry = Attendance(
        classroom_id=room.id,
        student_name=student_clean_name,
        session_id=session_id,
        join_time=datetime.utcnow(),
        ip_address=client_ip,
        status="present"
    )
    db.add(attendance_entry)
    db.commit()

    # Generate student token
    token_payload = {
        "sub": session_id,
        "name": student_clean_name,
        "role": "student",
        "room": room.permanent_id
    }
    student_token = AuthService.create_access_token(token_payload)

    # LiveKit Token
    lk_token = LiveKitService.generate_token(
        room_name=room.permanent_id,
        participant_identity=identity,
        participant_name=student_clean_name,
        is_teacher=False
    )

    response.set_cookie(
        key="student_session_token",
        value=student_token,
        httponly=False, # Accessible to JS client for WebSocket handshake
        max_age=28800,
        samesite="lax"
    )

    return {
        "success": True,
        "session_id": session_id,
        "identity": identity,
        "student_name": student_clean_name,
        "class_name": room.name,
        "permanent_id": room.permanent_id,
        "livekit_token": lk_token,
        "livekit_url": settings.LIVEKIT_URL,
        "active_book_id": room.active_book_id,
        "active_page": room.active_page
    }

@router.get("/status")
def check_class_status(db: Session = Depends(get_db)):
    room = db.query(Classroom).filter(Classroom.permanent_id == settings.PERMANENT_CLASS_ID).first()
    return {
        "is_live": room.is_live if room else False,
        "class_name": room.name if room else "",
        "student_count": classroom_manager.get_student_count(),
        "max_students": settings.MAX_STUDENTS_LIMIT
    }
