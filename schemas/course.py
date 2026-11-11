from pydantic import BaseModel, Field
from typing import Optional

class CourseCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=150)
    title_urdu: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = "Islamic Studies"
    duration: Optional[str] = "3 Months"
    thumbnail_url: Optional[str] = None

class CourseUpdate(BaseModel):
    title: Optional[str] = None
    title_urdu: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    duration: Optional[str] = None
    thumbnail_url: Optional[str] = None
    is_published: Optional[bool] = None

class LessonCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=150)
    lesson_number: int = Field(default=1, ge=1)
    description: Optional[str] = None
    content_text: Optional[str] = None
    video_url: Optional[str] = None
    audio_url: Optional[str] = None
    is_free_preview: Optional[bool] = False

class LessonUpdate(BaseModel):
    title: Optional[str] = None
    lesson_number: Optional[int] = None
    description: Optional[str] = None
    content_text: Optional[str] = None
    video_url: Optional[str] = None
    audio_url: Optional[str] = None
    is_free_preview: Optional[bool] = None
