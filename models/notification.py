from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from datetime import datetime
from database import Base

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, nullable=True, index=True)  # None means global to all students
    title = Column(String(150), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(50), default="info")  # info, success, warning, live
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Notification id={self.id} title='{self.title}'>"
