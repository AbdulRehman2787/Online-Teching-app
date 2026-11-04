from sqlalchemy import Column, Integer, String, Boolean, DateTime
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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Classroom id={self.id} permanent_id='{self.permanent_id}' is_live={self.is_live}>"
