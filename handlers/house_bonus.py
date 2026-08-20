import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from services.house_service import HouseService
from utils.user_utils import ensure_user, ensure_pet
from handlers.house import house_main

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "house_bonus")
async def claim_house_bonus(callback: CallbackQuery, session: AsyncSession) -> None:
    """Забрать ежедневный бонус дома"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    house_service = HouseService(session)
    result = await house_service.claim_daily_bonus(pet.id, user.id)
    
    if result["success"]:
        await callback.answer("✅ Бонус получен!", show_alert=True)
    else:
        await callback.answer(f"⏳ {result['message']}", show_alert=True)
    
    # Обновляем меню дома
    await house_main(callback, session)


@router.callback_query(F.data == "house_bonus_disabled")
async def house_bonus_disabled(callback: CallbackQuery) -> None:
    """Кнопка бонуса когда уже получен"""
    await callback.answer("⏳ Бонус уже получен сегодня! Возвращайся завтра.", show_alert=True)
