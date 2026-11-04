import os
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from database import get_db
from models.teacher import Teacher
from models.classroom import Classroom
from models.book import Book
from models.attendance import Attendance
from schemas.classroom import ClassroomResponse, ClassroomUpdate, ClassPasswordUpdate
from schemas.book import BookResponse, BookUpdate
from schemas.attendance import AttendanceResponse
from routers.auth import get_current_teacher
from services.classroom_service import classroom_manager
from services.livekit_service import LiveKitService
from config import settings

router = APIRouter(prefix="/api/teacher", tags=["Teacher Management"])

@router.get("/classroom", response_model=ClassroomResponse)
def get_classroom(
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    room = db.query(Classroom).filter(Classroom.permanent_id == settings.PERMANENT_CLASS_ID).first()
    if not room:
        raise HTTPException(status_code=404, detail="Classroom record not found")
    return room

@router.post("/classroom/start")
def start_class(
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    room = db.query(Classroom).filter(Classroom.permanent_id == settings.PERMANENT_CLASS_ID).first()
    if not room:
        raise HTTPException(status_code=404, detail="Classroom not found")
    
    session_id = f"sess_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    room.is_live = True
    room.current_session_id = session_id
    db.commit()
    db.refresh(room)
    return {"message": "Class started successfully", "session_id": session_id, "is_live": True}

@router.post("/classroom/end")
async def end_class(
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    room = db.query(Classroom).filter(Classroom.permanent_id == settings.PERMANENT_CLASS_ID).first()
    if not room:
        raise HTTPException(status_code=404, detail="Classroom not found")

    if room.current_session_id:
        # Mark all active students attendance leave_time
        now = datetime.utcnow()
        db.query(Attendance).filter(
            Attendance.session_id == room.current_session_id,
            Attendance.leave_time.is_(None)
        ).update({"leave_time": now, "status": "left"})
        db.commit()

    room.is_live = False
    db.commit()

    # Broadcast class ended to all connected students
    await classroom_manager.broadcast_to_students({
        "type": "class_ended",
        "message": "Teacher has ended the class session."
    })

    return {"message": "Class ended successfully", "is_live": False}

@router.put("/classroom/update", response_model=ClassroomResponse)
def update_classroom(
    class_update: ClassroomUpdate,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    room = db.query(Classroom).filter(Classroom.permanent_id == settings.PERMANENT_CLASS_ID).first()
    if not room:
        raise HTTPException(status_code=404, detail="Classroom not found")

    if class_update.name:
        room.name = class_update.name.strip()
    if class_update.max_students:
        room.max_students = class_update.max_students

    db.commit()
    db.refresh(room)
    return room

@router.post("/classroom/change-password")
async def change_class_password(
    password_in: ClassPasswordUpdate,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    room = db.query(Classroom).filter(Classroom.permanent_id == settings.PERMANENT_CLASS_ID).first()
    if not room:
        raise HTTPException(status_code=404, detail="Classroom not found")

    new_pass = password_in.new_password.strip()
    if not new_pass:
        raise HTTPException(status_code=400, detail="Password cannot be empty")

    room.password = new_pass
    db.commit()

    # Invalidate and disconnect all active students immediately
    await classroom_manager.disconnect_all_students_on_password_change()

    return {"message": "Class password changed successfully. All active students have been disconnected."}

# ==================== Book Management ====================

@router.get("/books", response_model=list[BookResponse])
def get_books(
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    return db.query(Book).order_by(Book.uploaded_at.desc()).all()

@router.post("/books/upload", response_model=BookResponse)
async def upload_book(
    title: str = Form(...),
    description: str = Form(None),
    file: UploadFile = File(...),
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    unique_filename = f"{uuid.uuid4().hex}_{file.filename}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    file_size = 0
    with open(file_path, "wb") as buffer:
        while chunk := await file.read(1024 * 1024): # 1MB chunks
            file_size += len(chunk)
            if file_size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
                buffer.close()
                if os.path.exists(file_path):
                    os.remove(file_path)
                raise HTTPException(
                    status_code=400,
                    detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB."
                )
            buffer.write(chunk)

    new_book = Book(
        title=title.strip(),
        description=description.strip() if description else None,
        filename=unique_filename,
        file_path=file_path,
        file_size=file_size,
        total_pages=1 # PDF.js on client side determines total pages upon load
    )
    db.add(new_book)
    db.commit()
    db.refresh(new_book)
    return new_book

@router.put("/books/{book_id}", response_model=BookResponse)
def update_book(
    book_id: int,
    book_in: BookUpdate,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    if book_in.title:
        book.title = book_in.title.strip()
    if book_in.description is not None:
        book.description = book_in.description.strip()
    db.commit()
    db.refresh(book)
    return book

@router.delete("/books/{book_id}")
def delete_book(
    book_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    if os.path.exists(book.file_path):
        try:
            os.remove(book.file_path)
        except Exception:
            pass

    db.delete(book)
    db.commit()
    return {"message": "Book deleted successfully"}

# ==================== Attendance & Controls ====================

@router.get("/attendance", response_model=list[AttendanceResponse])
def get_attendance_logs(
    session_id: str = None,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    query = db.query(Attendance)
    if session_id:
        query = query.filter(Attendance.session_id == session_id)
    return query.order_by(Attendance.join_time.desc()).limit(200).all()

@router.get("/students/active")
def get_active_students(teacher: Teacher = Depends(get_current_teacher)):
    students = [
        {
            "session_id": s_id,
            "name": p["name"],
            "mic_allowed": p.get("mic_allowed", False),
            "joined_at": p.get("joined_at", "")
        }
        for s_id, p in classroom_manager.active_participants.items()
        if not p.get("is_teacher", False)
    ]
    return {
        "count": len(students),
        "max_limit": settings.MAX_STUDENTS_LIMIT,
        "students": students
    }

@router.post("/students/{session_id}/kick")
async def kick_student_endpoint(
    session_id: str,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    # Update attendance record status
    db.query(Attendance).filter(
        Attendance.session_id == session_id,
        Attendance.leave_time.is_(None)
    ).update({"leave_time": datetime.utcnow(), "status": "removed"})
    db.commit()

    await classroom_manager.kick_student(session_id)
    return {"message": "Student kicked successfully"}

@router.post("/students/{session_id}/mic")
async def toggle_student_mic(
    session_id: str,
    allow: bool,
    teacher: Teacher = Depends(get_current_teacher)
):
    await classroom_manager.set_mic_permission(session_id, allow)
    return {"message": f"Microphone permission set to {allow}"}

@router.get("/livekit-token")
def get_teacher_livekit_token(teacher: Teacher = Depends(get_current_teacher)):
    room_name = settings.PERMANENT_CLASS_ID
    identity = f"teacher_{teacher.username}"
    token = LiveKitService.generate_token(
        room_name=room_name,
        participant_identity=identity,
        participant_name=teacher.full_name,
        is_teacher=True
    )
    return {
        "token": token,
        "livekit_url": settings.LIVEKIT_URL,
        "room_name": room_name,
        "participant_name": teacher.full_name,
        "participant_identity": identity,
        "is_teacher": True
    }
