from typing import Union, Optional
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories.user_repository import UserRepository
from database.models import User, Pet  # <-- ДОБАВЛЕН Pet


def get_user_id(event: Union[Message, CallbackQuery]) -> Optional[int]:
    """Универсальное получение ID пользователя из события"""
    if isinstance(event, Message):
        return event.from_user.id if event.from_user else None
    elif isinstance(event, CallbackQuery):
        return event.from_user.id if event.from_user else None
    return None


async def get_user(
    event: Union[Message, CallbackQuery],
    session: AsyncSession
) -> Optional[User]:
    """Универсальное получение пользователя из БД"""
    user_id = get_user_id(event)
    if not user_id:
        return None
    
    user_repo = UserRepository(session)
    return await user_repo.get_by_telegram_id(user_id)


async def ensure_user(
    event: Union[Message, CallbackQuery],
    session: AsyncSession,
    send_error: bool = True
) -> Optional[User]:
    """Проверить наличие пользователя, при отсутствии отправить ошибку"""
    user_id = get_user_id(event)
    
    if not user_id:
        if send_error:
            error_text = "❌ Пользователь не найден. Используй /start"
            if isinstance(event, Message):
                await event.answer(error_text)
            elif isinstance(event, CallbackQuery):
                try:
                    await event.message.edit_text(error_text)
                except Exception:
                    await event.message.answer(error_text)
                await event.answer()
        return None
    
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(user_id)
    
    if not user and send_error:
        error_text = "❌ Пользователь не найден. Используй /start"
        if isinstance(event, Message):
            await event.answer(error_text)
        elif isinstance(event, CallbackQuery):
            try:
                await event.message.edit_text(error_text)
            except Exception:
                await event.message.answer(error_text)
            await event.answer()
    
    return user


async def ensure_pet(
    event: Union[Message, CallbackQuery],
    session: AsyncSession,
    user: User,
    send_error: bool = True
) -> Optional[Pet]:  # <-- ИСПРАВЛЕНО: возвращает Pet, а не User
    """Проверить наличие питомца у пользователя"""
    from database.repositories.pet_repository import PetRepository
    
    pet_repo = PetRepository(session)
    pet = await pet_repo.get_by_user_id(user.id)
    
    if not pet and send_error:
        error_text = "🐾 У тебя еще нет питомца! Используй /start, чтобы создать."
        
        if isinstance(event, Message):
            await event.answer(error_text)
        elif isinstance(event, CallbackQuery):
            try:
                await event.message.edit_text(error_text)
            except Exception:
                await event.message.answer(error_text)
            await event.answer()
    
    return pet