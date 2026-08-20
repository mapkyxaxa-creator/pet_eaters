from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from services.photo_service import PhotoService
from services.moderation_service import ModerationService
from utils.user_utils import ensure_user, ensure_pet
from utils.message_utils import send_or_edit, delete_message
from keyboards.main_menu import get_main_menu_keyboard_sync
from config import config

import logging
logger = logging.getLogger(__name__)

router = Router()


class PhotoStates(StatesGroup):
    """Состояния для альбома"""
    waiting_for_photo = State()
    waiting_for_caption = State()


@router.message(Command("photos"))
async def cmd_photos(message: Message, session: AsyncSession) -> None:
    """Команда /photos — альбом фотографий"""
    await show_album(message, session)


async def show_album(message: Message, session: AsyncSession) -> None:
    """Показать альбом фотографий"""
    user = await ensure_user(message, session)
    if not user:
        return
    
    pet = await ensure_pet(message, session, user)
    if not pet:
        return
    
    photo_service = PhotoService(session)
    photos = await photo_service.get_photos(pet.id)
    
    if not photos:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📸 Добавить фото", callback_data="photo_add")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
            ]
        )
        
        await message.answer(
            "📸 <b>Альбом фотографий</b>\n\n"
            "У тебя пока нет одобренных фотографий в альбоме.\n"
            "Добавь первое фото! Оно пройдёт модерацию.\n\n"
            "<i>Фото появляется в альбоме после одобрения админом.</i>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        return
    
    main_photo = await photo_service.get_main_photo(pet.id)
    photo_to_show = main_photo or photos[0]
    
    text = f"📸 <b>Альбом фотографий</b>\n\n"
    text += f"Всего фото: {len(photos)}\n"
    if photo_to_show.caption:
        text += f"📝 {photo_to_show.caption}\n"
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⬅️", callback_data=f"photo_prev_{photo_to_show.id}"),
                InlineKeyboardButton(text=f"{photos.index(photo_to_show) + 1}/{len(photos)}", callback_data="photo_info"),
                InlineKeyboardButton(text="➡️", callback_data=f"photo_next_{photo_to_show.id}")
            ],
            [
                InlineKeyboardButton(text="📸 Добавить фото", callback_data="photo_add"),
                InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"photo_delete_{photo_to_show.id}")
            ],
            [
                InlineKeyboardButton(text="⭐ Сделать главным", callback_data=f"photo_main_{photo_to_show.id}")
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")
            ]
        ]
    )
    
    await message.answer_photo(
        photo=photo_to_show.telegram_file_id,
        caption=text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )


async def show_album_from_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Показать альбом из callback (из профиля)"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    await delete_message(callback)
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    photo_service = PhotoService(session)
    photos = await photo_service.get_photos(pet.id)
    
    if not photos:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📸 Добавить фото", callback_data="photo_add")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
            ]
        )
        
        await callback.message.answer(
            "📸 <b>Альбом фотографий</b>\n\n"
            "У тебя пока нет одобренных фотографий в альбоме.\n"
            "Добавь первое фото! Оно пройдёт модерацию.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        return
    
    main_photo = await photo_service.get_main_photo(pet.id)
    photo_to_show = main_photo or photos[0]
    
    text = f"📸 <b>Альбом фотографий</b>\n\n"
    text += f"Всего фото: {len(photos)}\n"
    if photo_to_show.caption:
        text += f"📝 {photo_to_show.caption}\n"
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⬅️", callback_data=f"photo_prev_{photo_to_show.id}"),
                InlineKeyboardButton(text=f"{photos.index(photo_to_show) + 1}/{len(photos)}", callback_data="photo_info"),
                InlineKeyboardButton(text="➡️", callback_data=f"photo_next_{photo_to_show.id}")
            ],
            [
                InlineKeyboardButton(text="📸 Добавить фото", callback_data="photo_add"),
                InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"photo_delete_{photo_to_show.id}")
            ],
            [
                InlineKeyboardButton(text="⭐ Сделать главным", callback_data=f"photo_main_{photo_to_show.id}")
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")
            ]
        ]
    )
    
    await callback.message.answer_photo(
        photo=photo_to_show.telegram_file_id,
        caption=text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "photo_add")
