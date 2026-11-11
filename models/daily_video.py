from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from datetime import datetime
from database import Base

class DailyVideo(Base):
    __tablename__ = "daily_videos"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    video_type = Column(String(20), default="url")  # "url" or "file"
    video_url = Column(String(500), nullable=False)
    thumbnail_url = Column(String(500), nullable=True)
    category = Column(String(100), default="روزانہ کا سبق")
    duration = Column(String(50), nullable=True, default="")
    is_published = Column(Boolean, default=True)
    date_posted = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<DailyVideo id={self.id} title='{self.title}' category='{self.category}'>"
