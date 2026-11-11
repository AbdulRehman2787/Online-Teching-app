import os
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models.teacher import Teacher
from models.classroom import Classroom
from models.book import Book
from models.student import Student
from models.course import Course, Lesson
from models.student_progress import StudentProgress
from models.contact_setting import ContactSetting
from models.notification import Notification
from models.daily_video import DailyVideo
from services.auth_service import AuthService
from services.classroom_service import classroom_manager
from config import settings

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory="templates")

def get_auth_context(request: Request, db: Session):
    """Helper to get current teacher and/or student for headers & navigation."""
    teacher = None
    student = None

    teacher_token = request.cookies.get("teacher_access_token")
    if teacher_token:
        teacher = AuthService.get_current_teacher_from_token(teacher_token, db)

    student_token = request.cookies.get("student_access_token")
    if student_token:
        student = AuthService.get_current_student_from_token(student_token, db)

    contact = db.query(ContactSetting).first()
    room = db.query(Classroom).filter(Classroom.permanent_id == settings.PERMANENT_CLASS_ID).first()

    return {
        "teacher": teacher,
        "student": student,
        "contact": contact,
        "classroom": room,
        "app_name": settings.APP_NAME
    }

# ==========================================
# PUBLIC AREA (REQUIREMENTS 1, 2, 8, 9, 10, 14, 15, 16)
# ==========================================

@router.get("/", response_class=HTMLResponse)
def home_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_auth_context(request, db)
    courses = db.query(Course).filter(Course.is_published == True).order_by(Course.order_index.asc()).all()
    books = db.query(Book).filter(Book.is_published == True).order_by(Book.uploaded_at.desc()).limit(6).all()
    notifications = db.query(Notification).order_by(Notification.created_at.desc()).limit(3).all()
    daily_videos = db.query(DailyVideo).filter(DailyVideo.is_published == True).order_by(DailyVideo.date_posted.desc()).limit(4).all()

    ctx.update({
        "courses": courses,
        "books": books,
        "notifications": notifications,
        "daily_videos": daily_videos
    })
    return templates.TemplateResponse(request=request, name="home.html", context=ctx)

@router.get("/online-class", response_class=HTMLResponse)
def online_class_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_auth_context(request, db)
    return templates.TemplateResponse(request=request, name="online_class.html", context=ctx)

@router.get("/daily-videos", response_class=HTMLResponse)
def daily_videos_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_auth_context(request, db)
    videos = db.query(DailyVideo).filter(DailyVideo.is_published == True).order_by(DailyVideo.date_posted.desc()).all()
    ctx.update({"videos": videos})
    return templates.TemplateResponse(request=request, name="daily_videos.html", context=ctx)

@router.get("/join", response_class=HTMLResponse)
def join_admission_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_auth_context(request, db)
    courses = db.query(Course).filter(Course.is_published == True).all()
    ctx.update({"courses": courses})
    return templates.TemplateResponse(request=request, name="student_join.html", context=ctx)

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_auth_context(request, db)
    if ctx["teacher"]:
        return RedirectResponse(url="/admin/dashboard")
    if ctx["student"]:
        return RedirectResponse(url="/student/dashboard")
    return templates.TemplateResponse(request=request, name="login.html", context=ctx)

@router.get("/courses", response_class=HTMLResponse)
def courses_catalog_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_auth_context(request, db)
    courses = db.query(Course).filter(Course.is_published == True).order_by(Course.order_index.asc()).all()
    ctx.update({"courses": courses})
    return templates.TemplateResponse(request=request, name="courses.html", context=ctx)

@router.get("/courses/{slug}", response_class=HTMLResponse)
def course_detail_page(slug: str, request: Request, db: Session = Depends(get_db)):
    ctx = get_auth_context(request, db)
    course = db.query(Course).filter(Course.slug == slug, Course.is_published == True).first()
    if not course:
        return RedirectResponse(url="/courses")
    ctx.update({"course": course})
    return templates.TemplateResponse(request=request, name="course_detail.html", context=ctx)

@router.get("/quran", response_class=HTMLResponse)
def quran_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_auth_context(request, db)
    return templates.TemplateResponse(request=request, name="quran.html", context=ctx)

@router.get("/qaida", response_class=HTMLResponse)
def qaida_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_auth_context(request, db)
    return templates.TemplateResponse(request=request, name="qaida.html", context=ctx)

@router.get("/library", response_class=HTMLResponse)
def library_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_auth_context(request, db)
    books = db.query(Book).filter(Book.is_published == True).order_by(Book.uploaded_at.desc()).all()
    ctx.update({"books": books})
    return templates.TemplateResponse(request=request, name="library.html", context=ctx)

@router.get("/contact", response_class=HTMLResponse)
def contact_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_auth_context(request, db)
    return templates.TemplateResponse(request=request, name="contact.html", context=ctx)

# ==========================================
# STUDENT PRIVATE AREA (REQUIREMENTS 4, 5, 13, 15)
# ==========================================

