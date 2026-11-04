from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from datetime import datetime
from database import Base

class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    classroom_id = Column(Integer, ForeignKey("classroom.id"), nullable=False)
    student_name = Column(String(100), nullable=False)
    session_id = Column(String(64), nullable=False, index=True)
    join_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    leave_time = Column(DateTime, nullable=True)
    ip_address = Column(String(50), nullable=True)
    status = Column(String(20), default="present") # present, left, removed

    def __repr__(self):
        return f"<Attendance id={self.id} student='{self.student_name}' session='{self.session_id}'>"
