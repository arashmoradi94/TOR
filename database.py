from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

# تنظیمات پایگاه داده
DATABASE_URL = os.getenv('DATABASE_URL')  # به راحتی می‌توانید از SQLite یا هر دیتابیس دیگر استفاده کنید

# ایجاد پایگاه داده
Base = declarative_base()
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# مدل کاربر
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True)
    username = Column(String, index=True)
    subscription_type = Column(String, default='free')
    subscription_end_date = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# مدل لایسنس
class License(Base):
    __tablename__ = "licenses"

    id = Column(Integer, primary_key=True, index=True)
    license_key = Column(String, unique=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    type = Column(String)
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")

# ایجاد تمام جداول در پایگاه داده
Base.metadata.create_all(bind=engine)

# تابع برای دسترسی به جلسه پایگاه داده
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
