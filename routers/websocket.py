import json
import logging
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from database import SessionLocal
from models.classroom import Classroom
from models.attendance import Attendance
from models.message import Message
from services.classroom_service import classroom_manager
from config import settings

logger = logging.getLogger("websocket_router")
router = APIRouter(tags=["WebSocket"])

@router.websocket("/ws/classroom/{session_id}")
async def websocket_classroom(websocket: WebSocket, session_id: str, role: str = "student", name: str = "Anonymous"):
    is_teacher = (role == "teacher")
    await classroom_manager.connect(session_id, name, is_teacher, websocket)

    db: Session = SessionLocal()
    try:
        while True:
            data_text = await websocket.receive_text()
            try:
                data = json.loads(data_text)
            except Exception:
                continue

            event_type = data.get("type")

            # 1. Live Chat
            if event_type == "chat_message":
                text = data.get("message", "").strip()
                if text:
                    # Save to DB
                    msg_record = Message(
                        session_id=session_id,
                        sender_name=name,
                        sender_role=role,
                        message=text,
                        timestamp=datetime.utcnow()
                    )
                    db.add(msg_record)
                    db.commit()

                    # Broadcast to everyone
                    await classroom_manager.broadcast_to_all({
                        "type": "chat_message",
                        "sender_name": name,
                        "sender_role": role,
                        "message": text,
                        "time": datetime.utcnow().strftime("%I:%M %p")
                    })

            # 2. PDF Page Synchronization (Teacher Only)
            elif event_type == "pdf_sync" and is_teacher:
                book_id = data.get("book_id")
                page = data.get("page", 1)
                
                # Update classroom active book in DB
                room = db.query(Classroom).filter(Classroom.permanent_id == settings.PERMANENT_CLASS_ID).first()
                if room:
                    room.active_book_id = book_id
                    room.active_page = page
                    db.commit()

                await classroom_manager.sync_pdf(book_id, page)

            # 3. Teacher Drawing / Annotation (Teacher Only)
            elif event_type == "draw_stroke" and is_teacher:
                stroke_data = data.get("stroke")
                if stroke_data:
                    await classroom_manager.add_annotation(stroke_data)

            # 4. Clear Canvas / Annotations (Teacher Only)
            elif event_type == "clear_canvas" and is_teacher:
                await classroom_manager.clear_annotations()

            # 5. Teacher Mic Control
            elif event_type == "toggle_mic" and is_teacher:
                target_session_id = data.get("target_session_id")
                allow = data.get("allow", False)
                if target_session_id:
                    await classroom_manager.set_mic_permission(target_session_id, allow)

            # 6. Teacher Kick Student
            elif event_type == "kick_student" and is_teacher:
                target_session_id = data.get("target_session_id")
                if target_session_id:
                    # Update attendance
                    db.query(Attendance).filter(
                        Attendance.session_id == target_session_id,
                        Attendance.leave_time.is_(None)
                    ).update({"leave_time": datetime.utcnow(), "status": "removed"})
                    db.commit()
                    await classroom_manager.kick_student(target_session_id)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for {session_id}: {e}")
    finally:
        # Mark attendance leave time if student
        if not is_teacher:
            try:
                db.query(Attendance).filter(
                    Attendance.session_id == session_id,
                    Attendance.leave_time.is_(None)
                ).update({"leave_time": datetime.utcnow(), "status": "left"})
                db.commit()
            except Exception:
                pass
        db.close()
        await classroom_manager.disconnect(session_id)
