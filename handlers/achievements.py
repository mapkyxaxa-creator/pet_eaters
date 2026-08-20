from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories.user_repository import UserRepository
from database.repositories.pet_repository import PetRepository
from services.achievement_service import AchievementService
from services.data_loader import data_loader
from utils.user_utils import ensure_user, ensure_pet
from utils.message_utils import send_or_edit, delete_message
from keyboards.main_menu import get_main_menu_keyboard_sync
from handlers.common import get_achievement_service

router = Router()


@router.message(Command("achievements"))
async def cmd_achievements(message: Message, session: AsyncSession) -> None:
    """Команда /achievements — достижения"""
    await show_achievements(message, session)


async def show_achievements(event: Message, session: AsyncSession) -> None:
    """Показать достижения"""
    user = await ensure_user(event, session)
    if not user:
        return
    
    pet = await ensure_pet(event, session, user)
    if not pet:
        return
    
    # Получаем данные из workflow
    data = event.bot.data if hasattr(event.bot, 'data') else {}
    achievement_service = get_achievement_service(session, data)
    
    # Проверяем новые достижения
    unlocked = await achievement_service.check_all_achievements(pet.id)
    
    # Получаем список всех достижений
    all_achievements = achievement_service.achievements_data
    unlocked_achievements = await achievement_service.get_unlocked_achievements(pet.id)
    unlocked_ids = [ach["id"] for ach in unlocked_achievements]
    
    # Формируем сообщение
    total = len(all_achievements)
    unlocked_count = len(unlocked_achievements)
    
    text = f"🏆 <b>Достижения</b>\n\n"
    text += f"📊 Прогресс: {unlocked_count}/{total}\n\n"
    
    # Показываем последние 5 разблокированных
    if unlocked_achievements:
        text += "✅ <b>Последние достижения:</b>\n"
        for ach in unlocked_achievements[-5:]:
            text += f"{ach['emoji']} {ach['name']}\n"
        text += "\n"
    
    # Показываем недоступные (первые 5)
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
    
    # Если есть новые достижения
    if unlocked:
        text += "\n\n🎉 <b>Новые достижения!</b>\n"
        for ach in unlocked:
            text += f"{ach['data'].get('emoji', '')} {ach['data'].get('name', '')}\n"
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👑 Мои титулы", callback_data="titles")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
        ]
    )
    
    await event.answer(text, reply_markup=keyboard, parse_mode="HTML")


async def cmd_achievements_from_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Обертка для вызова cmd_achievements из callback"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    await delete_message(callback)
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    # Получаем данные из workflow
    data = callback.bot.data if hasattr(callback.bot, 'data') else {}
    achievement_service = get_achievement_service(session, data)
    
    # Проверяем новые достижения
    unlocked = await achievement_service.check_all_achievements(pet.id)
    
    # Получаем список всех достижений
    all_achievements = achievement_service.achievements_data
    unlocked_achievements = await achievement_service.get_unlocked_achievements(pet.id)
    unlocked_ids = [ach["id"] for ach in unlocked_achievements]
    
    # Формируем сообщение
    total = len(all_achievements)
    unlocked_count = len(unlocked_achievements)
    
    text = f"🏆 <b>Достижения</b>\n\n"
    text += f"📊 Прогресс: {unlocked_count}/{total}\n\n"
    
    # Показываем последние 5 разблокированных
    if unlocked_achievements:
        text += "✅ <b>Последние достижения:</b>\n"
        for ach in unlocked_achievements[-5:]:
            text += f"{ach['emoji']} {ach['name']}\n"
        text += "\n"
    
    # Показываем недоступные (первые 5)
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
    
    # Если есть новые достижения
    if unlocked:
        text += "\n\n🎉 <b>Новые достижения!</b>\n"
        for ach in unlocked:
            text += f"{ach['data'].get('emoji', '')} {ach['data'].get('name', '')}\n"
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👑 Мои титулы", callback_data="titles")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
        ]
    )
    
    await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "titles")
async def show_titles(callback: CallbackQuery, session: AsyncSession) -> None:
    """Показать доступные титулы"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    # Получаем данные из workflow
    data = callback.bot.data if hasattr(callback.bot, 'data') else {}
    achievement_service = get_achievement_service(session, data)
    titles = await achievement_service.get_available_titles(pet)
    
    text = "👑 <b>Титулы</b>\n\n"
    text += "Выбери титул, который будет отображаться в профиле:\n\n"
    
    keyboard = []
    
    for title in titles:
        status = "✅" if title["is_active"] else "⬜"
        text += f"{status} {title['emoji']} {title['name']}\n"
        text += f"   {title['description']}\n"
        
        if not title["is_active"]:
            keyboard.append([
                InlineKeyboardButton(
                    text=f"👑 {title['emoji']} {title['name']}",
                    callback_data=f"set_title_{title['id']}"
                )
            ])
    
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="achievements_back")])
    
    await send_or_edit(
        callback,
        text=text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set_title_"))
async def set_title(callback: CallbackQuery, session: AsyncSession) -> None:
    """Установить титул"""
    title_id = callback.data.split("_", 2)[2]
    
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    # Получаем данные из workflow
    data = callback.bot.data if hasattr(callback.bot, 'data') else {}
    achievement_service = get_achievement_service(session, data)
    success = await achievement_service.set_title(pet.id, title_id)
    
    if success:
        await callback.answer("✅ Титул установлен!", show_alert=True)
        await show_titles(callback, session)
    else:
        await callback.answer("❌ Титул недоступен", show_alert=True)


@router.callback_query(F.data == "achievements_back")
async def achievements_back(callback: CallbackQuery, session: AsyncSession) -> None:
    """Возврат к достижениям"""
    await delete_message(callback)
    await cmd_achievements_from_callback(callback, session)
    await callback.answer()


@router.callback_query(F.data == "achievements")
async def achievements_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Callback для кнопки 'Достижения'"""
    await cmd_achievements_from_callback(callback, session)