@router.get("/student/dashboard", response_class=HTMLResponse)
def student_dashboard(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("student_access_token")
    if not token:
        return RedirectResponse(url="/login")

    student = AuthService.get_current_student_from_token(token, db)
    if not student:
        return RedirectResponse(url="/login")

    ctx = get_auth_context(request, db)
    courses = db.query(Course).filter(Course.is_published == True).all()

    # Progress Calculation
    total_lessons = db.query(Lesson).count()
    completed_lessons = db.query(StudentProgress).filter(
        StudentProgress.student_id == student.id,
        StudentProgress.is_completed == True
    ).count()

    progress_pct = int((completed_lessons / total_lessons * 100)) if total_lessons > 0 else 0
    notifications = db.query(Notification).order_by(Notification.created_at.desc()).limit(5).all()

    ctx.update({
        "student": student,
        "courses": courses,
        "total_lessons": total_lessons,
        "completed_lessons": completed_lessons,
        "progress_pct": progress_pct,
        "notifications": notifications
    })
    return templates.TemplateResponse(request=request, name="student_dashboard.html", context=ctx)

@router.get("/student/courses", response_class=HTMLResponse)
def student_courses(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("student_access_token")
    if not token:
        return RedirectResponse(url="/login")
    student = AuthService.get_current_student_from_token(token, db)
    if not student:
        return RedirectResponse(url="/login")

    ctx = get_auth_context(request, db)
    courses = db.query(Course).filter(Course.is_published == True).order_by(Course.order_index.asc()).all()
    completed_lesson_ids = [
        p.lesson_id for p in db.query(StudentProgress).filter(
            StudentProgress.student_id == student.id,
            StudentProgress.is_completed == True
        ).all()
    ]

    ctx.update({
        "student": student,
        "courses": courses,
        "completed_lesson_ids": completed_lesson_ids
    })
    return templates.TemplateResponse(request=request, name="student_courses.html", context=ctx)

@router.get("/student/lesson/{lesson_id}", response_class=HTMLResponse)
def student_lesson_view(lesson_id: int, request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("student_access_token")
    if not token:
        return RedirectResponse(url="/login")
    student = AuthService.get_current_student_from_token(token, db)
    if not student:
        return RedirectResponse(url="/login")

    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        return RedirectResponse(url="/student/courses")

    progress = db.query(StudentProgress).filter(
        StudentProgress.student_id == student.id,
        StudentProgress.lesson_id == lesson_id
    ).first()

    ctx = get_auth_context(request, db)
    ctx.update({
        "student": student,
        "lesson": lesson,
        "course": lesson.course,
        "is_completed": progress.is_completed if progress else False
    })
    return templates.TemplateResponse(request=request, name="student_lesson.html", context=ctx)

@router.get("/student/classroom", response_class=HTMLResponse)
def student_classroom_view(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("student_access_token")
    if not token:
        return RedirectResponse(url="/login")
    student = AuthService.get_current_student_from_token(token, db)
    if not student:
        return RedirectResponse(url="/login")

    ctx = get_auth_context(request, db)
    return templates.TemplateResponse(request=request, name="student_classroom.html", context=ctx)

@router.get("/student/profile", response_class=HTMLResponse)
def student_profile_view(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("student_access_token")
    if not token:
        return RedirectResponse(url="/login")
    student = AuthService.get_current_student_from_token(token, db)
    if not student:
        return RedirectResponse(url="/login")

    ctx = get_auth_context(request, db)
    return templates.TemplateResponse(request=request, name="student_profile.html", context=ctx)

@router.get("/student/logout")
def student_logout_view():
    resp = RedirectResponse(url="/", status_code=302)
    resp.delete_cookie(key="student_access_token")
    return resp

# ==========================================
# ADMIN PRIVATE AREA (REQUIREMENTS 6, 7, 8, 9, 10, 11, 12, 15)
# ==========================================

@router.get("/admin", response_class=HTMLResponse)
@router.get("/admin/dashboard", response_class=HTMLResponse)
def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("teacher_access_token")
    if not token:
        return RedirectResponse(url="/login?role=admin")
    teacher = AuthService.get_current_teacher_from_token(token, db)
    if not teacher:
        return RedirectResponse(url="/login?role=admin")

    ctx = get_auth_context(request, db)

    # Statistics
    total_students = db.query(Student).count()
    pending_students = db.query(Student).filter(Student.status == "pending").count()
    approved_students = db.query(Student).filter(Student.status == "approved").count()
    active_students = db.query(Student).filter(Student.status == "approved", Student.is_active == True).count()
    total_courses = db.query(Course).count()
    total_books = db.query(Book).count()
    total_daily_videos = db.query(DailyVideo).count()
    recent_students = db.query(Student).order_by(Student.created_at.desc()).limit(8).all()

    ctx.update({
        "teacher": teacher,
        "stats": {
            "total_students": total_students,
            "pending_students": pending_students,
            "approved_students": approved_students,
            "active_students": active_students,
            "total_courses": total_courses,
            "total_books": total_books,
            "total_daily_videos": total_daily_videos,
            "is_live": ctx["classroom"].is_live if ctx["classroom"] else False,
            "student_count": classroom_manager.get_student_count()
        },
        "recent_students": recent_students
    })
    return templates.TemplateResponse(request=request, name="admin/dashboard.html", context=ctx)

@router.get("/admin/students", response_class=HTMLResponse)
def admin_students_view(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("teacher_access_token")
    if not token:
        return RedirectResponse(url="/login?role=admin")
    teacher = AuthService.get_current_teacher_from_token(token, db)
    if not teacher:
        return RedirectResponse(url="/login?role=admin")

    ctx = get_auth_context(request, db)
    students = db.query(Student).order_by(Student.created_at.desc()).all()
    courses = db.query(Course).all()
    ctx.update({
        "students": students,
        "courses": courses,
        "pending_count": db.query(Student).filter(Student.status == "pending").count()
    })
    return templates.TemplateResponse(request=request, name="admin/students.html", context=ctx)

@router.get("/admin/courses", response_class=HTMLResponse)
def admin_courses_view(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("teacher_access_token")
    if not token:
        return RedirectResponse(url="/login?role=admin")
    teacher = AuthService.get_current_teacher_from_token(token, db)
    if not teacher:
        return RedirectResponse(url="/login?role=admin")

    ctx = get_auth_context(request, db)
    courses = db.query(Course).order_by(Course.order_index.asc()).all()
    ctx.update({"courses": courses})
    return templates.TemplateResponse(request=request, name="admin/courses.html", context=ctx)

@router.get("/admin/library", response_class=HTMLResponse)
def admin_library_view(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("teacher_access_token")
    if not token:
        return RedirectResponse(url="/login?role=admin")
    teacher = AuthService.get_current_teacher_from_token(token, db)
    if not teacher:
        return RedirectResponse(url="/login?role=admin")

    ctx = get_auth_context(request, db)
    books = db.query(Book).order_by(Book.uploaded_at.desc()).all()
    ctx.update({"books": books})
    return templates.TemplateResponse(request=request, name="admin/library.html", context=ctx)

@router.get("/admin/classroom", response_class=HTMLResponse)
def admin_classroom_view(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("teacher_access_token")
    if not token:
        return RedirectResponse(url="/login?role=admin")
    teacher = AuthService.get_current_teacher_from_token(token, db)
    if not teacher:
        return RedirectResponse(url="/login?role=admin")

    ctx = get_auth_context(request, db)
    books = db.query(Book).filter(Book.is_published == True).all()
    ctx.update({
        "books": books,
        "participants": classroom_manager.get_active_participants()
    })
    return templates.TemplateResponse(request=request, name="admin/classroom.html", context=ctx)

@router.get("/admin/settings/contact", response_class=HTMLResponse)
def admin_contact_settings_view(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("teacher_access_token")
    if not token:
        return RedirectResponse(url="/login?role=admin")
    teacher = AuthService.get_current_teacher_from_token(token, db)
    if not teacher:
        return RedirectResponse(url="/login?role=admin")

    ctx = get_auth_context(request, db)
    return templates.TemplateResponse(request=request, name="admin/contact_settings.html", context=ctx)

@router.get("/admin/daily-videos", response_class=HTMLResponse)
def admin_daily_videos_view(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("teacher_access_token")
    if not token:
        return RedirectResponse(url="/login?role=admin")
    teacher = AuthService.get_current_teacher_from_token(token, db)
    if not teacher:
        return RedirectResponse(url="/login?role=admin")

    ctx = get_auth_context(request, db)
    videos = db.query(DailyVideo).order_by(DailyVideo.date_posted.desc(), DailyVideo.id.desc()).all()
    ctx.update({"videos": videos})
    return templates.TemplateResponse(request=request, name="admin/daily_videos.html", context=ctx)

@router.get("/admin/logout")
def admin_logout_view():
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie(key="teacher_access_token")
    return resp

# Backward compatibility routes
@router.get("/dashboard")
def legacy_dashboard():
    return RedirectResponse(url="/admin/dashboard")

@router.get("/classroom/teacher")
def legacy_teacher_classroom(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("teacher_access_token")
    if not token:
        return RedirectResponse(url="/login?role=admin")
    teacher = AuthService.get_current_teacher_from_token(token, db)
    if not teacher:
        return RedirectResponse(url="/login?role=admin")

    room = db.query(Classroom).filter(Classroom.permanent_id == settings.PERMANENT_CLASS_ID).first()
    books = db.query(Book).order_by(Book.uploaded_at.desc()).all()

    return templates.TemplateResponse(request=request, name="teacher_classroom.html", context={
        "teacher": teacher,
        "classroom": room,
        "books": books,
        "app_name": settings.APP_NAME
    })
