import re
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.orm import Session
from database import get_db
from models.student import Student
from models.course import Course, Lesson
from models.student_progress import StudentProgress
from schemas.student import StudentRegisterRequest, StudentLoginRequest
from services.auth_service import AuthService

router = APIRouter(prefix="/api/students", tags=["Student Authentication & Admission"])

def get_current_student(request: Request, db: Session = Depends(get_db)) -> Student:
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    if not token:
        token = request.cookies.get("student_access_token")

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="طالب علم لاگ ان نہیں ہے (Not authenticated as student)")

    student = AuthService.get_current_student_from_token(token, db)
    if not student:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="سیشن ختم ہو چکا ہے، دوبارہ لاگ ان کریں (Invalid or expired session)")
    return student

@router.post("/register")
def register_student(req: StudentRegisterRequest, db: Session = Depends(get_db)):
    # Clean inputs
    name = req.student_name.strip()
    parent_name = req.parent_name.strip()
    whatsapp = re.sub(r'[^0-9+]', '', req.whatsapp_number.strip())
    country = req.country.strip() if req.country else "Pakistan"
    email = req.email.strip().lower() if req.email else None
    course = req.requested_course.strip() if req.requested_course else "نورانی قاعدہ مع تجوید"

    # Check if student with same WhatsApp already applied and is pending/approved
    existing = db.query(Student).filter(Student.whatsapp_number == whatsapp).first()
    if existing:
        if existing.status == "pending":
            return {
                "success": True,
                "message": "آپ کی درخواست پہلے سے موصول ہو چکی ہے اور ایڈمن کی زیرِ غور ہے۔ جلد آپ سے واٹس ایپ پر رابطہ کیا جائے گا۔",
                "status": "pending",
                "student_id": existing.student_id
            }
        elif existing.status == "approved":
            return {
                "success": True,
                "message": f"آپ کا داخلہ پہلے ہی منظور ہو چکا ہے! آپ کا اسٹوڈنٹ آئی ڈی: {existing.student_id} ہے۔ براہ کرم لاگ ان کریں۔",
                "status": "approved",
                "student_id": existing.student_id
            }

    # Generate student ID e.g. STU-1001
    new_student_id = AuthService.generate_student_id(db)

    # Initial default password (can be updated upon approval)
    initial_temp_pass = AuthService.generate_simple_password()
    hashed_pass = AuthService.get_password_hash(initial_temp_pass)

    new_student = Student(
        student_id=new_student_id,
        full_name=name,
        parent_name=parent_name,
        whatsapp_number=whatsapp,
        country=country,
        age=req.age,
        email=email,
        requested_course=course,
        status="pending",
        is_active=True,
        password_hash=hashed_pass,
        temp_password=initial_temp_pass,
        created_at=datetime.utcnow()
    )

    db.add(new_student)
    db.commit()
    db.refresh(new_student)

    return {
        "success": True,
        "message": "آپ کی درخواست موصول ہو گئی ہے۔ ایڈمن کی منظوری کے بعد آپ کلاس میں شامل ہو سکیں گے۔",
        "student_id": new_student.student_id,
        "whatsapp_number": new_student.whatsapp_number
    }

@router.post("/login")
def login_student(login_data: StudentLoginRequest, response: Response, db: Session = Depends(get_db)):
    ident = login_data.login_identifier.strip()
    clean_phone = re.sub(r'[^0-9+]', '', ident)

    # Find student by student_id or whatsapp_number or email
    student = db.query(Student).filter(
        (Student.student_id == ident.upper()) |
        (Student.whatsapp_number == clean_phone) |
        (Student.whatsapp_number == ident) |
        (Student.email == ident.lower())
    ).first()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="طالب علم کا ریکارڈ نہیں ملا۔ براہ کرم اسٹوڈنٹ آئی ڈی یا واٹس ایپ نمبر درست درج کریں۔"
        )

    # Check status
    if student.status == "pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="آپ کی درخواست ابھی ایڈمن کی زیرِ منظوری ہے۔ منظوری کے بعد آپ لاگ ان کر سکیں گے۔"
        )
    elif student.status == "rejected":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="معذرت! آپ کی درخواست منظور نہیں ہو سکی۔ برائے رابطہ ایڈمن سے رابطہ کریں۔"
        )
    elif student.status == "blocked" or not student.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="آپ کا اکاؤنٹ غیر فعال (Blocked) ہے۔ براہ کرم استاد محترم سے رابطہ کریں۔"
        )

    # Verify password
    if not AuthService.verify_password(login_data.password.strip(), student.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="پاسورڈ غلط ہے۔ اگر آپ پاسورڈ بھول گئے ہیں تو ایڈمن سے رابطہ کریں۔"
        )

    student.last_login = datetime.utcnow()
    db.commit()

    token_data = {
        "sub": str(student.id),
        "student_id": student.student_id,
        "name": student.full_name,
        "role": "student"
    }
    access_token = AuthService.create_access_token(token_data)

    response.set_cookie(
        key="student_access_token",
        value=access_token,
        httponly=True,
        max_age=86400 * 7, # 7 days
        samesite="lax"
    )

    return {
        "success": True,
        "message": "کامیابی سے لاگ ان ہو گئے!",
        "access_token": access_token,
        "student": {
            "id": student.id,
            "student_id": student.student_id,
            "full_name": student.full_name,
            "whatsapp_number": student.whatsapp_number,
            "requested_course": student.requested_course
        }
    }

@router.post("/logout")
def logout_student(response: Response):
    response.delete_cookie(key="student_access_token")
    return {"success": True, "message": "کامیابی سے لاگ آؤٹ ہو گیا۔"}

@router.get("/me")
def get_student_profile(student: Student = Depends(get_current_student)):
    return {
        "id": student.id,
        "student_id": student.student_id,
        "full_name": student.full_name,
        "parent_name": student.parent_name,
        "whatsapp_number": student.whatsapp_number,
        "country": student.country,
        "age": student.age,
        "email": student.email,
        "requested_course": student.requested_course,
        "status": student.status,
        "created_at": student.created_at.strftime("%Y-%m-%d %H:%M") if student.created_at else None
    }

@router.post("/progress/{lesson_id}")
def toggle_lesson_progress(
    lesson_id: int,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db)
):
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="سبق نہیں ملا")

    progress = db.query(StudentProgress).filter(
        StudentProgress.student_id == student.id,
        StudentProgress.lesson_id == lesson_id
    ).first()

    if progress:
        progress.is_completed = not progress.is_completed
        progress.completed_at = datetime.utcnow()
    else:
        progress = StudentProgress(
            student_id=student.id,
            course_id=lesson.course_id,
            lesson_id=lesson_id,
            is_completed=True
        )
        db.add(progress)

    db.commit()
    return {"success": True, "is_completed": progress.is_completed}