async def photo_add(callback: CallbackQuery, state: FSMContext) -> None:
    """Начать добавление фото"""
    await state.set_state(PhotoStates.waiting_for_photo)
    await state.update_data(photo_source="album")
    
    await delete_message(callback)
    await callback.message.answer(
        "📸 <b>Добавление фото в альбом</b>\n\n"
        "Отправь фотографию питомца.\n\n"
        "<i>Фото пройдёт модерацию перед публикацией в альбоме.</i>\n"
        "Обычно это занимает несколько минут.",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(PhotoStates.waiting_for_photo, F.photo)
async def photo_received(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Получено фото"""
    user = await ensure_user(message, session)
    if not user:
        return
    
    file_id = message.photo[-1].file_id
    await state.update_data(file_id=file_id)
    
    await message.answer(
        "✏️ <b>Добавь подпись к фото</b>\n\n"
        "Можешь написать что-нибудь о своём питомце.\n"
        "Или нажми «Пропустить».",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="photo_skip_caption")]
            ]
        ),
        parse_mode="HTML"
    )
    await state.set_state(PhotoStates.waiting_for_caption)


@router.message(PhotoStates.waiting_for_photo)
async def photo_received_invalid(message: Message) -> None:
    """Получен не фото"""
    await message.answer("❌ Отправь фотографию!")


@router.message(PhotoStates.waiting_for_caption, F.text)
async def photo_caption_received(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Получена подпись"""
    user = await ensure_user(message, session)
    if not user:
        return
    
    caption = message.text.strip()
    if len(caption) > 200:
        await message.answer("❌ Подпись не должна превышать 200 символов")
        return
    
    await state.update_data(caption=caption)
    await save_photo(message, state, session)


@router.callback_query(PhotoStates.waiting_for_caption, F.data == "photo_skip_caption")
async def photo_skip_caption(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Пропустить подпись"""
    await state.update_data(caption=None)
    
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    data = await state.get_data()
    file_id = data.get("file_id")
    caption = data.get("caption")
    
    photo_service = PhotoService(session)
    count = await photo_service.get_photos_count(pet.id)
    is_main = count == 0
    
    # Добавляем фото с модерацией
    photo = await photo_service.add_photo_with_moderation(
        pet_id=pet.id,
        telegram_file_id=file_id,
        caption=caption,
        is_main=is_main,
        auto_approve=False  # Требуется модерация
    )
    
    await state.clear()
    
    await callback.message.edit_text(
        f"✅ Фото отправлено на модерацию!\n\n"
        f"📸 Оно появится в альбоме и ленте после проверки администратором.\n"
        f"Обычно это занимает несколько минут.",
        reply_markup=get_main_menu_keyboard_sync()
    )
    await callback.answer()
    
    # Уведомляем админов
    if photo:
        await notify_admins_about_photo(session, photo, callback.bot)


async def save_photo(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Сохранить фото в альбом"""
    data = await state.get_data()
    file_id = data.get("file_id")
    caption = data.get("caption")
    
    user = await ensure_user(message, session)
    if not user:
        return
    
    pet = await ensure_pet(message, session, user)
    if not pet:
        return
    
    photo_service = PhotoService(session)
    
    count = await photo_service.get_photos_count(pet.id)
    is_main = count == 0
    
    # Добавляем фото с модерацией
    photo = await photo_service.add_photo_with_moderation(
        pet_id=pet.id,
        telegram_file_id=file_id,
        caption=caption,
        is_main=is_main,
        auto_approve=False
    )
    
    await state.clear()
    
    await message.answer(
        f"✅ Фото отправлено на модерацию!\n\n"
        f"📸 Оно появится в альбоме и ленте после проверки администратором.\n"
        f"Обычно это занимает несколько минут.",
        reply_markup=get_main_menu_keyboard_sync()
    )
    
    # Уведомляем админов
    if photo:
        await notify_admins_about_photo(session, photo, message.bot)


@router.callback_query(F.data.startswith("photo_delete_"))
async def photo_delete(callback: CallbackQuery, session: AsyncSession) -> None:
    """Удалить фото"""
    photo_id = int(callback.data.split("_")[2])
    
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    photo_service = PhotoService(session)
    photo = await photo_service.get_photo(photo_id)
    
    if not photo or photo.pet_id != pet.id:
        await callback.answer("❌ Фото не найдено", show_alert=True)
        return
    
    count = await photo_service.get_photos_count(pet.id)
    
    if count <= 1:
        await callback.answer("❌ Нельзя удалить последнее фото", show_alert=True)
        return
    
    await photo_service.delete_photo(photo_id)
    
    await callback.answer("✅ Фото удалено", show_alert=True)
    await delete_message(callback)
    await show_album_from_callback(callback, session)


@router.callback_query(F.data.startswith("photo_main_"))
async def photo_set_main(callback: CallbackQuery, session: AsyncSession) -> None:
    """Сделать фото главным"""
    photo_id = int(callback.data.split("_")[2])
    
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    photo_service = PhotoService(session)
    success = await photo_service.set_main_photo(pet.id, photo_id)
    
    if success:
        await callback.answer("⭐ Фото теперь главное!", show_alert=True)
        await delete_message(callback)
        await show_album_from_callback(callback, session)
    else:
        await callback.answer("❌ Не удалось установить главное фото", show_alert=True)


@router.callback_query(F.data == "photo_info")
async def photo_info(callback: CallbackQuery) -> None:
    """Информация о фото (заглушка)"""
    await callback.answer("📸 Листай фото в альбоме")


@router.callback_query(F.data == "my_photos")
async def my_photos_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Callback для кнопки 'Альбом' в профиле"""
    await show_album_from_callback(callback, session)


@router.callback_query(F.data.startswith("photo_prev_"))
async def photo_prev(callback: CallbackQuery, session: AsyncSession) -> None:
    """Предыдущее фото"""
    photo_id = int(callback.data.split("_")[2])
    
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    photo_service = PhotoService(session)
    photos = await photo_service.get_photos(pet.id)
    
    current_index = next((i for i, p in enumerate(photos) if p.id == photo_id), -1)
    if current_index > 0:
        prev_photo = photos[current_index - 1]
        await show_photo_detail(callback, session, prev_photo, photos, pet.id)
    else:
        await callback.answer("Это первое фото", show_alert=True)


@router.callback_query(F.data.startswith("photo_next_"))
async def photo_next(callback: CallbackQuery, session: AsyncSession) -> None:
    """Следующее фото"""
    photo_id = int(callback.data.split("_")[2])
    
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    photo_service = PhotoService(session)
    photos = await photo_service.get_photos(pet.id)
    
    current_index = next((i for i, p in enumerate(photos) if p.id == photo_id), -1)
    if current_index < len(photos) - 1:
        next_photo = photos[current_index + 1]
        await show_photo_detail(callback, session, next_photo, photos, pet.id)
    else:
        await callback.answer("Это последнее фото", show_alert=True)


async def show_photo_detail(callback: CallbackQuery, session: AsyncSession, photo, photos, pet_id: int) -> None:
    """Показать детали фото"""
    text = f"📸 <b>Альбом фотографий</b>\n\n"
    text += f"Всего фото: {len(photos)}\n"
    if photo.caption:
        text += f"📝 {photo.caption}\n"
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⬅️", callback_data=f"photo_prev_{photo.id}"),
                InlineKeyboardButton(text=f"{photos.index(photo) + 1}/{len(photos)}", callback_data="photo_info"),
                InlineKeyboardButton(text="➡️", callback_data=f"photo_next_{photo.id}")
            ],
            [
                InlineKeyboardButton(text="📸 Добавить фото", callback_data="photo_add"),
                InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"photo_delete_{photo.id}")
            ],
            [
                InlineKeyboardButton(text="⭐ Сделать главным", callback_data=f"photo_main_{photo.id}")
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")
            ]
        ]
    )
    
    await callback.message.edit_media(
        media=InputMediaPhoto(
            media=photo.telegram_file_id,
            caption=text,
            parse_mode="HTML"
        ),
        reply_markup=keyboard
    )
    await callback.answer()


async def notify_admins_about_photo(session: AsyncSession, photo, bot: Bot) -> None:
    """Уведомить админов о новом фото на модерации"""
    from database.repositories.pet_repository import PetRepository
    from database.repositories.user_repository import UserRepository
    
    try:
        pet_repo = PetRepository(session)
        user_repo = UserRepository(session)
        
        pet = await pet_repo.get_by_id(photo.pet_id)
        if not pet:
            return
        
        owner = await user_repo.get_by_id(pet.user_id)
        if not owner:
            return
        
        text = (
            f"📸 <b>Новое фото на модерации</b>\n\n"
            f"👤 От: {owner.first_name or owner.username or 'Пользователь'}\n"
            f"🐾 Питомец: {pet.name}\n"
            f"🆔 ID: {owner.telegram_id}\n"
            f"🕐 {photo.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"<a href='tg://user?id={owner.telegram_id}'>Перейти к пользователю</a>"
        )
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📸 Модерация",
                        callback_data="moderation"
                    )
                ]
            ]
        )
        
        for admin_id in config.ADMIN_IDS:
            try:
                await bot.send_photo(
                    chat_id=admin_id,
                    photo=photo.telegram_file_id,
                    caption=text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                logger.info(f"Уведомление о новом фото отправлено админу {admin_id}")
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")
                # Пытаемся отправить текстовое уведомление
                try:
                    await bot.send_message(
                        chat_id=admin_id,
                        text=f"📸 Новое фото на модерации от @{owner.username or 'пользователя'}\n\n"
                             f"Нажми /moderation для проверки.",
                        parse_mode="HTML"
                    )
                except:
                    pass
    except Exception as e:
        logger.error(f"Ошибка уведомления админов: {e}")