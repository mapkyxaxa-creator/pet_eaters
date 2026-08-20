import logging
from typing import Optional
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories.user_repository import UserRepository
from database.repositories.pet_repository import PetRepository
from services.moderation_service import ModerationService
from services.photo_service import PhotoService
from services.feed_service import FeedService
from keyboards.moderation import (
    get_moderation_main_keyboard,
    get_moderation_list_keyboard,
    get_moderation_photo_keyboard,
    get_moderation_approve_keyboard,
    get_moderation_reject_keyboard,
    get_moderation_success_keyboard,
    get_moderation_empty_keyboard
)
from utils.user_utils import ensure_user
from utils.message_utils import send_or_edit, delete_message
from config import config

logger = logging.getLogger(__name__)
router = Router()

ADMIN_IDS = config.ADMIN_IDS


def is_admin(user_id: int) -> bool:
    """Проверить, является ли пользователь админом"""
    result = user_id in ADMIN_IDS
    logger.info(f"🔍 Проверка админа: user_id={user_id}, ADMIN_IDS={ADMIN_IDS}, result={result}")
    return result


@router.message(Command("moderation"))
async def cmd_moderation(message: Message, session: AsyncSession) -> None:
    """Команда /moderation - панель модерации"""
    user_id = message.from_user.id
    
    logger.info(f"📸 Команда /moderation от user_id={user_id}")
    logger.info(f"📸 ADMIN_IDS={ADMIN_IDS}")
    
    if not is_admin(user_id):
        await message.answer("❌ У вас нет доступа к панели модерации.")
        return
    
    await show_moderation_panel(message, session)


@router.callback_query(F.data == "moderation")
async def moderation_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Callback для кнопки модерации"""
    user_id = callback.from_user.id
    
    logger.info(f"📸 Callback moderation от user_id={user_id}")
    logger.info(f"📸 ADMIN_IDS={ADMIN_IDS}")
    
    if not is_admin(user_id):
        await callback.answer("❌ У вас нет доступа.", show_alert=True)
        return
    
    await delete_message(callback)
    await show_moderation_panel(callback, session)
    await callback.answer()


@router.callback_query(F.data == "moderation_main")
async def moderation_main_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Callback для возврата в главное меню модерации"""
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ У вас нет доступа.", show_alert=True)
        return
    
    await delete_message(callback)
    await show_moderation_panel(callback, session)
    await callback.answer()


@router.callback_query(F.data == "moderation_refresh")
async def moderation_refresh_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Callback для обновления панели модерации"""
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ У вас нет доступа.", show_alert=True)
        return
    
    await delete_message(callback)
    await show_moderation_panel(callback, session)
    await callback.answer()


async def show_moderation_panel(event: Message | CallbackQuery, session: AsyncSession) -> None:
    """Показать панель модерации"""
    moderation_service = ModerationService(session)
    pending_count = await moderation_service.get_pending_count()
    
    text = (
        "📸 <b>Панель модерации</b>\n\n"
        f"📊 На модерации: <b>{pending_count}</b> фото\n\n"
        "Выбери действие:"
    )
    
    keyboard = get_moderation_main_keyboard()
    
    await send_or_edit(event, text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "moderation_list")
async def moderation_list_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Callback для списка фото на модерации"""
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ У вас нет доступа.", show_alert=True)
        return
    
    await show_moderation_list(callback, session, page=0)
    await callback.answer()


