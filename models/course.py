from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(150), nullable=False)
    title_urdu = Column(String(150), nullable=True)
    slug = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True, default="Islamic Studies")
    duration = Column(String(50), nullable=True, default="3 Months")
    thumbnail_url = Column(String(300), nullable=True)
    is_published = Column(Boolean, default=True, nullable=False)
    order_index = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    lessons = relationship("Lesson", back_populates="course", cascade="all, delete-orphan", order_by="Lesson.lesson_number")

    def __repr__(self):
        return f"<Course id={self.id} title='{self.title}'>"


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    title = Column(String(150), nullable=False)
    lesson_number = Column(Integer, default=1, nullable=False)
    description = Column(Text, nullable=True)
    content_text = Column(Text, nullable=True)
    pdf_file = Column(String(300), nullable=True)
    video_url = Column(String(300), nullable=True)
    audio_url = Column(String(300), nullable=True)
    is_free_preview = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    course = relationship("Course", back_populates="lessons")

    def __repr__(self):
        return f"<Lesson id={self.id} course_id={self.course_id} title='{self.title}'>"
