from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from database import Base

class ContactSetting(Base):
    __tablename__ = "contact_settings"

    id = Column(Integer, primary_key=True, index=True)
    institute_name = Column(String(150), default="دار التعلیم والقرآن اکیڈمی")
    teacher_name = Column(String(120), default="قاری عبد الرحمن صاحب")
    whatsapp_number = Column(String(50), default="+92 300 1234567")
    phone_number = Column(String(50), default="+92 300 1234567")
    email = Column(String(120), default="abdulrehman2787182@gmail.com")
    address = Column(String(255), default="جامع مسجد، نزد مین مارکیٹ، لاہور، پاکستان")
    welcome_quote = Column(Text, default="«خَيْرُكُمْ مَنْ تَعَلَّمَ الْقُرْآنَ وَعَلَّمَهُ» — تم میں سے بہترین شخص وہ ہے جو قرآن سیکھے اور سکھائے۔ (صحیح بخاری)")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ContactSetting teacher='{self.teacher_name}' whatsapp='{self.whatsapp_number}'>"
