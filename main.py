import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import init_db
from routers import auth, teacher, student, student_auth, admin_management, websocket, views

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables, seed courses, books, settings & single permanent classroom
    init_db()
    yield

app = FastAPI(
    title=settings.APP_NAME,
    description="دار التعلیم والقرآن — Comprehensive Islamic Education Platform with Student Admission & Admin Management System",
    version="2.0.0",
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Files & Uploads
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)
os.makedirs("static/images", exist_ok=True)
os.makedirs("uploads/books", exist_ok=True)
os.makedirs("uploads/lessons", exist_ok=True)
os.makedirs("uploads/covers", exist_ok=True)
os.makedirs("uploads/videos", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Register Routers
app.include_router(auth.router)
app.include_router(teacher.router)
app.include_router(student.router)
app.include_router(student_auth.router)
app.include_router(admin_management.router)
app.include_router(websocket.router)
app.include_router(views.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=True)
