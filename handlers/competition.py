"""Обработчики для соревнований"""
import logging
from typing import Union
from aiogram import Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from utils.user_utils import ensure_user, ensure_pet
from utils.message_utils import send_or_edit, delete_message
from services.competition_service import CompetitionService
from services.level_service import LevelService

logger = logging.getLogger(__name__)

router = Router()


# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====

def _get_competition_emoji(comp_type: str) -> str:
    """Получить эмодзи для типа соревнования"""
    emojis = {
        "pizza": "🍕",
        "sausage": "🌭", 
        "cake": "🎂",
        "random": "🎲",
    }
    return emojis.get(comp_type, "🏆")


def _get_medal(rank: int) -> str:
    """Получить медаль для места"""
    if rank == 1:
        return "🥇"
    elif rank == 2:
        return "🥈"
    elif rank == 3:
        return "🥉"
    else:
        return "▪️"


def _get_league_emoji(league_id: str) -> str:
    """Получить эмодзи для лиги"""
    emojis = {
        "bronze": "🥉",
        "silver": "🥈",
        "gold": "🥇",
        "diamond": "💎",
        "legendary": "👑",
    }
    return emojis.get(league_id, "⭐")


# ===== КОМАНДЫ И CALLBACK'И =====

@router.message(Command("competition"))
async def cmd_competition(message: Message, session: AsyncSession) -> None:
    """Команда /competition"""
    user = await ensure_user(message, session)
    if not user:
        return
    
    pet = await ensure_pet(message, session, user)
    if not pet:
        return
    
    await show_competition(message, session)


@router.callback_query(lambda c: c.data == "competition")
async def callback_competition(callback: CallbackQuery, session: AsyncSession) -> None:
    """Колбэк для кнопки 'Соревнования'"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    await delete_message(callback)
    await show_competition(callback, session)
    await callback.answer()


@router.callback_query(lambda c: c.data == "competition_join")
async def callback_competition_join(callback: CallbackQuery, session: AsyncSession) -> None:
    """Зарегистрироваться на соревнование"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    service = CompetitionService(session)
    result = await service.join_competition(pet.id, user.id)
    
    await callback.answer(result["message"], show_alert=True)
    await show_competition(callback, session)


@router.callback_query(lambda c: c.data == "competition_my_results")
async def callback_competition_my_results(callback: CallbackQuery, session: AsyncSession) -> None:
    """Мои результаты"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    service = CompetitionService(session)
    results = await service.get_my_results(user.id)
    
    if not results:
        text = "📊 У тебя пока нет результатов в соревнованиях.\nУчаствуй и побеждай! 🏆"
    else:
        text = "📊 <b>Твои результаты в соревнованиях</b>\n\n"
        for idx, r in enumerate(results[:10], 1):
            comp_type = r.competition.type if r.competition else "неизвестно"
            emoji = _get_competition_emoji(comp_type)
            text += f"{idx}. {emoji} <b>{comp_type}</b>\n"
            text += f"   🏅 Очки: {r.score} | Место: {r.rank or '—'}\n"
            text += f"   🪙 +{r.reward_coins} монет | ⭐ +{r.reward_xp} XP\n"
            if r.reward_title:
                text += f"   🏷️ Титул: {r.reward_title}\n"
            text += f"   {'✅ Награда получена' if r.rewards_claimed else '⏳ Награда ожидает'}\n\n"
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Забрать награды", callback_data="competition_claim")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="competition")],
        ]
    )
    
    await send_or_edit(callback, text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data == "competition_claim")
async def callback_competition_claim(callback: CallbackQuery, session: AsyncSession) -> None:
    """Забрать награды"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    service = CompetitionService(session)
    result = await service.claim_rewards(user.id)
    
    await callback.answer(result["message"], show_alert=True)
    await show_competition(callback, session)


@router.callback_query(lambda c: c.data == "competition_top")
async def callback_competition_top(callback: CallbackQuery, session: AsyncSession) -> None:
    """Топ участников"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    service = CompetitionService(session)
    results = await service.get_competition_top(10)
    
    if not results:
        text = "👥 Пока нет участников в этом соревновании. Будь первым! 🏆"
    else:
        text = f"👥 <b>Топ участников соревнования</b>\n\n"
        for idx, r in enumerate(results, 1):
            pet_name = r.pet.name if r.pet else "Питомец"
            medal = _get_medal(idx)
            text += f"{medal} <b>{idx}.</b> {pet_name} — {r.score} очков"
            if r.league_id:
                league = _get_league_emoji(r.league_id)
                text += f" {league}"
            text += "\n"
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="competition")],
        ]
    )
    
    await send_or_edit(callback, text, reply_markup=keyboard)
    await callback.answer()


# ===== ОСНОВНОЙ ЭКРАН =====

async def show_competition(source: Union[Message, CallbackQuery], session: AsyncSession) -> None:
    """Показать информацию о соревновании"""
    user = await ensure_user(source, session)
    if not user:
        return
    
    pet = await ensure_pet(source, session, user)
    if not pet:
        return
    
    service = CompetitionService(session)
    
    # Проверяем активное соревнование
    competition = await service.get_active_competition()
    
    if not competition:
        text = "❌ Нет активных соревнований.\nЗагляни позже! 🏆\n\n"
        text += "💡 Соревнования проходят регулярно.\nСледи за новостями!"
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="competition")],
                [InlineKeyboardButton(text="🔙 В меню", callback_data="main_menu")],
            ]
        )
        await send_or_edit(source, text, reply_markup=keyboard)
        return
    
    # Получаем статус
    status = await service.get_competition_status(pet.id)
    
    # Информация о соревновании
    comp_info = await service.get_competition_info()
    
    text = f"{comp_info.get('emoji', '🏆')} <b>{comp_info.get('name', 'Соревнование')}</b>\n\n"
    text += f"📝 {comp_info.get('description', '')}\n"
    text += f"👥 Участников: {comp_info.get('participants', 0)}\n"
    if comp_info.get('started_at'):
        text += f"⏰ Началось: {comp_info['started_at'].strftime('%d.%m.%Y %H:%M')}\n\n"
    
    if status.get("is_participating"):
        text += "✅ <b>Ты участвуешь!</b>\n"
        text += f"📊 Очки: {status.get('score', 0)}\n"
        if status.get('league'):
            league_emoji = _get_league_emoji(status['league'])
            text += f"🏅 Лига: {league_emoji} {status['league'].capitalize()}\n"
        if status.get('rank'):
            text += f"📊 Место: #{status['rank']}\n"
    else:
        text += "👤 Ты ещё не участвуешь!\n"
        text += "🎯 Присоединяйся и поборись за призы!"
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Мои результаты", callback_data="competition_my_results")],
            [InlineKeyboardButton(text="👥 Топ участников", callback_data="competition_top")],
            [InlineKeyboardButton(text="🔙 В меню", callback_data="main_menu")],
        ]
    )
    
    # Добавляем кнопку участия если не участвует
    if not status.get("is_participating") and status.get("success"):
        keyboard.inline_keyboard.insert(0, [
            InlineKeyboardButton(text="🎯 Участвовать!", callback_data="competition_join")
        ])
    
    await send_or_edit(source, text, reply_markup=keyboard)