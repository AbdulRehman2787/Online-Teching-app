import json
import logging
from typing import Dict, Any, Optional, List
from fastapi import WebSocket
from config import settings

logger = logging.getLogger("classroom_manager")

class ClassroomManager:
    def __init__(self):
        # session_id -> { "ws": WebSocket, "name": str, "identity": str, "is_teacher": bool, "mic_allowed": bool, "joined_at": str }
        self.active_participants: Dict[str, Dict[str, Any]] = {}
        self.teacher_session_id: Optional[str] = None
        
        # Classroom Live State
        self.current_book_id: Optional[int] = None
        self.current_page: int = 1
        self.annotations: List[Dict[str, Any]] = [] # drawing strokes/history

    def get_student_count(self) -> int:
        return sum(1 for p in self.active_participants.values() if not p.get("is_teacher", False))

    def can_student_join(self) -> bool:
        return self.get_student_count() < settings.MAX_STUDENTS_LIMIT

    async def connect(self, session_id: str, name: str, is_teacher: bool, websocket: WebSocket):
        await websocket.accept()
        self.active_participants[session_id] = {
            "ws": websocket,
            "name": name,
            "session_id": session_id,
            "is_teacher": is_teacher,
            "mic_allowed": True if is_teacher else False, # Students start muted by default, can be toggled by teacher
        }
        if is_teacher:
            self.teacher_session_id = session_id
            logger.info(f"Teacher connected: {name} ({session_id})")
        else:
            logger.info(f"Student connected: {name} ({session_id}). Total students: {self.get_student_count()}")

        # Notify teacher & students of updated roster
        await self.broadcast_roster_update()

        # Send current class state to the newly connected participant
        state_msg = {
            "type": "class_state",
            "book_id": self.current_book_id,
            "page": self.current_page,
            "annotations": self.annotations,
            "student_count": self.get_student_count(),
            "max_students": settings.MAX_STUDENTS_LIMIT
        }
        await websocket.send_text(json.dumps(state_msg))

    async def disconnect(self, session_id: str):
        if session_id in self.active_participants:
            p = self.active_participants.pop(session_id)
            if p.get("is_teacher", False):
                self.teacher_session_id = None
                logger.info("Teacher disconnected.")
            else:
                logger.info(f"Student disconnected: {p.get('name')}")
            await self.broadcast_roster_update()

    async def broadcast_roster_update(self):
        students_list = [
            {
                "session_id": s_id,
                "name": p["name"],
                "mic_allowed": p.get("mic_allowed", False)
            }
            for s_id, p in self.active_participants.items()
            if not p.get("is_teacher", False)
        ]
        msg = {
            "type": "roster_update",
            "students": students_list,
            "student_count": len(students_list),
            "max_students": settings.MAX_STUDENTS_LIMIT
        }
        await self.broadcast_to_all(msg)

    async def broadcast_to_all(self, data: Dict[str, Any]):
        msg_text = json.dumps(data)
        dead_sessions = []
        for s_id, p in list(self.active_participants.items()):
            try:
                await p["ws"].send_text(msg_text)
            except Exception as e:
                logger.warning(f"Error sending to {s_id}: {e}")
                dead_sessions.append(s_id)
        for s_id in dead_sessions:
            await self.disconnect(s_id)

    async def broadcast_to_students(self, data: Dict[str, Any]):
        msg_text = json.dumps(data)
        for s_id, p in list(self.active_participants.items()):
            if not p.get("is_teacher", False):
                try:
                    await p["ws"].send_text(msg_text)
                except Exception:
                    pass

    async def send_to_teacher(self, data: Dict[str, Any]):
        if self.teacher_session_id and self.teacher_session_id in self.active_participants:
            try:
                await self.active_participants[self.teacher_session_id]["ws"].send_text(json.dumps(data))
            except Exception:
                pass

    async def send_to_session(self, session_id: str, data: Dict[str, Any]):
        if session_id in self.active_participants:
            try:
                await self.active_participants[session_id]["ws"].send_text(json.dumps(data))
            except Exception:
                pass

    async def kick_student(self, session_id: str, reason: str = "Removed by teacher"):
        if session_id in self.active_participants and not self.active_participants[session_id].get("is_teacher"):
            p = self.active_participants[session_id]
            try:
                await p["ws"].send_text(json.dumps({
                    "type": "kicked",
                    "reason": reason
                }))
                await p["ws"].close()
            except Exception:
                pass
            await self.disconnect(session_id)

    async def set_mic_permission(self, session_id: str, is_allowed: bool):
        if session_id in self.active_participants:
            self.active_participants[session_id]["mic_allowed"] = is_allowed
            await self.send_to_session(session_id, {
                "type": "mic_permission_changed",
                "mic_allowed": is_allowed
            })
            await self.broadcast_roster_update()

    async def sync_pdf(self, book_id: Optional[int], page: int):
        self.current_book_id = book_id
        self.current_page = page
        self.annotations = [] # clear page annotations on page switch
        await self.broadcast_to_students({
            "type": "pdf_sync",
            "book_id": book_id,
            "page": page
        })

    async def add_annotation(self, stroke_data: Dict[str, Any]):
        self.annotations.append(stroke_data)
        # Broadcast stroke to all students
        await self.broadcast_to_students({
            "type": "draw_stroke",
            "stroke": stroke_data
        })

    async def clear_annotations(self):
        self.annotations = []
        await self.broadcast_to_students({
            "type": "clear_canvas"
        })

    async def disconnect_all_students_on_password_change(self):
        for s_id, p in list(self.active_participants.items()):
            if not p.get("is_teacher", False):
                try:
                    await p["ws"].send_text(json.dumps({
                        "type": "password_changed",
                        "message": "Class password was changed by teacher. Please re-enter with new password."
                    }))
                    await p["ws"].close()
                except Exception:
                    pass
                if s_id in self.active_participants:
                    del self.active_participants[s_id]
        await self.broadcast_roster_update()

classroom_manager = ClassroomManager()
