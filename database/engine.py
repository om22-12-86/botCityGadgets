import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base, Product  # Добавил импорт модели Product
from database.orm_query import orm_add_banner_description, orm_create_categories
from common.texts_for_db import categories, description_for_info_pages

# from .env file:
# DB_LITE=sqlite+aiosqlite:///my_base.db
# DB_URL=postgresql+asyncpg://login:password@localhost:5432/db_name

# Выберите нужный источник данных
# engine = create_async_engine(os.getenv('DB_LITE'), echo=True)
engine = create_async_engine(os.getenv('DB_URL'), echo=True)

# Используем единое имя для sessionmaker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)

async def create_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:  # Используем корректное имя SessionLocal
        await orm_create_categories(session, categories)
        await orm_add_banner_description(session, description_for_info_pages)

async def drop_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

async def get_db():
    async with SessionLocal() as session:  # Используем корректное имя SessionLocal
        yield session

async def check_product_availability(product_id, db_session: AsyncSession):
    product = await db_session.get(Product, product_id)
    if product and product.stock > 0:
        return True
    else:
        product.is_available = False
        await db_session.commit()
        return False
