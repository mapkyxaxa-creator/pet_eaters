import asyncio
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import OperationalError

from database.connection import async_session

logger = logging.getLogger(__name__)


class DatabaseMiddleware(BaseMiddleware):
    """
    Middleware для внедрения сессии БД в хендлеры.
    
    Создаёт сессию, передаёт её в хендлер через data["session"],
    и автоматически фиксирует изменения после успешного выполнения.
    При ошибке делает rollback.
    
    Добавлена поддержка повторных попыток при блокировке БД.
    """
    
    MAX_RETRIES = 3
    RETRY_DELAY = 0.5
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        last_error = None
        
        for attempt in range(self.MAX_RETRIES):
            try:
                async with async_session() as session:
                    data["session"] = session
                    try:
                        result = await handler(event, data)
                        # Фиксируем все изменения в БД
                        await session.commit()
                        return result
                    except Exception as e:
                        # Откатываем изменения при ошибке
                        await session.rollback()
                        raise e
                # Если дошли сюда — успешно
                break
            except OperationalError as e:
                last_error = e
                if "database is locked" in str(e) and attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_DELAY * (attempt + 1)
                    logger.warning(
                        f"⚠️ БД заблокирована, попытка {attempt + 1}/{self.MAX_RETRIES}, "
                        f"повтор через {delay:.1f}с"
                    )
                    await asyncio.sleep(delay)
                else:
                    raise e
            except Exception as e:
                # Другие ошибки не повторяем
                raise e
        
        if last_error:
            raise last_error