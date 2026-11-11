from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from datetime import datetime
from database import Base

class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    author = Column(String(120), nullable=True, default="نامعلوم مصنف")
    category = Column(String(80), nullable=True, default="قرآنی علوم")
    description = Column(Text, nullable=True)
    cover_image = Column(String(300), nullable=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, default=0)
    total_pages = Column(Integer, default=1)
    is_published = Column(Boolean, default=True, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Book id={self.id} title='{self.title}' author='{self.author}'>"
