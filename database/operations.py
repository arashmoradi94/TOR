from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from cryptography.fernet import Fernet
from .models import Base, User
from config import DATABASE_URL, ENCRYPTION_KEY

engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
fernet = Fernet(ENCRYPTION_KEY.encode())

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_user(telegram_id: int) -> User:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

async def create_user(telegram_id: int) -> User:
    async with AsyncSessionLocal() as session:
        user = User(telegram_id=telegram_id)
        session.add(user)
        await session.commit()
        return user

async def update_api_keys(telegram_id: int, woo_key: str = None, woo_secret: str = None, torob_key: str = None):
    async with AsyncSessionLocal() as session:
        user = await get_user(telegram_id)
        if not user:
            user = await create_user(telegram_id)
            
        if woo_key:
            user.woo_key = fernet.encrypt(woo_key.encode()).decode()
        if woo_secret:
            user.woo_secret = fernet.encrypt(woo_secret.encode()).decode()
        if torob_key:
            user.torob_key = fernet.encrypt(torob_key.encode()).decode()
            
        await session.commit()
