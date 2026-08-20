import logging
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from database.models import User, Pet
from database.repositories.user_repository import UserRepository
from database.repositories.pet_repository import PetRepository
from utils.user_utils import ensure_user

logger = logging.getLogger(__name__)

router = Router()

# ===== СПИСОК АДМИНОВ (Telegram ID) =====
ADMIN_IDS = [2031001867]  # <-- ЗАМЕНИТЬ НА СВОЙ TELEGRAM ID


@router.message(Command("admin_stats"))
async def cmd_admin_stats(message: Message, session: AsyncSession) -> None:
    """Команда /admin_stats — статистика бота (только для админов)"""
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    await show_admin_stats(message, session)


@router.callback_query(F.data == "admin_stats")
async def admin_stats_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Callback для кнопки статистики"""
    user_id = callback.from_user.id
    
    if user_id not in ADMIN_IDS:
        await callback.answer("❌ У вас нет доступа.", show_alert=True)
        return
    
    await show_admin_stats(callback, session)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_top_"))
async def admin_top_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Callback для переключения топов"""
    user_id = callback.from_user.id
    
    if user_id not in ADMIN_IDS:
        await callback.answer("❌ У вас нет доступа.", show_alert=True)
        return
    
    top_type = callback.data.split("_")[2]
    await show_top_list(callback, session, top_type)
    await callback.answer()


async def show_admin_stats(event: Message | CallbackQuery, session: AsyncSession) -> None:
    """Показать статистику бота"""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)
    
    # ===== СТАТИСТИКА ПОЛЬЗОВАТЕЛЕЙ =====
    total_users = await session.scalar(select(func.count(User.id)))
    users_today = await session.scalar(
        select(func.count(User.id)).where(User.last_active >= today_start)
    )
    users_week = await session.scalar(
        select(func.count(User.id)).where(User.last_active >= week_start)
    )
    
    # ===== СТАТИСТИКА ПИТОМЦЕВ =====
    total_pets = await session.scalar(select(func.count(Pet.id)))
    avg_level = await session.scalar(select(func.avg(Pet.level)))
    avg_level = round(avg_level or 0, 1)
    
    # ===== ЭКОНОМИКА =====
    total_coins = await session.scalar(select(func.sum(User.coins))) or 0
    total_premium = await session.scalar(select(func.sum(User.premium_currency))) or 0
    
    # ===== ОНБОРДИНГ =====
    onboarding_completed = await session.scalar(
        select(func.count(User.id)).where(User.onboarding_step >= 7)
    )
    onboarding_total = total_users or 0
    onboarding_percent = round((onboarding_completed / onboarding_total * 100) if onboarding_total > 0 else 0, 1)
    
    # ===== ТОП-5 ПО УРОВНЮ =====
    top_level = await session.execute(
        select(Pet).order_by(desc(Pet.level), desc(Pet.experience)).limit(5)
    )
    top_level = top_level.scalars().all()
    
    # ===== ТОП-5 ПО МОНЕТАМ =====
    top_coins = await session.execute(
        select(User).order_by(desc(User.coins)).limit(5)
    )
    top_coins = top_coins.scalars().all()
    
    # ===== ФОРМИРУЕМ СООБЩЕНИЕ =====
    text = "📊 <b>СТАТИСТИКА БОТА</b>\n\n"
    
    text += "👥 <b>Пользователи:</b>\n"
    text += f"   Всего: {total_users or 0}\n"
    text += f"   За день: {users_today or 0}\n"
    text += f"   За неделю: {users_week or 0}\n\n"
    
    text += "🐾 <b>Питомцы:</b>\n"
    text += f"   Всего: {total_pets or 0}\n"
    text += f"   Средний уровень: {avg_level}\n\n"
    
    text += "💰 <b>Экономика:</b>\n"
    text += f"   Всего монет: {total_coins:,.0f}\n"
    text += f"   Всего лапок: {total_premium:,.0f}\n\n"
    
    text += "🎓 <b>Онбординг:</b>\n"
    text += f"   Завершили: {onboarding_completed or 0}\n"
    text += f"   Процент: {onboarding_percent}%\n\n"
    
    # ===== КЛАВИАТУРА =====
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🏆 Топ по уровню", callback_data="admin_top_level"),
                InlineKeyboardButton(text="💰 Топ по монетам", callback_data="admin_top_coins")
            ],
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_stats"),
                InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")
            ]
        ]
    )
    
    if isinstance(event, Message):
        await event.answer(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await event.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


async def show_top_list(event: Message | CallbackQuery, session: AsyncSession, top_type: str) -> None:
    """Показать топ список"""
    if top_type == "level":
        results = await session.execute(
            select(Pet, User)
            .join(User, Pet.user_id == User.id)
            .order_by(desc(Pet.level), desc(Pet.experience))
            .limit(10)
        )
        rows = results.all()
        
        text = "🏆 <b>ТОП-10 ПО УРОВНЮ</b>\n\n"
        medals = ["🥇", "🥈", "🥉"]
        
        for i, (pet, user) in enumerate(rows, 1):
            medal = medals[i-1] if i <= 3 else f"{i}."
            emoji_map = {
                'dog': '🐶', 'cat': '🐱', 'fox': '🦊', 'wolf': '🐺',
                'rabbit': '🐰', 'bear': '🐻', 'panda': '🐼', 'lion': '🦁',
                'tiger': '🐯', 'dragon': '🐉', 'unicorn': '🦄', 'bird': '🐦',
                'penguin': '🐧', 'owl': '🦉', 'elephant': '🐘', 'monkey': '🐒'
            }
            emoji = emoji_map.get(pet.character_id, '🐾')
            text += f"{medal} {emoji} <b>{pet.name}</b>\n"
            text += f"   👤 {user.first_name or user.username}\n"
            text += f"   📊 Ур.{pet.level} | ❤️ {pet.total_likes}\n\n"
        
    elif top_type == "coins":
        results = await session.execute(
            select(User).order_by(desc(User.coins)).limit(10)
        )
        users = results.scalars().all()
        
        text = "💰 <b>ТОП-10 ПО МОНЕТАМ</b>\n\n"
        medals = ["🥇", "🥈", "🥉"]
        
        for i, user in enumerate(users, 1):
            medal = medals[i-1] if i <= 3 else f"{i}."
            text += f"{medal} <b>{user.first_name or user.username}</b>\n"
            text += f"   💰 {user.coins:,.0f} монет\n\n"
    else:
        text = "❌ Неизвестный тип топа"
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад к статистике", callback_data="admin_stats")]
        ]
    )
    
    if isinstance(event, Message):
        await event.answer(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await event.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")