@router.callback_query(F.data.startswith("moderation_page_"))
async def moderation_page_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Callback для пагинации списка модерации"""
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ У вас нет доступа.", show_alert=True)
        return
    
    page = int(callback.data.split("_")[2])
    await show_moderation_list(callback, session, page)
    await callback.answer()


async def show_moderation_list(event: Message | CallbackQuery, session: AsyncSession, page: int = 0) -> None:
    """Показать список фото на модерации"""
    moderation_service = ModerationService(session)
    
    pending_photos = await moderation_service.get_pending_photos(limit=20)
    total = len(pending_photos)
    
    if not pending_photos:
        text = (
            "📸 <b>Модерация</b>\n\n"
            "✅ Нет фото на модерации!\n"
            "Все фото проверены."
        )
        keyboard = get_moderation_empty_keyboard()
        await send_or_edit(event, text, reply_markup=keyboard, parse_mode="HTML")
        return
    
    per_page = 5
    start_idx = page * per_page
    end_idx = min(start_idx + per_page, total)
    page_photos = pending_photos[start_idx:end_idx]
    
    text = (
        f"📸 <b>Фото на модерации</b>\n\n"
        f"Всего: <b>{total}</b> фото\n"
        f"Страница: {page + 1}/{max(1, (total + per_page - 1) // per_page)}\n\n"
    )
    
    for idx, item in enumerate(page_photos, start=start_idx + 1):
        photo = item["photo"]
        pet = item["pet"]
        user = item["user"]
        
        pet_name = pet.name if pet else "Без имени"
        owner_name = user.first_name or user.username or "Пользователь"
        created_at = photo.created_at.strftime("%d.%m.%Y %H:%M")
        
        text += (
            f"<b>{idx}.</b> 🐾 {pet_name}\n"
            f"   👤 @{owner_name}\n"
            f"   🕐 {created_at}\n"
            f"   📝 {photo.caption or 'Без описания'}\n\n"
        )
    
    keyboard = get_moderation_list_keyboard(page_photos, page, total)
    await send_or_edit(event, text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("moderation_view_"))
async def moderation_view_callback(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    """Callback для просмотра фото на модерации"""
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ У вас нет доступа.", show_alert=True)
        return
    
    photo_id = int(callback.data.split("_")[2])
    
    moderation_service = ModerationService(session)
    photo_details = await moderation_service.get_photo_details(photo_id)
    
    if not photo_details:
        await callback.answer("❌ Фото не найдено или уже проверено", show_alert=True)
        await show_moderation_panel(callback, session)
        return
    
    photo = photo_details["photo"]
    pet = photo_details["pet"]
    user = photo_details["user"]
    
    text = (
        f"📸 <b>Модерация фото</b>\n\n"
        f"🐾 <b>Питомец:</b> {pet.name}\n"
        f"👤 <b>Владелец:</b> {user.first_name or user.username or 'Пользователь'}\n"
        f"🆔 <b>ID владельца:</b> {user.telegram_id}\n"
        f"📝 <b>Описание:</b> {photo.caption or 'Без описания'}\n"
        f"🕐 <b>Отправлено:</b> {photo.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"<a href='tg://user?id={user.telegram_id}'>Перейти к пользователю</a>"
    )
    
    keyboard = get_moderation_photo_keyboard(photo_id)
    
    try:
        await delete_message(callback)
        await callback.message.answer_photo(
            photo=photo.telegram_file_id,
            caption=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Ошибка отправки фото на модерацию: {e}")
        await callback.message.answer(
            f"❌ Не удалось загрузить фото\n\n{text}",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    
    await callback.answer()


@router.callback_query(F.data.startswith("moderation_approve_"))
async def moderation_approve_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Callback для одобрения фото"""
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ У вас нет доступа.", show_alert=True)
        return
    
    parts = callback.data.split("_")
    
    if len(parts) >= 3 and parts[2] == "confirm":
        if len(parts) >= 4:
            photo_id = int(parts[3])
            await moderation_approve_confirm_callback(callback, session, photo_id)
        return
    
    if len(parts) >= 3:
        try:
            photo_id = int(parts[2])
        except ValueError:
            await callback.answer("❌ Ошибка: неверный формат", show_alert=True)
            return
    else:
        await callback.answer("❌ Ошибка: неверный формат", show_alert=True)
        return
    
    keyboard = get_moderation_approve_keyboard(photo_id)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


