import os
import logging
from sqlalchemy import create_engine, inspect, text
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

def migrate_existing_tables():
    """Ensure newly added columns exist in previously created tables."""
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    if "books" in existing_tables:
        book_cols = [c["name"] for c in inspector.get_columns("books")]
        with engine.begin() as conn:
            if "author" not in book_cols:
                conn.execute(text("ALTER TABLE books ADD COLUMN author VARCHAR(120) DEFAULT 'نامعلوم مصنف'"))
            if "category" not in book_cols:
                conn.execute(text("ALTER TABLE books ADD COLUMN category VARCHAR(80) DEFAULT 'قرآنی علوم'"))
            if "cover_image" not in book_cols:
                conn.execute(text("ALTER TABLE books ADD COLUMN cover_image VARCHAR(300) NULL"))
            if "is_published" not in book_cols:
                conn.execute(text("ALTER TABLE books ADD COLUMN is_published BOOLEAN DEFAULT 1"))

    if "classroom" in existing_tables:
        room_cols = [c["name"] for c in inspector.get_columns("classroom")]
        with engine.begin() as conn:
            if "zoom_link" not in room_cols:
                conn.execute(text("ALTER TABLE classroom ADD COLUMN zoom_link VARCHAR(500) DEFAULT 'https://zoom.us/join'"))
            if "zoom_meeting_id" not in room_cols:
                conn.execute(text("ALTER TABLE classroom ADD COLUMN zoom_meeting_id VARCHAR(100) DEFAULT '854 2190 3341'"))
            if "zoom_password" not in room_cols:
                conn.execute(text("ALTER TABLE classroom ADD COLUMN zoom_password VARCHAR(100) DEFAULT '786786'"))
            if "zoom_topic" not in room_cols:
                conn.execute(text("ALTER TABLE classroom ADD COLUMN zoom_topic VARCHAR(200) DEFAULT 'روزانہ کی آن لائن کلاس (Zoom Live)'"))
            if "zoom_instructions" not in room_cols:
                conn.execute(text("ALTER TABLE classroom ADD COLUMN zoom_instructions VARCHAR(500) DEFAULT 'کلاس کے وقت زووم لنک پر کلک کریں اور لائیو کلاس میں شرکت کریں۔'"))
            if "is_zoom_live" not in room_cols:
                conn.execute(text("ALTER TABLE classroom ADD COLUMN is_zoom_live BOOLEAN DEFAULT 1"))

