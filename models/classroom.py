from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from datetime import datetime
from database import Base

class Classroom(Base):
    __tablename__ = "classroom"

    id = Column(Integer, primary_key=True, index=True)
    permanent_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(120), nullable=False, default="Master Live Classroom")
    password = Column(String(60), nullable=False, default="Learn123")
    max_students = Column(Integer, default=20, nullable=False)
    is_live = Column(Boolean, default=False, nullable=False)
    current_session_id = Column(String(64), nullable=True)
    active_book_id = Column(Integer, nullable=True)
    active_page = Column(Integer, default=1)
    
    # Zoom Integration
    zoom_link = Column(String(500), nullable=True, default="https://zoom.us/join")
    zoom_meeting_id = Column(String(100), nullable=True, default="854 2190 3341")
    zoom_password = Column(String(100), nullable=True, default="786786")
    zoom_topic = Column(String(200), nullable=True, default="روزانہ کی آن لائن کلاس (Zoom Live)")
    zoom_instructions = Column(String(500), nullable=True, default="کلاس کے وقت زووم لنک پر کلک کریں اور لائیو کلاس میں شرکت کریں۔")
    is_zoom_live = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Classroom id={self.id} permanent_id='{self.permanent_id}' is_live={self.is_live}>"
