"""
Handlers for progress tracking: achievements and rating.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from services.achievement_service import AchievementService
from services.social_service import SocialService
from utils.user_utils import ensure_user, ensure_pet
from utils.message_utils import delete_message
from handlers.common import get_achievement_service

router = Router()


@router.message(Command("progress"))
async def cmd_progress(message: Message, session: AsyncSession) -> None:
    """Command /progress — show achievements and rating tabs."""
    await show_progress(message, session)


async def show_progress(event: Message, session: AsyncSession) -> None:
    """Show progress with two tabs: Achievements and Rating."""
    user = await ensure_user(event, session)
    if not user:
        return
    
    pet = await ensure_pet(event, session, user)
    if not pet:
        return
    
    await show_achievements_tab(event, session, pet)


async def show_achievements_tab(event: Message | CallbackQuery, session: AsyncSession, pet) -> None:
    """Show achievements tab content."""
    data = event.bot.data if hasattr(event.bot, 'data') else {}
    achievement_service = get_achievement_service(session, data)
    
    unlocked = await achievement_service.check_all_achievements(pet.id)
    
    all_achievements = achievement_service.achievements_data
    unlocked_achievements = await achievement_service.get_unlocked_achievements(pet.id)
    unlocked_ids = [ach["id"] for ach in unlocked_achievements]
    
    total = len(all_achievements)
    unlocked_count = len(unlocked_achievements)
    
    text = f"🏆 <b>Достижения</b>\n\n"
    text += f"📊 Прогресс: {unlocked_count}/{total}\n\n"
    
    if unlocked_achievements:
        text += "✅ <b>Последние достижения:</b>\n"
        for ach in unlocked_achievements[-5:]:
            text += f"{ach['emoji']} {ach['name']}\n"
        text += "\n"
    
    locked = []
    for ach_id, ach_data in all_achievements.items():
        if ach_id not in unlocked_ids:
            locked.append(ach_data)
    
    if locked:
        text += "🔒 <b>Следующие достижения:</b>\n"
        for ach in locked[:5]:
            text += f"{ach.get('emoji', '')} {ach.get('name', ach_id)} — {ach.get('description', '')}\n"
        
        if len(locked) > 5:
            text += f"\n...и еще {len(locked) - 5} достижений"
    
    if unlocked:
        text += "\n\n🎉 <b>Новые достижения!</b>\n"
        for ach in unlocked:
            text += f"{ach['data'].get('emoji', '')} {ach['data'].get('name', '')}\n"
    
    # ЕДИНАЯ КЛАВИАТУРА
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🏆 Достижения ✅", callback_data="progress_achievements"),
                InlineKeyboardButton(text="📊 Рейтинг", callback_data="progress_rating")
            ],
            [
                InlineKeyboardButton(text="👑 Мои титулы", callback_data="progress_titles")
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")
            ]
        ]
    )
    
    if isinstance(event, CallbackQuery):
        await delete_message(event)
        await event.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, reply_markup=keyboard, parse_mode="HTML")


async def show_rating_tab(event: Message | CallbackQuery, session: AsyncSession) -> None:
    """Show rating tab content."""
    user = await ensure_user(event, session)
    if not user:
        return
    
    social_service = SocialService(session)
    result = await social_service.get_rating("level", limit=10)
    
    if not result["success"]:
        text = f"❌ {result['message']}"
        if isinstance(event, CallbackQuery):
            await delete_message(event)
            await event.message.answer(text)
            await event.answer()
        else:
            await event.answer(text)
        return
    
    text = f"📊 <b>Рейтинг</b>\n\n"
    medals = ["🥇", "🥈", "🥉"]
    
    if not result["rating"]:
        text += "Пока нет игроков в рейтинге\n"
    else:
        for i, item in enumerate(result["rating"]):
            medal = medals[i] if i < 3 else f"{i+1}."
            text += f"{medal} <b>{item['pet_name']}</b>\n"
            text += f"   👤 {item['owner_name']}\n"
            text += f"   📊 Уровень: {item['level']} | ❤️ {item['likes']}\n\n"
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🏆 Достижения", callback_data="progress_achievements"),
                InlineKeyboardButton(text="📊 Рейтинг ✅", callback_data="progress_rating")
            ],
            [
                InlineKeyboardButton(text="📊 По уровню ✅", callback_data="progress_rating_level"),
                InlineKeyboardButton(text="❤️ По лайкам", callback_data="progress_rating_likes")
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")
            ]
        ]
    )
    
    if isinstance(event, CallbackQuery):
        await delete_message(event)
        await event.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "progress_achievements")
async def progress_achievements_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Switch to achievements tab."""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    await delete_message(callback)
    await show_achievements_tab(callback, session, pet)
    await callback.answer()


