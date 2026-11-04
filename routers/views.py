import os
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from models.teacher import Teacher
from models.classroom import Classroom
from models.book import Book
from services.auth_service import AuthService
from config import settings

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
def index_redirect(request: Request, db: Session = Depends(get_db)):
    teacher_exists = db.query(Teacher).count() > 0
    if not teacher_exists:
        return RedirectResponse(url="/setup")
    
    # Check if teacher cookie exists
    token = request.cookies.get("teacher_access_token")
    if token:
        teacher = AuthService.get_current_teacher_from_token(token, db)
        if teacher:
            return RedirectResponse(url="/dashboard")

    return RedirectResponse(url="/login")

@router.get("/setup", response_class=HTMLResponse)
def setup_page(request: Request, db: Session = Depends(get_db)):
    teacher_exists = db.query(Teacher).count() > 0
    if teacher_exists:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(request=request, name="setup.html", context={"app_name": settings.APP_NAME})

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    teacher_exists = db.query(Teacher).count() > 0
    if not teacher_exists:
        return RedirectResponse(url="/setup")
    return templates.TemplateResponse(request=request, name="login.html", context={"app_name": settings.APP_NAME})

@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("teacher_access_token")
    if not token:
        return RedirectResponse(url="/login")
    
    teacher = AuthService.get_current_teacher_from_token(token, db)
    if not teacher:
        return RedirectResponse(url="/login")

    room = db.query(Classroom).filter(Classroom.permanent_id == settings.PERMANENT_CLASS_ID).first()
    books = db.query(Book).order_by(Book.uploaded_at.desc()).all()

    return templates.TemplateResponse(request=request, name="dashboard.html", context={
        "teacher": teacher,
        "classroom": room,
        "books": books,
        "app_name": settings.APP_NAME
    })

@router.get("/classroom/teacher", response_class=HTMLResponse)
def teacher_classroom_view(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("teacher_access_token")
    if not token:
        return RedirectResponse(url="/login")
    
    teacher = AuthService.get_current_teacher_from_token(token, db)
    if not teacher:
        return RedirectResponse(url="/login")

    room = db.query(Classroom).filter(Classroom.permanent_id == settings.PERMANENT_CLASS_ID).first()
    books = db.query(Book).order_by(Book.uploaded_at.desc()).all()

    return templates.TemplateResponse(request=request, name="teacher_classroom.html", context={
        "teacher": teacher,
        "classroom": room,
        "books": books,
        "app_name": settings.APP_NAME
    })

@router.get("/join", response_class=HTMLResponse)
def student_join_view(request: Request, db: Session = Depends(get_db)):
    room = db.query(Classroom).filter(Classroom.permanent_id == settings.PERMANENT_CLASS_ID).first()
    return templates.TemplateResponse(request=request, name="student_join.html", context={
        "classroom": room,
        "app_name": settings.APP_NAME
    })

@router.get("/classroom/student", response_class=HTMLResponse)
def student_classroom_view(request: Request, db: Session = Depends(get_db)):
    room = db.query(Classroom).filter(Classroom.permanent_id == settings.PERMANENT_CLASS_ID).first()
    return templates.TemplateResponse(request=request, name="student_classroom.html", context={
        "classroom": room,
        "app_name": settings.APP_NAME
    })

@router.get("/books/file/{book_id}")
def serve_book_pdf(book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book or not os.path.exists(book.file_path):
        raise HTTPException(status_code=404, detail="Book file not found")
    return FileResponse(
        path=book.file_path,
        media_type="application/pdf",
        filename=book.filename
    )
