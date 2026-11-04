from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from database import Base

class Teacher(Base):
    __tablename__ = "teacher"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(120), nullable=False)
    username = Column(String(60), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    phone_number = Column(String(30), nullable=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Teacher id={self.id} username='{self.username}'>"
