import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("database")

Base = declarative_base()

def ensure_mysql_database(db_url: str):
    """Ensure MySQL database exists before SQLAlchemy engine connects."""
    try:
        url = make_url(db_url)
        if url.database and "mysql" in url.drivername:
            import pymysql
            conn = pymysql.connect(
                host=url.host or "localhost",
                port=url.port or 3306,
                user=url.username or "root",
                password=url.password or "",
                connect_timeout=3
            )
            with conn.cursor() as cur:
                cur.execute(f"CREATE DATABASE IF NOT EXISTS `{url.database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            conn.commit()
            conn.close()
            logger.info(f"Verified MySQL database `{url.database}`.")
    except Exception as err:
        logger.warning(f"Note on MySQL auto-check: {err}")

def get_engine():
    if settings.DATABASE_URL and not settings.DATABASE_URL.startswith("sqlite"):
        try:
            ensure_mysql_database(settings.DATABASE_URL)
            # Test connecting to MySQL
            test_engine = create_engine(
                settings.DATABASE_URL,
                pool_pre_ping=True,
                pool_recycle=3600,
                connect_args={"connect_timeout": 5}
            )
            with test_engine.connect() as conn:
                logger.info("Successfully connected to MySQL database!")
            return test_engine
        except Exception as e:
            logger.warning(f"Could not connect to MySQL ({e}).")
            if settings.FALLBACK_TO_SQLITE:
                logger.info(f"Falling back to local SQLite database: {settings.SQLITE_URL}")
                return create_engine(
                    settings.SQLITE_URL,
                    connect_args={"check_same_thread": False}
                )
            else:
                raise e
    else:
        return create_engine(
            settings.SQLITE_URL,
            connect_args={"check_same_thread": False}
        )

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    from models import teacher, classroom, book, attendance, message
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized successfully.")

    # Ensure single permanent classroom exists
    db = SessionLocal()
    try:
        room = db.query(classroom.Classroom).filter(classroom.Classroom.permanent_id == settings.PERMANENT_CLASS_ID).first()
        if not room:
            new_room = classroom.Classroom(
                permanent_id=settings.PERMANENT_CLASS_ID,
                name=settings.DEFAULT_CLASS_NAME,
                password=settings.DEFAULT_CLASS_PASSWORD,
                max_students=settings.MAX_STUDENTS_LIMIT,
                is_live=False
            )
            db.add(new_room)
            db.commit()
            logger.info(f"Permanent Classroom '{settings.PERMANENT_CLASS_ID}' created with password '{settings.DEFAULT_CLASS_PASSWORD}'.")
    finally:
        db.close()
