from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from keyboards.main_menu import get_main_menu_keyboard, get_main_menu_keyboard_sync
from utils.user_utils import ensure_user
from utils.message_utils import send_or_edit, delete_message

router = Router()


@router.message(Command("menu"))
async def cmd_menu(message: Message) -> None:
    """Команда /menu - главное меню"""
    await message.answer(
        "🏠 <b>Главное меню</b>\n\n"
        "Выбери действие:",
        reply_markup=get_main_menu_keyboard_sync(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Callback для возврата в главное меню"""
    user = await ensure_user(callback, session)
    if not user:
        return
    await delete_message(callback)
    keyboard = await get_main_menu_keyboard(session, callback.from_user.id)
    await callback.message.answer(
        "🏠 <b>Главное меню</b>\n\n"
        "Выбери действие:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


# ===== СТАНДАРТНЫЕ КНОПКИ =====

@router.callback_query(F.data == "profile")
async def menu_profile(callback: CallbackQuery, session: AsyncSession) -> None:
    from handlers.profile import show_profile_from_callback
    await show_profile_from_callback(callback, session)


@router.callback_query(F.data == "eat")
async def menu_eat(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    from handlers.food import cmd_eat_from_callback
    await cmd_eat_from_callback(callback, session, state)


@router.callback_query(F.data == "shop")
async def menu_shop(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Кнопка Магазин в главном меню"""
    from handlers.shop import show_shop_main
    await show_shop_main(callback, session, state)


@router.callback_query(F.data == "inventory")
async def menu_inventory(callback: CallbackQuery, session: AsyncSession) -> None:
    from handlers.inventory import cmd_inventory_from_callback
    await cmd_inventory_from_callback(callback, session)


@router.callback_query(F.data == "adventures")
async def menu_adventures(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    from handlers.adventure import show_locations_from_callback
    await show_locations_from_callback(callback, session, state)


@router.callback_query(F.data == "house")
async def menu_house(callback: CallbackQuery, session: AsyncSession) -> None:
    from handlers.house import house_main
    await house_main(callback, session)


@router.callback_query(F.data == "chat")
async def menu_chat(callback: CallbackQuery, session: AsyncSession) -> None:
    from handlers.chat import chat_callback
    await chat_callback(callback, session)


@router.callback_query(F.data == "mailbox")
async def menu_mailbox(callback: CallbackQuery, session: AsyncSession) -> None:
    from handlers.mailbox import show_mailbox
    await show_mailbox(callback, session)


@router.callback_query(F.data == "achievements")
async def menu_achievements(callback: CallbackQuery, session: AsyncSession) -> None:
    from handlers.achievements import cmd_achievements_from_callback
    await cmd_achievements_from_callback(callback, session)


@router.callback_query(F.data == "rating")
async def menu_rating(callback: CallbackQuery, session: AsyncSession) -> None:
    from handlers.rating import show_rating_from_callback
    await show_rating_from_callback(callback, session, "level")


@router.callback_query(F.data == "daily")
async def menu_daily(callback: CallbackQuery, session: AsyncSession) -> None:
    """Callback для кнопки 'Ежедневное'"""
    from handlers.daily import show_daily_main
    await show_daily_main(callback, session)
    await callback.answer()


@router.callback_query(F.data == "quests")
async def menu_quests(callback: CallbackQuery, session: AsyncSession) -> None:
    """Callback для кнопки 'Задания' (перенаправляет в ежедневное)"""
    from handlers.daily import show_daily_quests_tab
    await show_daily_quests_tab(callback, session)
    await callback.answer()


@router.callback_query(F.data == "my_photos")
async def menu_my_photos(callback: CallbackQuery, session: AsyncSession) -> None:
    from handlers.photos import my_photos_callback
    await my_photos_callback(callback, session)


@router.callback_query(F.data == "progress")
async def menu_progress(callback: CallbackQuery, session: AsyncSession) -> None:
    """Кнопка Прогресс"""
    user = await ensure_user(callback, session)
    if not user:
        return
    await delete_message(callback)
    from handlers.progress import show_progress
    await show_progress(callback, session)


@router.callback_query(F.data == "competition")
async def menu_competition(callback: CallbackQuery, session: AsyncSession) -> None:
    from handlers.competition import callback_competition
    await callback_competition(callback, session)


@router.callback_query(F.data == "feed")
async def menu_feed(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Кнопка Лента"""
    from handlers.feed import feed_callback
    await feed_callback(callback, state, session)


@router.callback_query(F.data == "notifications")
async def menu_notifications(callback: CallbackQuery, session: AsyncSession) -> None:
    """Кнопка Уведомления"""
    from handlers.notifications import notifications_callback
    await notifications_callback(callback, session)


@router.callback_query(F.data == "help")
async def menu_help(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await ensure_user(callback, session)
    if not user:
        return
    keyboard = await get_main_menu_keyboard(session, callback.from_user.id)
    await send_or_edit(
        callback,
        text="ℹ️ <b>Помощь</b>\n\n"
             "📋 <b>Доступные команды:</b>\n"
             "/start - Главное меню\n"
             "/profile - Профиль питомца\n"
             "/eat - Покормить питомца\n"
             "/shop - Магазин\n"
             "/inventory - Инвентарь\n"
             "/adventure - Приключения\n"
             "/achievements - Достижения\n"
             "/daily - Ежедневное\n"
             "/rating - Рейтинг\n"
             "/photos - Альбом фото\n"
             "/house - Дом\n"
             "/view @username - Профиль игрока\n"
             "/menu - Главное меню\n\n"
             "🐾 <b>Игра «Питомцы: Большой Жор»</b>\n"
             "Создай своего питомца и отправляйся в приключения! 🚀",
        reply_markup=keyboard
    )
    await callback.answer()


# ===== УДАЛЯЕМ КНОПКУ RANDOM_PET (ОНА НЕ ИСПОЛЬЗУЕТСЯ) =====
# Убрал обработчик random_pet, так как кнопки в меню больше нет