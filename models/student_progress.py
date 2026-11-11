from sqlalchemy import Column, Integer, Boolean, DateTime, ForeignKey
from datetime import datetime
from database import Base

class StudentProgress(Base):
    __tablename__ = "student_progress"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=True, index=True)
    is_completed = Column(Boolean, default=True)
    completed_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<StudentProgress student_id={self.student_id} course_id={self.course_id} lesson_id={self.lesson_id}>"