def seed_initial_data(db: Session):
    from models.classroom import Classroom
    from models.contact_setting import ContactSetting
    from models.course import Course, Lesson
    from models.book import Book
    from models.notification import Notification

    # 1. Classroom
    room = db.query(Classroom).filter(Classroom.permanent_id == settings.PERMANENT_CLASS_ID).first()
    if not room:
        room = Classroom(
            permanent_id=settings.PERMANENT_CLASS_ID,
            name=settings.DEFAULT_CLASS_NAME,
            password=settings.DEFAULT_CLASS_PASSWORD,
            max_students=settings.MAX_STUDENTS_LIMIT,
            is_live=False
        )
        db.add(room)
        db.commit()
        logger.info("Default Classroom created.")

    # 2. Contact Settings
    contact = db.query(ContactSetting).first()
    if not contact:
        contact = ContactSetting(
            institute_name="دار التعلیم والقرآن اکیڈمی",
            teacher_name="قاری عبد الرحمن صاحب",
            whatsapp_number="+92 300 1234567",
            phone_number="+92 300 1234567",
            email="abdulrehman2787182@gmail.com",
            address="جامع مسجد، نزد مین مارکیٹ، لاہور، پاکستان",
            welcome_quote="«خَيْرُكُمْ مَنْ تَعَلَّمَ الْقُرْآنَ وَعَلَّمَهُ» — تم میں سے بہترین شخص وہ ہے جو قرآن سیکھے اور سکھائے۔ (صحیح بخاری)"
        )
        db.add(contact)
        db.commit()
        logger.info("Default Contact Settings seeded.")

    # 3. Islamic Courses
    if db.query(Course).count() == 0:
        courses_data = [
            {
                "title": "Quran Translation",
                "title_urdu": "ترجمۃ القرآن الکریم",
                "slug": "quran-translation",
                "category": "قرآنی علوم",
                "duration": "6 Months / 6 ماہ",
                "thumbnail_url": "https://images.unsplash.com/photo-1609599006353-e629aaabfeae?auto=format&fit=crop&w=600&q=80",
                "description": "قرآن مجید کا مکمل لفظی اور بامحاورہ سلیس اردو ترجمہ، بنیادی گرائمر اور فہمِ دین کے ساتھ۔",
                "order_index": 1,
                "lessons": [
                    {"lesson_number": 1, "title": "سورۃ الفاتحہ کا مفہوم و ترجمہ", "description": "ام الکتاب سورۃ الفاتحہ کی فضیلت، آیات کا لفظی اور تفصیلی ترجمہ۔"},
                    {"lesson_number": 2, "title": "سورۃ البقرہ: تعارف و ابتدائی 5 آیات", "description": "متقیوں کے اوصاف اور قرآن مجید کی حقانیت۔"},
                    {"lesson_number": 3, "title": "آیت الکرسی کا ترجمہ و شانِ عظمت", "description": "توحیدِ باری تعالیٰ کا جامع بیان اور آیت الکرسی کی برکات۔"},
                    {"lesson_number": 4, "title": "آخری پارے کی منتخب سورتوں کا ترجمہ", "description": "قصار السور (سورۃ الاخلاص، الفلق، الناس) کا لفظی مفہوم۔"}
                ]
            },
            {
                "title": "Quran Tafseer",
                "title_urdu": "تفسیر القرآن الکریم",
                "slug": "quran-tafseer",
                "category": "تفسیر و فہم",
                "duration": "1 Year / 1 سال",
                "thumbnail_url": "https://images.unsplash.com/photo-1584286595398-a59f21d313f5?auto=format&fit=crop&w=600&q=80",
                "description": "مستند تفاسیر کی روشنی میں آیات کے شانِ نزول، فقہی احکام اور دورِ حاضر کے مسائل کا حل۔",
                "order_index": 2,
                "lessons": [
                    {"lesson_number": 1, "title": "اصولِ تفسیر اور علوم القرآن کا تعارف", "description": "وحی کی اقسام، حفاظت قرآن اور تفسیر کے معتبر اصول۔"},
                    {"lesson_number": 2, "title": "تفسیر سورۃ یٰسین مبارکہ", "description": "قلب القرآن سورۃ یٰسین کی تفصیلی تفسیر اور آخرت کے دلائل۔"},
                    {"lesson_number": 3, "title": "تفسیر سورۃ الرحمٰن", "description": "اللہ تعالیٰ کی نعمتوں کا شکر اور قدرت کے نظارے۔"}
                ]
            },
            {
                "title": "Noorani Qaida with Tajweed",
                "title_urdu": "نورانی قاعدہ مع تجوید",
                "slug": "noorani-qaida",
                "category": "تجوید و قراءت",
                "duration": "3 Months / 3 ماہ",
                "thumbnail_url": "https://images.unsplash.com/photo-1542816417-0983c9c9ad53?auto=format&fit=crop&w=600&q=80",
                "description": "بچوں اور بڑوں کے لیے قرآن پاک کو درست مخارج اور ترتیل کے ساتھ پڑھنے کی بنیادی مشقیں۔",
                "order_index": 3,
                "lessons": [
                    {"lesson_number": 1, "title": "تختی نمبر 1: مفردات (حروفِ تہجی)", "description": "عربی حروف کے درست مخارج اور صوتی ادائیگی۔", "is_free_preview": True},
                    {"lesson_number": 2, "title": "تختی نمبر 2: مرکبات (ملے جلے حروف)", "description": "حروف کی مختلف شکلیں اور پہچان۔"},
                    {"lesson_number": 3, "title": "تختی نمبر 3: مقطعات", "description": "حروفِ مقطعات کو کھینچ کر پڑھنے کا اصول۔"},
                    {"lesson_number": 4, "title": "تختی نمبر 4: حرکات (زبر، زیر، پیش)", "description": "حرکات کو بغیر کھینچے معروف پڑھنے کی مشق۔"}
                ]
            },
            {
                "title": "Masnoon Duain & Daily Adhkar",
                "title_urdu": "مسنون دعائیں اور اذکار",
                "slug": "masnoon-duain",
                "category": "سنت و اذکار",
                "duration": "1 Month / 1 ماہ",
                "thumbnail_url": "https://images.unsplash.com/photo-1579783902614-a3fb3927b675?auto=format&fit=crop&w=600&q=80",
                "description": "صبح و شام کے مسنون اذکار، کھانے پینے، سونے جاگنے اور سفر کی روزمرہ دعائیں مع اردو ترجمہ۔",
                "order_index": 4,
                "lessons": [
                    {"lesson_number": 1, "title": "صبح اور شام کے مسنون اذکار", "description": "حفاظت کی دعائیں اور سید الاستغفار۔", "is_free_preview": True},
                    {"lesson_number": 2, "title": "سونے اور بیدار ہونے کی دعائیں", "description": "سنت کے مطابق سونے کے آداب اور اذکار۔"},
                    {"lesson_number": 3, "title": "کھانے، پینے اور لباس کی دعائیں", "description": "روزمرہ کے کاموں میں برکت کے مسنون طریقے اور دعائیں۔"}
                ]
            },
            {
                "title": "Forty Ahadith of Imam Nawawi",
                "title_urdu": "چالیس احادیث نبوی (اربعین نووی)",
                "slug": "forty-ahadith",
                "category": "حدیث شریف",
                "duration": "2 Months / 2 ماہ",
                "thumbnail_url": "https://images.unsplash.com/photo-1590076215667-875d4ef2d7ee?auto=format&fit=crop&w=600&q=80",
                "description": "دینِ اسلام کے بنیادی اصولوں پر مشتمل امام نوویؒ کی مشہور چالیس احادیث مبارکہ کا مطالعہ۔",
                "order_index": 5,
                "lessons": [
                    {"lesson_number": 1, "title": "حدیث 1: انما الاعمال بالنیات", "description": "اعمال کا دارومدار نیتوں پر ہے - اخلاصِ نیت کی اہمیت۔", "is_free_preview": True},
                    {"lesson_number": 2, "title": "حدیث 2: حدیثِ جبرائیل (اسلام، ایمان اور احسان)", "description": "دین کے تین بنیادی درجات کی جامع وضاحت۔"},
                    {"lesson_number": 3, "title": "حدیث 3: اسلام کی پانچ بنیادیں", "description": "کلمہ شہادت، نماز، زکوۃ، روزہ اور حج کا فلسفہ۔"}
                ]
            },
            {
                "title": "Namaz & Taharat Practical Course",
                "title_urdu": "نماز اور بنیادی طہارت کورس",
                "slug": "namaz-taharat",
                "category": "فقہ و عبادات",
                "duration": "1 Month / 1 ماہ",
                "thumbnail_url": "https://images.unsplash.com/photo-1564769625905-50e93615e769?auto=format&fit=crop&w=600&q=80",
                "description": "وضو، غسل، تیمم کے فرائض اور مسنون نماز (تکبیر تحریمہ سے سلام تک) عملی طریقہ کار۔",
                "order_index": 6,
                "lessons": [
                    {"lesson_number": 1, "title": "وضو اور طہارت کا عملی طریقہ", "description": "وضو کے فرائض، سنن اور مستحبات کی تفصیلی وضاحت۔", "is_free_preview": True},
                    {"lesson_number": 2, "title": "نماز کے فرائض، شرائط اور واجبات", "description": "نماز کن چیزوں سے درست ہوتی ہے اور سجدہ سہو کے احکام۔"},
                    {"lesson_number": 3, "title": "مسنون طریقہ نماز مع دعائے قنوت و تشہد", "description": "تکبیر سے لے کر سلام تک ہر رکن کی درست ادائیگی۔"}
                ]
            }
        ]

        for c_data in courses_data:
            lessons_info = c_data.pop("lessons", [])
            course = Course(**c_data)
            db.add(course)
            db.flush()
            for l_info in lessons_info:
                lesson = Lesson(course_id=course.id, **l_info)
                db.add(lesson)
        db.commit()
        logger.info("Default Islamic Courses and Lessons seeded successfully.")

    # 4. Library Books Seeding
    if db.query(Book).count() == 0:
        sample_books = [
            {
                "title": "نورانی قاعدہ مع تجوید",
                "author": "مولانا نور محمد حقانیؒ",
                "category": "تجوید و قراءت",
                "description": "قرآن پاک کی درست تلاوت کے لیے دنیا بھر میں رائج مستند بنیادی قاعدہ۔",
                "cover_image": "https://images.unsplash.com/photo-1542816417-0983c9c9ad53?auto=format&fit=crop&w=400&q=80",
                "filename": "noorani_qaida.pdf",
                "file_path": "uploads/books/noorani_qaida.pdf",
                "file_size": 2048500,
                "total_pages": 32,
                "is_published": True
            },
            {
                "title": "اربعین نووی (چالیس احادیث)",
                "author": "امام یحییٰ بن شرف نوویؒ",
                "category": "حدیث شریف",
                "description": "اسلام کے بنیادی عقائد و احکام پر محیط چالیس جامع احادیث کا مجموعہ۔",
                "cover_image": "https://images.unsplash.com/photo-1590076215667-875d4ef2d7ee?auto=format&fit=crop&w=400&q=80",
                "filename": "forty_ahadith.pdf",
                "file_path": "uploads/books/forty_ahadith.pdf",
                "file_size": 1548000,
                "total_pages": 48,
                "is_published": True
            },
            {
                "title": "حصن المسلم (مسنون دعائیں)",
                "author": "ڈاکٹر سعید بن علی بن وہف القحطانیؒ",
                "category": "سنت و اذکار",
                "description": "قرآن و سنت کی روشنی میں روزمرہ کے تمام مسنون اذکار اور دعاؤں کا نادر مجموعہ۔",
                "cover_image": "https://images.unsplash.com/photo-1579783902614-a3fb3927b675?auto=format&fit=crop&w=400&q=80",
                "filename": "hisnul_muslim.pdf",
                "file_path": "uploads/books/hisnul_muslim.pdf",
                "file_size": 3120000,
                "total_pages": 120,
                "is_published": True
            },
            {
                "title": "تعلیم الاسلام (چار حصے)",
                "author": "مفتی کفایت اللہ دہلویؒ",
                "category": "فقہ و اسلامی عقائد",
                "description": "عقائد، وضو، نماز، روزہ، زکوٰۃ اور حج کے ضروری احکام پر مستند بنیادی کتاب۔",
                "cover_image": "https://images.unsplash.com/photo-1564769625905-50e93615e769?auto=format&fit=crop&w=400&q=80",
                "filename": "taleem_ul_islam.pdf",
                "file_path": "uploads/books/taleem_ul_islam.pdf",
                "file_size": 4200000,
                "total_pages": 160,
                "is_published": True
            }
        ]
        for b_data in sample_books:
            b = Book(**b_data)
            db.add(b)
        db.commit()
        logger.info("Default Library Books seeded successfully.")

    # 5. Global Welcome Notification
    if db.query(Notification).count() == 0:
        welcome_notice = Notification(
            title="خوش آمدید — دار التعلیم والقرآن اکیڈمی",
            message="تمام طلبہ کرام کو اکیڈمی میں خوش آمدید کہا جاتا ہے۔ لائیو کلاس کے اوقات میں کلاس روم میں شامل ہوں۔",
            type="info"
        )
        db.add(welcome_notice)
        db.commit()

    # 6. Sample Daily Videos
    from models.daily_video import DailyVideo
    if db.query(DailyVideo).count() == 0:
        sample_videos = [
            {
                "title": "روزانہ کا سبق 1: سورۃ الفاتحہ کی تجوید و درست مخارج",
                "description": "ام الکتاب سورۃ الفاتحہ کے حروف کے درست مخارج، ترتیل اور تجوید کے ضروری قواعد کی عملی مشق۔",
                "video_type": "url",
                "video_url": "https://www.youtube.com/watch?v=F73M175D3lM",
                "thumbnail_url": "https://images.unsplash.com/photo-1609599006353-e629aaabfeae?auto=format&fit=crop&w=600&q=80",
                "category": "تجوید و قراءت",
                "duration": "12 منٹ",
                "is_published": True
            },
            {
                "title": "روزانہ کا سبق 2: آیت الکرسی کے فضائل اور لفظی ترجمہ",
                "description": "عظیم ترین آیت 'آیت الکرسی' کا لفظ بہ لفظ ترجمہ، توحید باری تعالیٰ اور روزمرہ حفاظت کے اعمال۔",
                "video_type": "url",
                "video_url": "https://www.youtube.com/watch?v=yWbB39_d24E",
                "thumbnail_url": "https://images.unsplash.com/photo-1584286595398-a59f21d313f5?auto=format&fit=crop&w=600&q=80",
                "category": "ترجمہ و تفسیر",
                "duration": "18 منٹ",
                "is_published": True
            },
            {
                "title": "روزانہ کا سبق 3: وضو اور نماز کا مسنون طریقہ",
                "description": "تکبیر تحریمہ سے لے کر سلام پھیرنے تک نماز کے تمام ارکان کی درست ادائیگی اور عام غلطیوں کی اصلاح۔",
                "video_type": "url",
                "video_url": "https://www.youtube.com/watch?v=kpv4QnFqZMo",
                "thumbnail_url": "https://images.unsplash.com/photo-1564769625905-50e93615e769?auto=format&fit=crop&w=600&q=80",
                "category": "نماز و احکام",
                "duration": "15 منٹ",
                "is_published": True
            }
        ]
        for v_data in sample_videos:
            v = DailyVideo(**v_data)
            db.add(v)
        db.commit()
        logger.info("Default Daily Videos seeded successfully.")

def init_db():
    from models import (
        teacher, classroom, book, attendance, message,
        student, course, student_progress, contact_setting, notification, daily_video
    )
    Base.metadata.create_all(bind=engine)
    migrate_existing_tables()
    logger.info("Database tables initialized & migrated successfully.")

    db = SessionLocal()
    try:
        seed_initial_data(db)
    except Exception as e:
        logger.error(f"Error seeding initial data: {e}")
        db.rollback()
    finally:
        db.close()
