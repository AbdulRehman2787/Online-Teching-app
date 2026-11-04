from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from database import Base

class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(String(500), nullable=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, default=0)
    total_pages = Column(Integer, default=1)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Book id={self.id} title='{self.title}'>"