async def moderation_approve_confirm_callback(callback: CallbackQuery, session: AsyncSession, photo_id: int) -> None:
    """Подтверждение одобрения фото"""
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ У вас нет доступа.", show_alert=True)
        return
    
    bot = callback.bot
    
    moderation_service = ModerationService(session)
    result = await moderation_service.approve_photo(photo_id, user_id)
    
    if result["success"]:
        photo = result["photo"]
        
        pet_repo = PetRepository(session)
        pet = await pet_repo.get_by_id(photo.pet_id)
        
        user_repo = UserRepository(session)
        owner = await user_repo.get_by_id(pet.user_id) if pet else None
        
        if pet and owner:
            try:
                feed_service = FeedService(session)
                await feed_service.create_post(
                    pet_id=pet.id,
                    photo_id=photo.id,
                    caption=photo.caption,
                    is_published=True
                )
                logger.info(f"Создан пост из одобренного фото {photo_id}")
            except Exception as e:
                logger.error(f"Ошибка создания поста из фото {photo_id}: {e}")
        
        if owner:
            try:
                await bot.send_message(
                    chat_id=owner.telegram_id,
                    text=(
                        f"✅ <b>Ваше фото одобрено!</b>\n\n"
                        f"🐾 Питомец: {pet.name}\n"
                        f"📸 Фото добавлено в альбом и ленту!\n\n"
                        f"Спасибо за участие! 🌟"
                    ),
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить владельца {owner.telegram_id}: {e}")
        
        await callback.answer("✅ Фото одобрено!", show_alert=True)
        await show_next_or_list(callback, session)
    else:
        await callback.answer("❌ Фото не найдено", show_alert=True)
        await show_moderation_panel(callback, session)


@router.callback_query(F.data.startswith("moderation_reject_"))
async def moderation_reject_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Callback для отклонения фото"""
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ У вас нет доступа.", show_alert=True)
        return
    
    parts = callback.data.split("_")
    
    if len(parts) >= 4 and parts[2] == "confirm":
        if len(parts) >= 5:
            photo_id = int(parts[3])
            reason_key = parts[4]
            await moderation_reject_confirm_callback(callback, session, photo_id, reason_key)
        return
    
    if len(parts) >= 3:
        try:
            photo_id = int(parts[2])
        except ValueError:
            await callback.answer("❌ Ошибка: неверный формат", show_alert=True)
            return
    else:
        await callback.answer("❌ Ошибка: неверный формат", show_alert=True)
        return
    
    keyboard = get_moderation_reject_keyboard(photo_id)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


async def moderation_reject_confirm_callback(callback: CallbackQuery, session: AsyncSession, photo_id: int, reason_key: str) -> None:
    """Подтверждение отклонения фото"""
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ У вас нет доступа.", show_alert=True)
        return
    
    bot = callback.bot
    
    reason_map = {
        "not_suitable": "Фото не подходит для альбома",
        "low_quality": "Низкое качество фото",
        "not_pet": "На фото не питомец",
        "other": "Другая причина"
    }
    reason = reason_map.get(reason_key, "Другая причина")
    
    moderation_service = ModerationService(session)
    result = await moderation_service.reject_photo(photo_id, user_id, reason)
    
    if result["success"]:
        photo = result["photo"]
        
        pet_repo = PetRepository(session)
        pet = await pet_repo.get_by_id(photo.pet_id)
        
        user_repo = UserRepository(session)
        owner = await user_repo.get_by_id(pet.user_id) if pet else None
        
        if owner:
            try:
                await bot.send_message(
                    chat_id=owner.telegram_id,
                    text=(
                        f"❌ <b>Ваше фото отклонено</b>\n\n"
                        f"🐾 Питомец: {pet.name}\n"
                        f"📝 Причина: {reason}\n\n"
                        f"Вы можете загрузить другое фото.\n"
                        f"Если вы считаете, что это ошибка, свяжитесь с администрацией."
                    ),
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить владельца {owner.telegram_id}: {e}")
        
        await callback.answer("❌ Фото отклонено", show_alert=True)
        await show_next_or_list(callback, session)
    else:
        await callback.answer("❌ Фото не найдено", show_alert=True)
        await show_moderation_panel(callback, session)


@router.callback_query(F.data == "moderation_next")
async def moderation_next_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Callback для перехода к следующему фото"""
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ У вас нет доступа.", show_alert=True)
        return
    
    await show_next_photo(callback, session)


@router.callback_query(F.data == "moderation_info")
async def moderation_info_callback(callback: CallbackQuery) -> None:
    """Callback для информации о модерации"""
    await callback.answer("📸 Листайте список фото на модерации")


async def show_next_photo(event: Message | CallbackQuery, session: AsyncSession) -> None:
    """Показать следующее фото на модерации"""
    moderation_service = ModerationService(session)
    pending_photos = await moderation_service.get_pending_photos(limit=1)
    
    if not pending_photos:
        text = (
            "📸 <b>Модерация</b>\n\n"
            "✅ Все фото проверены!"
        )
        keyboard = get_moderation_empty_keyboard()
        await send_or_edit(event, text, reply_markup=keyboard, parse_mode="HTML")
        return
    
    item = pending_photos[0]
    photo = item["photo"]
    pet = item["pet"]
    user = item["user"]
    
    text = (
        f"📸 <b>Модерация фото</b>\n\n"
        f"🐾 <b>Питомец:</b> {pet.name}\n"
        f"👤 <b>Владелец:</b> {user.first_name or user.username or 'Пользователь'}\n"
        f"🆔 <b>ID владельца:</b> {user.telegram_id}\n"
        f"📝 <b>Описание:</b> {photo.caption or 'Без описания'}\n"
        f"🕐 <b>Отправлено:</b> {photo.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"<a href='tg://user?id={user.telegram_id}'>Перейти к пользователю</a>"
    )
    
    keyboard = get_moderation_photo_keyboard(photo.id)
    
    try:
        await delete_message(event)
        await event.message.answer_photo(
            photo=photo.telegram_file_id,
            caption=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Ошибка отправки фото на модерацию: {e}")
        await send_or_edit(
            event,
            f"❌ Не удалось загрузить фото\n\n{text}",
            reply_markup=keyboard,
            parse_mode="HTML"
        )


async def show_next_or_list(event: Message | CallbackQuery, session: AsyncSession) -> None:
    """Показать следующее фото или список"""
    moderation_service = ModerationService(session)
    pending_count = await moderation_service.get_pending_count()
    
    if pending_count > 0:
        await show_next_photo(event, session)
    else:
        text = "✅ <b>Все фото проверены!</b>\n\nБольше нет фото на модерации."
        keyboard = get_moderation_empty_keyboard()
        await send_or_edit(event, text, reply_markup=keyboard, parse_mode="HTML")