@router.callback_query(F.data == "progress_rating")
async def progress_rating_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Switch to rating tab."""
    await delete_message(callback)
    await show_rating_tab(callback, session)
    await callback.answer()


@router.callback_query(F.data == "progress_rating_level")
async def progress_rating_level(callback: CallbackQuery, session: AsyncSession) -> None:
    """Show rating by level."""
    await delete_message(callback)
    
    social_service = SocialService(session)
    result = await social_service.get_rating("level", limit=10)
    
    if not result["success"]:
        await callback.message.answer(f"❌ {result['message']}")
        await callback.answer()
        return
    
    text = f"📊 <b>Рейтинг по уровню</b>\n\n"
    medals = ["🥇", "🥈", "🥉"]
    
    if not result["rating"]:
        text += "Пока нет игроков в рейтинге\n"
    else:
        for i, item in enumerate(result["rating"]):
            medal = medals[i] if i < 3 else f"{i+1}."
            text += f"{medal} <b>{item['pet_name']}</b>\n"
            text += f"   👤 {item['owner_name']}\n"
            text += f"   📊 Уровень: {item['level']} | ❤️ {item['likes']}\n\n"
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🏆 Достижения", callback_data="progress_achievements"),
                InlineKeyboardButton(text="📊 Рейтинг ✅", callback_data="progress_rating")
            ],
            [
                InlineKeyboardButton(text="📊 По уровню ✅", callback_data="progress_rating_level"),
                InlineKeyboardButton(text="❤️ По лайкам", callback_data="progress_rating_likes")
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")
            ]
        ]
    )
    
    await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "progress_rating_likes")
async def progress_rating_likes(callback: CallbackQuery, session: AsyncSession) -> None:
    """Show rating by likes."""
    await delete_message(callback)
    
    social_service = SocialService(session)
    result = await social_service.get_rating("likes", limit=10)
    
    if not result["success"]:
        await callback.message.answer(f"❌ {result['message']}")
        await callback.answer()
        return
    
    text = f"❤️ <b>Рейтинг по лайкам</b>\n\n"
    medals = ["🥇", "🥈", "🥉"]
    
    if not result["rating"]:
        text += "Пока нет игроков в рейтинге\n"
    else:
        for i, item in enumerate(result["rating"]):
            medal = medals[i] if i < 3 else f"{i+1}."
            text += f"{medal} <b>{item['pet_name']}</b>\n"
            text += f"   👤 {item['owner_name']}\n"
            text += f"   📊 Уровень: {item['level']} | ❤️ {item['likes']}\n\n"
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🏆 Достижения", callback_data="progress_achievements"),
                InlineKeyboardButton(text="📊 Рейтинг ✅", callback_data="progress_rating")
            ],
            [
                InlineKeyboardButton(text="📊 По уровню", callback_data="progress_rating_level"),
                InlineKeyboardButton(text="❤️ По лайкам ✅", callback_data="progress_rating_likes")
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")
            ]
        ]
    )
    
    await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "progress_titles")
async def progress_titles(callback: CallbackQuery, session: AsyncSession) -> None:
    """Show titles from progress tab."""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    data = callback.bot.data if hasattr(callback.bot, 'data') else {}
    achievement_service = get_achievement_service(session, data)
    titles = await achievement_service.get_available_titles(pet)
    
    text = "👑 <b>Титулы</b>\n\n"
    text += "Выбери титул, который будет отображаться в профиле:\n\n"
    
    keyboard = []
    
    for title in titles:
        status = "✅" if title["is_active"] else "⬜"
        text += f"{status} {title['emoji']} {title['name']}\n"
        text += f"   {title['description']}\n\n"
        
        if not title["is_active"]:
            keyboard.append([
                InlineKeyboardButton(
                    text=f"👑 {title['emoji']} {title['name']}",
                    callback_data=f"progress_set_title_{title['id']}"
                )
            ])
    
    keyboard.append([InlineKeyboardButton(text="🔙 Назад к достижениям", callback_data="progress_achievements")])
    
    await delete_message(callback)
    await callback.message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("progress_set_title_"))
async def progress_set_title(callback: CallbackQuery, session: AsyncSession) -> None:
    """Set title from progress tab."""
    title_id = callback.data.split("_", 3)[3]
    
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    data = callback.bot.data if hasattr(callback.bot, 'data') else {}
    achievement_service = get_achievement_service(session, data)
    success = await achievement_service.set_title(pet.id, title_id)
    
    if success:
        await callback.answer("✅ Титул установлен!", show_alert=True)
        await progress_titles(callback, session)
    else:
        await callback.answer("❌ Титул недоступен", show_alert=True)