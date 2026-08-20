import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from services.data_loader import data_loader
from utils.user_utils import ensure_user, ensure_pet
from utils.message_utils import send_or_edit, delete_message
from keyboards.main_menu import get_main_menu_keyboard
from keyboards.adventure import (
    get_locations_keyboard,
    get_adventure_confirm_keyboard,
    get_adventure_status_keyboard
)
from handlers.common import get_adventure_service

logger = logging.getLogger(__name__)
router = Router()


class AdventureStates(StatesGroup):
    """Состояния для приключений"""
    choosing_location = State()
    adventure_in_progress = State()


@router.message(Command("adventure"))
async def cmd_adventure(message: Message, session: AsyncSession, state: FSMContext) -> None:
    """Команда /adventure — приключения"""
    await show_locations(message, session, state)


async def show_locations(message: Message, session: AsyncSession, state: FSMContext) -> None:
    """Показать доступные локации (из сообщения)"""
    user = await ensure_user(message, session)
    if not user:
        return
    
    pet = await ensure_pet(message, session, user)
    if not pet:
        return
    
    data = message.bot.data if hasattr(message.bot, 'data') else {}
    adventure_service = get_adventure_service(session, data)
    
    await adventure_service.recover_energy(pet)
    
    locations = await adventure_service.get_available_locations(pet.level)
    
    if not locations:
        await message.answer(
            "🌍 Пока нет доступных локаций.\n"
            "Прокачай уровень, чтобы открыть новые места!",
            reply_markup=await get_main_menu_keyboard()
        )
        return
    
    keyboard = get_locations_keyboard(locations, pet)
    
    hunger_emoji = "😊"
    hunger_percent = pet.get_hunger_percent()
    if hunger_percent >= 150:
        hunger_emoji = "💀"
    elif hunger_percent >= 120:
        hunger_emoji = "🤢"
    elif hunger_percent >= 100:
        hunger_emoji = "😋"
    
    await message.answer(
        f"⚔️ <b>Приключения</b>\n\n"
        f"🐾 <b>Питомец:</b> {pet.name}\n"
        f"📊 <b>Уровень:</b> {pet.level}\n"
        f"⚡ <b>Энергия:</b> {pet.energy}/100\n"
        f"{hunger_emoji} <b>Сытость:</b> {hunger_percent:.0f}%\n\n"
        f"🌍 <b>Выбери локацию:</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await state.set_state(AdventureStates.choosing_location)


async def show_locations_from_callback(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    """Показать доступные локации (из callback)"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    data = callback.bot.data if hasattr(callback.bot, 'data') else {}
    adventure_service = get_adventure_service(session, data)
    
    await adventure_service.recover_energy(pet)
    
    locations = await adventure_service.get_available_locations(pet.level)
    
    if not locations:
        await send_or_edit(
            callback,
            text="🌍 Пока нет доступных локаций.\n"
                 "Прокачай уровень, чтобы открыть новые места!",
            reply_markup=await get_main_menu_keyboard()
        )
        return
    
    keyboard = get_locations_keyboard(locations, pet)
    
    hunger_emoji = "😊"
    hunger_percent = pet.get_hunger_percent()
    if hunger_percent >= 150:
        hunger_emoji = "💀"
    elif hunger_percent >= 120:
        hunger_emoji = "🤢"
    elif hunger_percent >= 100:
        hunger_emoji = "😋"
    
    await send_or_edit(
        callback,
        text=f"⚔️ <b>Приключения</b>\n\n"
             f"🐾 <b>Питомец:</b> {pet.name}\n"
             f"📊 <b>Уровень:</b> {pet.level}\n"
             f"⚡ <b>Энергия:</b> {pet.energy}/100\n"
             f"{hunger_emoji} <b>Сытость:</b> {hunger_percent:.0f}%\n\n"
             f"🌍 <b>Выбери локацию:</b>",
        reply_markup=keyboard
    )
    
    await state.set_state(AdventureStates.choosing_location)
    await callback.answer()


@router.callback_query(AdventureStates.choosing_location, F.data.startswith("adv_location_"))
async def adventure_location(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Выбор локации для приключения"""
    location_id = callback.data.split("_", 2)[2]
    
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    data = callback.bot.data if hasattr(callback.bot, 'data') else {}
    adventure_service = get_adventure_service(session, data)
    
    location = adventure_service.locations.get(location_id, {})
    energy_cost = location.get("energy_cost", 10)
    
    if pet.energy < energy_cost:
        await send_or_edit(
            callback,
            text=f"⚡ Недостаточно энергии!\n"
                 f"Нужно: {energy_cost}, у тебя: {pet.energy}\n\n"
                 f"Подожди, энергия восстановится сама.",
            reply_markup=await get_main_menu_keyboard()
        )
        return
    
    hunger_percent = pet.get_hunger_percent()
    if hunger_percent >= 150:
        await send_or_edit(
            callback,
            text="💀 Питомец в катастрофическом состоянии!\n"
                 "Нужно подождать, пока он переварит еду.",
            reply_markup=await get_main_menu_keyboard()
        )
        return
    
    keyboard = get_adventure_confirm_keyboard(location_id)
    
    await send_or_edit(
        callback,
        text=f"🗺️ <b>{location.get('emoji', '')} {location.get('name', location_id)}</b>\n\n"
             f"⏳ Время: {location.get('duration', 60)} сек.\n"
             f"⚡ Энергия: -{energy_cost}\n"
             f"📊 Уровень: {location.get('min_level', 0)}\n\n"
             f"<i>{location.get('description', 'Отправь питомца в приключение!')}</i>\n\n"
             f"Отправить питомца в приключение?",
        reply_markup=keyboard
    )
    await callback.answer()


# ===== КНОПКА "НАЗАД" ПРИ ВЫБОРЕ ЛОКАЦИИ =====
@router.callback_query(AdventureStates.choosing_location, F.data == "adv_back")
async def adventure_back(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Вернуться в главное меню из выбора локации"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    await state.clear()
    
    keyboard = await get_main_menu_keyboard(session, callback.from_user.id)
    
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    await callback.message.answer(
        "🏠 <b>Главное меню</b>\n\n"
        "Выбери действие:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


# ===== КНОПКА "НАЗАД" ПРИ ПОДТВЕРЖДЕНИИ =====
@router.callback_query(AdventureStates.choosing_location, F.data == "adv_confirm_back")
async def adv_confirm_back(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Вернуться к выбору локации из подтверждения"""
    await show_locations_from_callback(callback, session, state)
    await callback.answer()


# ===== ЗАБЛОКИРОВАННАЯ ЛОКАЦИЯ =====
@router.callback_query(F.data == "adv_locked")
async def adv_locked(callback: CallbackQuery) -> None:
    """Обработчик для заблокированных локаций"""
    await callback.answer("🔒 Эта локация ещё не доступна. Повысь уровень!", show_alert=True)


@router.callback_query(F.data.startswith("adv_confirm_"))
async def adventure_confirm(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Подтверждение начала приключения"""
    location_id = callback.data.split("_", 2)[2]
    
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    data = callback.bot.data if hasattr(callback.bot, 'data') else {}
    adventure_service = get_adventure_service(session, data)
    
    result = await adventure_service.start_adventure(
        user_id=callback.from_user.id,
        pet_id=pet.id,
        location_id=location_id
    )
    
    if not result["success"]:
        await send_or_edit(
            callback,
            text=f"❌ {result['message']}",
            reply_markup=await get_main_menu_keyboard()
        )
        return
    
    duration = result.get("duration", 60)
    adventure_id = result["adventure_id"]
    
    location = adventure_service.locations.get(location_id, {})
    location_name = location.get("name", location_id)
    location_emoji = location.get("emoji", "🗺️")
    
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    start_message = await callback.bot.send_message(
        chat_id=callback.message.chat.id,
        text=
        f"{location_emoji} <b>Питомец ушёл в приключение!</b>\n\n"
        f"📍 {location_name}\n"
        f"⏳ Длительность: {duration} сек.\n\n"
        f"<i>Питомец отправился в путь, жди результатов...</i>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🏠 В главное меню", callback_data="main_menu")]
            ]
        ),
        parse_mode="HTML"
    )
    
    await state.update_data(
        adventure_id=adventure_id,
        location_id=location_id,
        duration=duration,
        start_message_id=start_message.message_id,
        chat_id=callback.message.chat.id
    )
    await state.set_state(AdventureStates.adventure_in_progress)
    
    from tasks.adventure_completion import schedule_adventure_completion
    
    await schedule_adventure_completion(
        bot=callback.bot,
        user_id=callback.from_user.id,
        pet_id=pet.id,
        adventure_id=adventure_id,
        location_id=location_id,
        duration=duration,
        chat_id=callback.message.chat.id,
        message_id=start_message.message_id,
        session=session,
        data=data
    )
    
    await callback.answer("Питомец отправился в приключение! ⚔️")


@router.callback_query(AdventureStates.adventure_in_progress, F.data.startswith("adv_status_"))
async def adventure_status(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Проверка статуса приключения"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    data_state = await state.get_data()
    adventure_id = data_state.get("adventure_id")
    start_message_id = data_state.get("start_message_id")
    stored_chat_id = data_state.get("chat_id")
    
    chat_id = stored_chat_id if stored_chat_id else callback.message.chat.id
    
    if not adventure_id:
        await callback.answer("❌ Приключение не найдено")
        await send_or_edit(
            callback,
            text="❌ Приключение не найдено",
            reply_markup=await get_main_menu_keyboard()
        )
        return
    
    data = callback.bot.data if hasattr(callback.bot, 'data') else {}
    adventure_service = get_adventure_service(session, data)
    
    result = await adventure_service.check_adventure_by_id(adventure_id)
    
    if result["success"]:
        await state.clear()
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⚔️ Новое приключение", callback_data="adventure_new")],
                [InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")]
            ]
        )
        
        if start_message_id:
            try:
                await callback.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=start_message_id,
                    text=f"✅ <b>Приключение завершено!</b>\n\n{result['message']}",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                try:
                    await callback.message.delete()
                except Exception:
                    pass
            except Exception as e:
                logger.warning(f"Не удалось отредактировать сообщение {start_message_id}: {e}")
                try:
                    await callback.bot.send_message(
                        chat_id=chat_id,
                        text=f"✅ <b>Приключение завершено!</b>\n\n{result['message']}",
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                    try:
                        await callback.message.delete()
                    except Exception:
                        pass
                except Exception as e2:
                    logger.error(f"Не удалось отправить новое сообщение: {e2}")
                    await callback.answer("✅ Приключение завершено! Проверь награды в меню.")
        else:
            try:
                await callback.bot.send_message(
                    chat_id=chat_id,
                    text=f"✅ <b>Приключение завершено!</b>\n\n{result['message']}",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                await callback.message.delete()
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение: {e}")
                await send_or_edit(
                    callback,
                    text=f"✅ <b>Приключение завершено!</b>\n\n{result['message']}",
                    reply_markup=keyboard
                )
    else:
        if result.get("completed", False):
            await state.clear()
            await send_or_edit(
                callback,
                text="✅ Приключение уже завершено",
                reply_markup=await get_main_menu_keyboard()
            )
        else:
            remaining = result.get("remaining_seconds", 0)
            keyboard = get_adventure_status_keyboard(adventure_id)
            
            if start_message_id:
                try:
                    await callback.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=start_message_id,
                        text=f"⏳ <b>Приключение в процессе...</b>\n\n"
                             f"Осталось: {remaining} сек.\n"
                             f"Жди завершения!",
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                    try:
                        await callback.message.delete()
                    except Exception:
                        pass
                except Exception as e:
                    logger.warning(f"Не удалось отредактировать сообщение {start_message_id}: {e}")
                    try:
                        await callback.bot.send_message(
                            chat_id=chat_id,
                            text=f"⏳ <b>Приключение в процессе...</b>\n\n"
                                 f"Осталось: {remaining} сек.\n"
                                 f"Жди завершения!",
                            reply_markup=keyboard,
                            parse_mode="HTML"
                        )
                        try:
                            await callback.message.delete()
                        except Exception:
                            pass
                    except Exception as e2:
                        logger.error(f"Не удалось отправить новое сообщение: {e2}")
                        await send_or_edit(
                            callback,
                            text=f"⏳ <b>Приключение в процессе...</b>\n\n"
                                 f"Осталось: {remaining} сек.\n"
                                 f"Жди завершения!",
                            reply_markup=keyboard
                        )
            else:
                try:
                    await callback.bot.send_message(
                        chat_id=chat_id,
                        text=f"⏳ <b>Приключение в процессе...</b>\n\n"
                             f"Осталось: {remaining} сек.\n"
                             f"Жди завершения!",
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                    await callback.message.delete()
                except Exception as e:
                    logger.error(f"Не удалось отправить сообщение: {e}")
                    await send_or_edit(
                        callback,
                        text=f"⏳ <b>Приключение в процессе...</b>\n\n"
                             f"Осталось: {remaining} сек.\n"
                             f"Жди завершения!",
                        reply_markup=keyboard
                    )
    
    await callback.answer()


@router.callback_query(F.data == "adventure_new")
async def adventure_new(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Новое приключение"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    await state.clear()
    await show_locations_from_callback(callback, session, state)


@router.callback_query(F.data == "adventures")
async def adventures_callback(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Callback для кнопки 'Приключения'"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    await state.clear()
    await show_locations_from_callback(callback, session, state)