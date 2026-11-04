import bcrypt
from datetime import datetime, timedelta
from jose import JWTError, jwt
from typing import Optional, Dict, Any
from fastapi import HTTPException, status, Request
from config import settings

class AuthService:
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        try:
            return bcrypt.checkpw(plain_password.encode("utf-8")[:72], hashed_password.encode("utf-8"))
        except Exception:
            return False

    @staticmethod
    def get_password_hash(password: str) -> str:
        pwd_bytes = password.encode("utf-8")[:72]
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt

    @staticmethod
    def decode_token(token: str) -> Optional[Dict[str, Any]]:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            return payload
        except JWTError:
            return None

    @staticmethod
    def get_current_teacher_from_token(token: str, db) -> Optional[Any]:
        from models.teacher import Teacher
        payload = AuthService.decode_token(token)
        if not payload:
            return None
        if payload.get("role") != "teacher":
            return None
        teacher_id = payload.get("sub")
        if not teacher_id:
            return None
        teacher = db.query(Teacher).filter(Teacher.id == int(teacher_id)).first()
        return teacher
