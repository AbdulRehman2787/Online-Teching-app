import os
import re
import uuid
import urllib.parse
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_

from database import get_db
from models.teacher import Teacher
from models.student import Student
from models.course import Course, Lesson
from models.book import Book
from models.classroom import Classroom
from models.contact_setting import ContactSetting
from models.student_progress import StudentProgress
from models.notification import Notification
from models.daily_video import DailyVideo
from routers.auth import get_current_teacher
from services.auth_service import AuthService
from services.classroom_service import classroom_manager
from config import settings

router = APIRouter(prefix="/api/admin", tags=["Admin Management"])

# ==========================================
# 1. STUDENT MANAGEMENT
# ==========================================

@router.get("/students")
def list_students(
    q: Optional[str] = None,
    status_filter: Optional[str] = None,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    query = db.query(Student)

    if status_filter and status_filter != "all":
        query = query.filter(Student.status == status_filter)

    if q:
        q_clean = q.strip()
        query = query.filter(
            or_(
                Student.full_name.ilike(f"%{q_clean}%"),
                Student.parent_name.ilike(f"%{q_clean}%"),
                Student.whatsapp_number.ilike(f"%{q_clean}%"),
                Student.student_id.ilike(f"%{q_clean}%"),
                Student.email.ilike(f"%{q_clean}%")
            )
        )

    students = query.order_by(Student.created_at.desc()).all()

    return {
        "total": len(students),
        "students": [
            {
                "id": s.id,
                "student_id": s.student_id,
                "full_name": s.full_name,
                "parent_name": s.parent_name,
                "whatsapp_number": s.whatsapp_number,
                "country": s.country,
                "age": s.age,
                "email": s.email,
                "requested_course": s.requested_course,
                "status": s.status,
                "is_active": s.is_active,
                "temp_password": s.temp_password,
                "created_at": s.created_at.strftime("%Y-%m-%d %H:%M") if s.created_at else None,
                "approved_at": s.approved_at.strftime("%Y-%m-%d %H:%M") if s.approved_at else None,
                "last_login": s.last_login.strftime("%Y-%m-%d %H:%M") if s.last_login else None,
                "notes": s.notes
            }
            for s in students
        ]
    }

@router.post("/students/{student_id}/approve")
def approve_student(
    student_id: int,
    request: Request,
    custom_password: Optional[str] = Form(None),
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="طالب علم نہیں ملا")

    password_to_use = custom_password.strip() if custom_password and custom_password.strip() else (student.temp_password or AuthService.generate_simple_password())
    student.password_hash = AuthService.get_password_hash(password_to_use)
    student.temp_password = password_to_use
    student.status = "approved"
    student.is_active = True
    student.approved_at = datetime.utcnow()

    db.commit()
    db.refresh(student)

    # Format WhatsApp notification share text
    base_url = str(request.base_url).rstrip("/")
    login_url = f"{base_url}/login"
    wa_message = (
        f"السلام علیکم ورحمۃ اللہ وبرکاتہ!\n\n"
        f"محترم والدین/طالب علم {student.full_name}،\n"
        f"دار التعلیم والقرآن اکیڈمی میں آپ کا داخلہ بحمداللہ منظور کر لیا گیا ہے۔\n\n"
        f"آپ کی لاگ ان تفصیلات درج ذیل ہیں:\n"
        f"🔑 اسٹوڈنٹ آئی ڈی: {student.student_id}\n"
        f"🔒 پاسورڈ: {password_to_use}\n"
        f"📚 منتخب کورس: {student.requested_course}\n\n"
        f"🌐 کلاس روم اور ڈیش بورڈ میں داخل ہونے کا لنک:\n{login_url}\n\n"
        f"جزاکم اللہ خیراً واحسن الجزاء"
    )

    clean_phone = student.whatsapp_number.replace("+", "").replace(" ", "").replace("-", "")
    whatsapp_share_url = f"https://wa.me/{clean_phone}?text={urllib.parse.quote(wa_message)}"

    return {
        "success": True,
        "message": f"طالب علم {student.full_name} کا داخلہ کامیابی سے منظور ہو گیا ہے۔",
        "student_id": student.student_id,
        "password": password_to_use,
        "whatsapp_url": whatsapp_share_url
    }

@router.post("/students/{student_id}/reject")
def reject_student(
    student_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="طالب علم نہیں ملا")

    student.status = "rejected"
    student.is_active = False
    db.commit()
    return {"success": True, "message": "درخواست مسترد کر دی گئی۔"}

@router.post("/students/{student_id}/toggle-status")
def toggle_student_status(
    student_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="طالب علم نہیں ملا")

    if student.status == "blocked" or not student.is_active:
        student.status = "approved"
        student.is_active = True
        msg = "طالب علم کا اکاؤنٹ دوبارہ فعال (Activate) کر دیا گیا ہے۔"
    else:
        student.status = "blocked"
        student.is_active = False
        msg = "طالب علم کا اکاؤنٹ بلاک (Deactivate) کر دیا گیا ہے۔"

    db.commit()
    return {"success": True, "message": msg, "new_status": student.status}

@router.post("/students/{student_id}/reset-password")
def reset_student_password(
    student_id: int,
    new_password: str = Form(...),
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="طالب علم نہیں ملا")

    clean_pass = new_password.strip()
    if len(clean_pass) < 4:
        raise HTTPException(status_code=400, detail="پاسورڈ کم از کم 4 ہندسوں یا حروف پر مشتمل ہونا چاہیے۔")

    student.password_hash = AuthService.get_password_hash(clean_pass)
    student.temp_password = clean_pass
    db.commit()

    return {"success": True, "message": "پاسورڈ کامیابی سے تبدیل ہو گیا ہے۔", "password": clean_pass}

@router.post("/students/{student_id}/edit")
def edit_student_info(
    student_id: int,
    full_name: str = Form(...),
    parent_name: str = Form(...),
    whatsapp_number: str = Form(...),
    country: str = Form("Pakistan"),
    age: Optional[int] = Form(None),
    email: Optional[str] = Form(None),
    requested_course: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="طالب علم نہیں ملا")

    student.full_name = full_name.strip()
    student.parent_name = parent_name.strip()
    student.whatsapp_number = whatsapp_number.strip()
    student.country = country.strip()
    student.age = age
    student.email = email.strip() if email else None
    if requested_course:
        student.requested_course = requested_course.strip()
    student.notes = notes.strip() if notes else None

    db.commit()
    return {"success": True, "message": "طالب علم کی معلومات محفوظ ہو گئیں۔"}

@router.delete("/students/{student_id}")
def delete_student(
    student_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="طالب علم نہیں ملا")

    db.query(StudentProgress).filter(StudentProgress.student_id == student.id).delete()
    db.delete(student)
    db.commit()
    return {"success": True, "message": "طالب علم کا ریکارڈ کامیابی سے حذف کر دیا گیا۔"}

# ==========================================
# 2. COURSE & LESSON MANAGEMENT
# ==========================================

@router.get("/courses")
def list_courses(
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    courses = db.query(Course).order_by(Course.order_index.asc()).all()
    result = []
    for c in courses:
        result.append({
            "id": c.id,
            "title": c.title,
            "title_urdu": c.title_urdu,
            "slug": c.slug,
            "description": c.description,
            "category": c.category,
            "duration": c.duration,
            "thumbnail_url": c.thumbnail_url,
            "is_published": c.is_published,
            "lessons_count": len(c.lessons),
            "lessons": [
                {
                    "id": l.id,
                    "title": l.title,
                    "lesson_number": l.lesson_number,
                    "description": l.description,
                    "pdf_file": l.pdf_file,
                    "video_url": l.video_url,
                    "audio_url": l.audio_url,
                    "is_free_preview": l.is_free_preview
                }
                for l in c.lessons
            ]
        })
    return {"courses": result}

@router.post("/courses/create")
def create_course(
    title: str = Form(...),
    title_urdu: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    category: Optional[str] = Form("Islamic Studies"),
    duration: Optional[str] = Form("3 Months"),
    thumbnail_url: Optional[str] = Form(None),
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    clean_title = title.strip()
    slug_base = clean_title.lower().replace(" ", "-").replace("/", "-")
    slug = slug_base
    suffix = 1
    while db.query(Course).filter(Course.slug == slug).first():
        slug = f"{slug_base}-{suffix}"
        suffix += 1

    course = Course(
        title=clean_title,
        title_urdu=title_urdu.strip() if title_urdu else clean_title,
        slug=slug,
        description=description.strip() if description else "",
        category=category.strip() if category else "Islamic Studies",
        duration=duration.strip() if duration else "3 Months",
        thumbnail_url=thumbnail_url.strip() if thumbnail_url else "https://images.unsplash.com/photo-1609599006353-e629aaabfeae?auto=format&fit=crop&w=600&q=80",
        is_published=True,
        order_index=db.query(Course).count() + 1
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return {"success": True, "message": "نیا کورس کامیابی سے شامل کر دیا گیا۔", "course_id": course.id}

@router.post("/courses/{course_id}/edit")
def edit_course(
    course_id: int,
    title: str = Form(...),
    title_urdu: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    duration: Optional[str] = Form(None),
    thumbnail_url: Optional[str] = Form(None),
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="کورس نہیں ملا")

    course.title = title.strip()
    if title_urdu:
        course.title_urdu = title_urdu.strip()
    if description is not None:
        course.description = description.strip()
    if category:
        course.category = category.strip()
    if duration:
        course.duration = duration.strip()
    if thumbnail_url:
        course.thumbnail_url = thumbnail_url.strip()

    db.commit()
    return {"success": True, "message": "کورس کی معلومات اپڈیٹ ہو گئیں۔"}

@router.post("/courses/{course_id}/toggle-publish")
def toggle_course_publish(
    course_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="کورس نہیں ملا")

    course.is_published = not course.is_published
    db.commit()
    status_text = "شائع (Published)" if course.is_published else "غیر شائع (Unpublished)"
    return {"success": True, "message": f"کورس کا اسٹیٹس: {status_text}", "is_published": course.is_published}

@router.post("/courses/{course_id}/delete")
def delete_course(
    course_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="کورس نہیں ملا")

    db.delete(course)
    db.commit()
    return {"success": True, "message": "کورس اور اس کے تمام اسباق حذف کر دیے گئے۔"}

@router.post("/courses/{course_id}/lessons/create")
async def add_lesson(
    course_id: int,
    title: str = Form(...),
    lesson_number: int = Form(1),
    description: Optional[str] = Form(None),
    content_text: Optional[str] = Form(None),
    video_url: Optional[str] = Form(None),
    audio_url: Optional[str] = Form(None),
    is_free_preview: bool = Form(False),
    pdf_file: Optional[UploadFile] = File(None),
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="کورس نہیں ملا")

    saved_pdf_path = None
    if pdf_file and pdf_file.filename:
        ext = os.path.splitext(pdf_file.filename)[1].lower()
        if ext == ".pdf":
            filename = f"lesson_{course_id}_{uuid.uuid4().hex[:8]}.pdf"
            dest = os.path.join(settings.UPLOAD_DIR_LESSONS, filename)
            content = await pdf_file.read()
            with open(dest, "wb") as f:
                f.write(content)
            saved_pdf_path = f"/uploads/lessons/{filename}"

    lesson = Lesson(
        course_id=course_id,
        title=title.strip(),
        lesson_number=lesson_number,
        description=description.strip() if description else "",
        content_text=content_text.strip() if content_text else "",
        video_url=video_url.strip() if video_url else "",
        audio_url=audio_url.strip() if audio_url else "",
        pdf_file=saved_pdf_path,
        is_free_preview=is_free_preview
    )
    db.add(lesson)
    db.commit()
    db.refresh(lesson)
    return {"success": True, "message": "نیا سبق کامیابی سے شامل کر دیا گیا۔", "lesson_id": lesson.id}

@router.post("/lessons/{lesson_id}/delete")
def delete_lesson(
    lesson_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="سبق نہیں ملا")

    db.delete(lesson)
    db.commit()
    return {"success": True, "message": "سبق کامیابی سے حذف کر دیا گیا۔"}

# ==========================================
# 3. LIBRARY MANAGEMENT
# ==========================================

@router.get("/library")
def list_library_books(
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    books = db.query(Book).order_by(Book.uploaded_at.desc()).all()
    return {
        "books": [
            {
                "id": b.id,
                "title": b.title,
                "author": b.author,
                "category": b.category,
                "description": b.description,
                "cover_image": b.cover_image,
                "filename": b.filename,
                "file_path": b.file_path,
                "file_size": b.file_size,
                "is_published": b.is_published,
                "uploaded_at": b.uploaded_at.strftime("%Y-%m-%d") if b.uploaded_at else None
            }
            for b in books
        ]
    }

@router.post("/library/upload")
async def upload_library_book(
    title: str = Form(...),
    author: Optional[str] = Form("نامعلوم مصنف"),
    category: Optional[str] = Form("قرآنی علوم"),
    description: Optional[str] = Form(None),
    cover_image: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    saved_filename = "sample.pdf"
    file_path = "uploads/books/sample.pdf"
    file_size = 1024

    if file and file.filename:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext != ".pdf":
            raise HTTPException(status_code=400, detail="صرف پی ڈی ایف (PDF) فائلز اپلوڈ کی جا سکتی ہیں۔")

        unique_id = uuid.uuid4().hex[:10]
        safe_name = f"book_{unique_id}.pdf"
        dest_path = os.path.join(settings.UPLOAD_DIR, safe_name)

        content = await file.read()
        file_size = len(content)

        with open(dest_path, "wb") as f:
            f.write(content)

        saved_filename = file.filename
        file_path = f"uploads/books/{safe_name}"

    default_covers = {
        "قرآنی علوم": "https://images.unsplash.com/photo-1609599006353-e629aaabfeae?auto=format&fit=crop&w=400&q=80",
        "تجوید و قراءت": "https://images.unsplash.com/photo-1542816417-0983c9c9ad53?auto=format&fit=crop&w=400&q=80",
        "حدیث شریف": "https://images.unsplash.com/photo-1590076215667-875d4ef2d7ee?auto=format&fit=crop&w=400&q=80",
        "سنت و اذکار": "https://images.unsplash.com/photo-1579783902614-a3fb3927b675?auto=format&fit=crop&w=400&q=80",
        "فقہ و اسلامی عقائد": "https://images.unsplash.com/photo-1564769625905-50e93615e769?auto=format&fit=crop&w=400&q=80"
    }
    cat = category.strip() if category else "قرآنی علوم"
    cover = cover_image.strip() if cover_image and cover_image.strip() else default_covers.get(cat, default_covers["قرآنی علوم"])

    book = Book(
        title=title.strip(),
        author=author.strip() if author else "نامعلوم مصنف",
        category=cat,
        description=description.strip() if description else "",
        cover_image=cover,
        filename=saved_filename,
        file_path=file_path,
        file_size=file_size,
        total_pages=1,
        is_published=True,
        uploaded_at=datetime.utcnow()
    )
    db.add(book)
    db.commit()
    db.refresh(book)

    return {"success": True, "message": "کتاب کامیابی سے لائبریری میں شامل ہو گئی۔", "book_id": book.id}

@router.post("/library/{book_id}/edit")
def edit_library_book(
    book_id: int,
    title: str = Form(...),
    author: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    cover_image: Optional[str] = Form(None),
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="کتاب نہیں ملی")

    book.title = title.strip()
    if author:
        book.author = author.strip()
    if category:
        book.category = category.strip()
    if description is not None:
        book.description = description.strip()
    if cover_image:
        book.cover_image = cover_image.strip()

    db.commit()
    return {"success": True, "message": "کتاب کی معلومات اپڈیٹ ہو گئیں۔"}

@router.post("/library/{book_id}/toggle-publish")
def toggle_book_publish(
    book_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="کتاب نہیں ملی")

    book.is_published = not book.is_published
    db.commit()
    return {"success": True, "message": "کتاب کا اسٹیٹس تبدیل ہو گیا۔", "is_published": book.is_published}

@router.post("/library/{book_id}/delete")
def delete_library_book(
    book_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="کتاب نہیں ملی")

    if os.path.exists(book.file_path):
        try:
            os.remove(book.file_path)
        except Exception:
            pass

    db.delete(book)
    db.commit()
    return {"success": True, "message": "کتاب کامیابی سے حذف کر دی گئی۔"}

# ==========================================
# 4. CONTACT SETTINGS
# ==========================================

@router.get("/settings/contact")
def get_contact_settings(db: Session = Depends(get_db)):
    contact = db.query(ContactSetting).first()
    if not contact:
        contact = ContactSetting()
        db.add(contact)
        db.commit()
        db.refresh(contact)
    return {
        "institute_name": contact.institute_name,
        "teacher_name": contact.teacher_name,
        "whatsapp_number": contact.whatsapp_number,
        "phone_number": contact.phone_number,
        "email": contact.email,
        "address": contact.address,
        "welcome_quote": contact.welcome_quote
    }

@router.post("/settings/contact")
def update_contact_settings(
    institute_name: Optional[str] = Form(None),
    teacher_name: Optional[str] = Form(None),
    whatsapp_number: Optional[str] = Form(None),
    phone_number: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    welcome_quote: Optional[str] = Form(None),
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    contact = db.query(ContactSetting).first()
    if not contact:
        contact = ContactSetting()
        db.add(contact)

    if institute_name:
        contact.institute_name = institute_name.strip()
    if teacher_name:
        contact.teacher_name = teacher_name.strip()
    if whatsapp_number:
        contact.whatsapp_number = whatsapp_number.strip()
    if phone_number:
        contact.phone_number = phone_number.strip()
    if email:
        contact.email = email.strip()
    if address:
        contact.address = address.strip()
    if welcome_quote:
        contact.welcome_quote = welcome_quote.strip()

    db.commit()
    return {"success": True, "message": "رابطہ کی ترتیبات کامیابی سے محفوظ ہو گئیں۔"}

# ==========================================
# 5. CLASSROOM MANAGEMENT
# ==========================================

@router.post("/classroom/toggle-live")
async def toggle_classroom_live(
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    room = db.query(Classroom).filter(Classroom.permanent_id == settings.PERMANENT_CLASS_ID).first()
    if not room:
        raise HTTPException(status_code=404, detail="کلاس روم نہیں ملا")

    room.is_live = not room.is_live
    if room.is_live:
        room.current_session_id = f"sess_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        msg = "کلاس روم لائیو کر دیا گیا ہے۔ طلبہ اب شامل ہو سکتے ہیں۔"
        # Broadcast notification
        notice = Notification(
            title="کلاس لائیو شروع ہو گئی ہے!",
            message="استاد محترم نے لائیو کلاس روم شروع کر دیا ہے۔ فوراً کلاس میں شامل ہوں۔",
            type="live"
        )
        db.add(notice)
    else:
        msg = "کلاس روم ختم کر دیا گیا ہے۔"
        await classroom_manager.broadcast_to_students({
            "type": "class_ended",
            "message": "استاد محترم نے کلاس کا وقت مکمل ہونے پر سیشن ختم کر دیا ہے۔"
        })

    db.commit()
    return {"success": True, "message": msg, "is_live": room.is_live}

@router.post("/classroom/zoom-settings")
def update_zoom_settings(
    zoom_link: Optional[str] = Form(None),
    zoom_meeting_id: Optional[str] = Form(None),
    zoom_password: Optional[str] = Form(None),
    zoom_topic: Optional[str] = Form(None),
    zoom_instructions: Optional[str] = Form(None),
    is_zoom_live: Optional[str] = Form(None),
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    room = db.query(Classroom).filter(Classroom.permanent_id == settings.PERMANENT_CLASS_ID).first()
    if not room:
        raise HTTPException(status_code=404, detail="کلاس روم نہیں ملا")

    if zoom_link is not None:
        room.zoom_link = zoom_link.strip()
    if zoom_meeting_id is not None:
        room.zoom_meeting_id = zoom_meeting_id.strip()
    if zoom_password is not None:
        room.zoom_password = zoom_password.strip()
    if zoom_topic is not None:
        room.zoom_topic = zoom_topic.strip()
    if zoom_instructions is not None:
        room.zoom_instructions = zoom_instructions.strip()
    if is_zoom_live is not None:
        room.is_zoom_live = (is_zoom_live.lower() in ("true", "1", "yes", "on"))

    db.commit()
    return {"success": True, "message": "زووم آن لائن کلاس کی معلومات کامیابی سے محفوظ ہو گئیں۔"}

@router.post("/classroom/toggle-zoom-live")
def toggle_zoom_live(
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    room = db.query(Classroom).filter(Classroom.permanent_id == settings.PERMANENT_CLASS_ID).first()
    if not room:
        raise HTTPException(status_code=404, detail="کلاس روم نہیں ملا")

    room.is_zoom_live = not room.is_zoom_live
    if room.is_zoom_live:
        notice = Notification(
            title="آن لائن زووم کلاس شروع ہو گئی ہے!",
            message=f"استاد محترم نے آن لائن کلاس شروع کر دی ہے۔ میٹنگ آئی ڈی: {room.zoom_meeting_id or 'دستیاب ہے'}",
            type="live"
        )
        db.add(notice)

    db.commit()
    status_text = "لائیو کر دی گئی ہے" if room.is_zoom_live else "آف لائن کر دی گئی ہے"
    return {"success": True, "message": f"زووم کلاس اب {status_text}۔", "is_zoom_live": room.is_zoom_live}

# ==========================================
# 6. DAILY VIDEOS MANAGEMENT (REQUIREMENT 4)
# ==========================================

def extract_youtube_info(url: str):
    if not url:
        return {"is_youtube": False, "youtube_id": None, "thumbnail": None}
    match = re.search(r'(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/ ]{11})', url)
    if match:
        yt_id = match.group(1)
        return {
            "is_youtube": True,
            "youtube_id": yt_id,
            "thumbnail": f"https://img.youtube.com/vi/{yt_id}/hqdefault.jpg"
        }
    return {"is_youtube": False, "youtube_id": None, "thumbnail": None}

@router.get("/daily-videos")
def list_daily_videos(
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    videos = db.query(DailyVideo).order_by(DailyVideo.date_posted.desc(), DailyVideo.id.desc()).all()
    return {
        "total": len(videos),
        "videos": [
            {
                "id": v.id,
                "title": v.title,
                "description": v.description,
                "video_type": v.video_type,
                "video_url": v.video_url,
                "thumbnail_url": v.thumbnail_url,
                "category": v.category,
                "duration": v.duration,
                "is_published": v.is_published,
                "date_posted": v.date_posted.strftime("%Y-%m-%d") if v.date_posted else "",
                "created_at": v.created_at.strftime("%Y-%m-%d %H:%M") if v.created_at else ""
            }
            for v in videos
        ]
    }

@router.post("/daily-videos")
async def create_daily_video(
    title: str = Form(...),
    description: Optional[str] = Form(None),
    category: Optional[str] = Form("روزانہ کا سبق"),
    video_type: Optional[str] = Form("url"),
    video_url: Optional[str] = Form(None),
    duration: Optional[str] = Form(""),
    video_file: Optional[UploadFile] = File(None),
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    final_video_url = ""
    final_thumbnail_url = "https://images.unsplash.com/photo-1609599006353-e629aaabfeae?auto=format&fit=crop&w=600&q=80"
    v_type = video_type or "url"

    if v_type == "file" and video_file and video_file.filename:
        # File upload handling
        ext = os.path.splitext(video_file.filename)[1].lower()
        if ext not in [".mp4", ".webm", ".mkv", ".mov", ".m4v"]:
            raise HTTPException(status_code=400, detail="صرف ویڈیو فائلیں (mp4, webm, mov, mkv) اپلوڈ کی جا سکتی ہیں۔")
        
        os.makedirs("uploads/videos", exist_ok=True)
        unique_name = f"video_{uuid.uuid4().hex[:10]}{ext}"
        save_path = os.path.join("uploads", "videos", unique_name)
        
        content = await video_file.read()
        with open(save_path, "wb") as f:
            f.write(content)
        
        final_video_url = f"/uploads/videos/{unique_name}"
        final_thumbnail_url = "/static/images/app_logo.svg"
    else:
        # URL handling
        v_type = "url"
        if not video_url or not video_url.strip():
            raise HTTPException(status_code=400, detail="براہ کرم ویڈیو کا درست لنک فراہم کریں۔")
        final_video_url = video_url.strip()
        yt_info = extract_youtube_info(final_video_url)
        if yt_info["is_youtube"] and yt_info["thumbnail"]:
            final_thumbnail_url = yt_info["thumbnail"]

    video = DailyVideo(
        title=title.strip(),
        description=description.strip() if description else "",
        category=category.strip() if category else "روزانہ کا سبق",
        video_type=v_type,
        video_url=final_video_url,
        thumbnail_url=final_thumbnail_url,
        duration=duration.strip() if duration else "",
        is_published=True,
        date_posted=datetime.utcnow(),
        created_at=datetime.utcnow()
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    return {"success": True, "message": "روزانہ کی ویڈیو کامیابی سے شامل کر دی گئی۔", "video_id": video.id}

@router.post("/daily-videos/{video_id}/delete")
def delete_daily_video(
    video_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    video = db.query(DailyVideo).filter(DailyVideo.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="ویڈیو نہیں ملی")

    # If it was an uploaded local file, remove it from disk
    if video.video_type == "file" and video.video_url:
        clean_path = video.video_url.lstrip("/")
        if os.path.exists(clean_path):
            try:
                os.remove(clean_path)
            except Exception:
                pass

    db.delete(video)
    db.commit()
    return {"success": True, "message": "ویڈیو کامیابی سے حذف (Delete) کر دی گئی۔"}

@router.post("/daily-videos/{video_id}/toggle-publish")
def toggle_daily_video_publish(
    video_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    video = db.query(DailyVideo).filter(DailyVideo.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="ویڈیو نہیں ملی")

    video.is_published = not video.is_published
    db.commit()
    return {"success": True, "message": "ویڈیو کا اسٹیٹس تبدیل ہو گیا۔", "is_published": video.is_published}
