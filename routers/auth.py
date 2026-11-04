from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.orm import Session
from database import get_db
from models.teacher import Teacher
from schemas.teacher import TeacherCreate, TeacherLogin, TeacherUpdate, TeacherResponse
from services.auth_service import AuthService
from typing import Dict, Any

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

def get_current_teacher(request: Request, db: Session = Depends(get_db)) -> Teacher:
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    if not token:
        token = request.cookies.get("teacher_access_token")
    
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated as teacher")
    
    teacher = AuthService.get_current_teacher_from_token(token, db)
    if not teacher:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")
    return teacher

@router.get("/setup-status")
def check_setup_status(db: Session = Depends(get_db)):
    teacher_count = db.query(Teacher).count()
    return {"is_setup_done": teacher_count > 0}

@router.post("/setup", response_model=TeacherResponse)
def setup_first_teacher(teacher_in: TeacherCreate, db: Session = Depends(get_db)):
    teacher_count = db.query(Teacher).count()
    if teacher_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Teacher account is already configured. Multiple teacher accounts are strictly not allowed."
        )
    
    hashed_password = AuthService.get_password_hash(teacher_in.password)
    new_teacher = Teacher(
        full_name=teacher_in.full_name.strip(),
        username=teacher_in.username.strip().lower(),
        email=teacher_in.email.strip().lower(),
        phone_number=teacher_in.phone_number.strip() if teacher_in.phone_number else None,
        password_hash=hashed_password
    )
    db.add(new_teacher)
    db.commit()
    db.refresh(new_teacher)
    return new_teacher

@router.post("/login")
def login_teacher(login_in: TeacherLogin, response: Response, db: Session = Depends(get_db)):
    user_query = login_in.username_or_email.strip().lower()
    teacher = db.query(Teacher).filter(
        (Teacher.username == user_query) | (Teacher.email == user_query)
    ).first()

    if not teacher or not AuthService.verify_password(login_in.password, teacher.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password."
        )

    token_data = {
        "sub": str(teacher.id),
        "username": teacher.username,
        "role": "teacher"
    }
    access_token = AuthService.create_access_token(token_data)

    # Set secure HTTP-only cookie
    response.set_cookie(
        key="teacher_access_token",
        value=access_token,
        httponly=True,
        max_age=86400,
        samesite="lax"
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "teacher": {
            "id": teacher.id,
            "full_name": teacher.full_name,
            "username": teacher.username,
            "email": teacher.email
        }
    }

@router.post("/logout")
def logout_teacher(response: Response):
    response.delete_cookie(key="teacher_access_token")
    return {"message": "Successfully logged out"}

@router.get("/me", response_model=TeacherResponse)
def get_me(teacher: Teacher = Depends(get_current_teacher)):
    return teacher

@router.put("/profile", response_model=TeacherResponse)
def update_profile(
    update_in: TeacherUpdate,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    if update_in.full_name:
        teacher.full_name = update_in.full_name.strip()
    if update_in.email:
        existing = db.query(Teacher).filter(Teacher.email == update_in.email.strip().lower(), Teacher.id != teacher.id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")
        teacher.email = update_in.email.strip().lower()
    if update_in.phone_number is not None:
        teacher.phone_number = update_in.phone_number.strip()
    
    if update_in.new_password:
        if not update_in.current_password or not AuthService.verify_password(update_in.current_password, teacher.password_hash):
            raise HTTPException(status_code=400, detail="Current password incorrect")
        teacher.password_hash = AuthService.get_password_hash(update_in.new_password)

    db.commit()
    db.refresh(teacher)
    return teacher
