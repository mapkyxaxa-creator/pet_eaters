from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from aiogram.exceptions import TelegramRetryAfter
import time
from collections import defaultdict


class ThrottlingMiddleware(BaseMiddleware):
    """Middleware для ограничения частоты запросов"""
    
    def __init__(self, rate_limit: float = 1.0):
        self.rate_limit = rate_limit
        self.last_calls: Dict[str, float] = defaultdict(float)
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user_id = self._get_user_id(event)
        if user_id:
            key = f"user_{user_id}"
            now = time.time()
            last_call = self.last_calls.get(key, 0)
            
            if now - last_call < self.rate_limit:
                # Если сообщение - отправляем уведомление
                if isinstance(event, Message):
                    await event.answer("⏳ Слишком часто! Подожди немного.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("⏳ Слишком часто! Подожди немного.", show_alert=False)
                return
            
            self.last_calls[key] = now
        
        return await handler(event, data)
    
    def _get_user_id(self, event: TelegramObject) -> int:
        """Получение ID пользователя из события"""
        if isinstance(event, Message) and event.from_user:
            return event.from_user.id
        if isinstance(event, CallbackQuery) and event.from_user:
            return event.from_user.id
        return 0