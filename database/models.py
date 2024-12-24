from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True)
    woo_key = Column(String)
    woo_secret = Column(String)
    torob_key = Column(String)
    is_active = Column(Boolean, default=False)
    subscription_end = Column(DateTime)
    discount_percentage = Column(Float, default=5.0)
    created_at = Column(DateTime, default=datetime.utcnow)
