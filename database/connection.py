from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
    AsyncEngine
)
from sqlalchemy.orm import declarative_base

from config import config

Base = declarative_base()

# Настройка движка для SQLite (без pool_size для SQLite)
engine: AsyncEngine = create_async_engine(
    config.DATABASE_URL,
    echo=config.DEBUG,
    future=True,
    pool_pre_ping=True,
    connect_args={
        "timeout": 30,
        "check_same_thread": False,
    }
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def init_db() -> None:
    """Инициализация БД"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Закрытие соединения с БД"""
    await engine.dispose()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Генератор сессии для middleware"""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()