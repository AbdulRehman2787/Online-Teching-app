from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from datetime import datetime
from database import Base

class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String(30), unique=True, index=True, nullable=False)  # e.g., STU-1001
    full_name = Column(String(120), nullable=False)
    parent_name = Column(String(120), nullable=False)
    whatsapp_number = Column(String(50), nullable=False, index=True)
    country = Column(String(80), nullable=False, default="Pakistan")
    age = Column(Integer, nullable=True)
    email = Column(String(120), nullable=True)
    requested_course = Column(String(150), nullable=True, default="نورانی قاعدہ مع تجوید")
    
    # Status: 'pending', 'approved', 'rejected', 'blocked'
    status = Column(String(30), nullable=False, default="pending", index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Secure Password (hashed with bcrypt)
    password_hash = Column(String(255), nullable=True)
    temp_password = Column(String(100), nullable=True) # Handy for Admin to share directly on WhatsApp
    
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)
    last_login = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<Student id={self.id} student_id='{self.student_id}' name='{self.full_name}' status='{self.status}'>"
