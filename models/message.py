from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from database import Base

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), nullable=False, index=True)
    sender_name = Column(String(100), nullable=False)
    sender_role = Column(String(20), nullable=False) # teacher, student
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Message id={self.id} sender='{self.sender_name}' ({self.sender_role})>"
