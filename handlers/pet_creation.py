from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories.user_repository import UserRepository
from database.repositories.pet_repository import PetRepository
from services.data_loader import data_loader
from services.pet_service import PetService
from services.photo_service import PhotoService
from utils.validation import validate_pet_name
from utils.profanity_filter import validate_text
from utils.user_utils import ensure_user
from utils.message_utils import send_or_edit, delete_message
from keyboards.main_menu import get_main_menu_keyboard_sync

import logging
logger = logging.getLogger(__name__)

router = Router()


class PetCreationStates(StatesGroup):
    """Состояния создания питомца"""
    waiting_for_photo = State()
    waiting_for_name = State()


@router.callback_query(F.data.startswith("create_pet_"))
async def start_pet_creation(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Начало создания питомца - выбор характера"""
    # Проверяем пользователя
    user = await ensure_user(callback, session)
    if not user:
        return
    
    # maxsplit=2 на случай, если character_id будет содержать "_"
    character_id = callback.data.split("_", 2)[2]
    
    # Сохраняем характер в FSM
    await state.update_data(character_id=character_id)
    
    # Проверяем, что характер есть в JSON
    characters = data_loader.get_characters()
    
    if character_id not in characters:
        await send_or_edit(
            callback,
            text=f"❌ Ошибка: характер '{character_id}' не найден в базе данных.\n"
                 f"Доступные характеры: {', '.join(characters.keys())}"
        )
        return
    
    # Получаем данные характера для отображения
    character = characters.get(character_id, {})
    character_name = character.get("name", "Неизвестно")
    character_emoji = character.get("emoji", "")
    
    await delete_message(callback)
    await callback.message.answer(
        f"✅ Выбран характер: {character_emoji} {character_name}\n\n"
        "📸 <b>Теперь отправь фото своего питомца!</b>\n\n"
        "Это будет его аватар в игре. "
        "Отправь любое фото, и я превращу его в игрового персонажа! 🐾\n\n"
        "<i>Просто отправь фотографию в этот чат.</i>",
        parse_mode="HTML"
    )
    
    await state.set_state(PetCreationStates.waiting_for_photo)
    await callback.answer()


@router.message(PetCreationStates.waiting_for_photo, F.photo)
async def process_photo(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Обработка фото питомца"""
    # Проверяем пользователя
    user = await ensure_user(message, session)
    if not user:
        return
    
    # Сохраняем file_id фото
    photo_file_id = message.photo[-1].file_id
    await state.update_data(photo_file_id=photo_file_id)
    
    # Запрашиваем имя
    await message.answer(
        "✏️ <b>Теперь придумай имя для питомца!</b>\n\n"
        "Имя должно быть:\n"
        "• От 2 до 20 символов\n"
        "• Только буквы, цифры и пробелы\n\n"
        "<i>Напиши имя в ответном сообщении.</i>",
        parse_mode="HTML"
    )
    
    await state.set_state(PetCreationStates.waiting_for_name)


@router.message(PetCreationStates.waiting_for_photo)
async def process_photo_invalid(message: Message) -> None:
    """Обработка не-фото при ожидании фото"""
    await message.answer(
        "❌ Пожалуйста, отправь <b>фотографию</b> своего питомца!\n"
        "Просто нажми на скрепку 📎 и выбери фото.",
        parse_mode="HTML"
    )


@router.message(PetCreationStates.waiting_for_name)
async def process_name(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Обработка имени питомца"""
    # Проверяем пользователя
    user = await ensure_user(message, session)
    if not user:
        return
    
    name = message.text.strip()
    
    # Валидация имени
    is_valid, error = validate_pet_name(name)
    if not is_valid:
        await message.answer(f"❌ {error}\n\nПопробуй еще раз:")
        return
    
    # ===== ПРОВЕРКА НА МАТ =====
    is_valid, error, filtered_name = validate_text(name, "Имя")
    if not is_valid:
        await message.answer(
            f"{error}\n\n"
            f"📝 Предлагаем вариант: <b>{filtered_name}</b>\n"
            f"Или придумайте другое имя.",
            parse_mode="HTML"
        )
        return
    
    # Получаем данные из FSM
    data = await state.get_data()
    character_id = data.get("character_id")
    photo_file_id = data.get("photo_file_id")
    
    if not character_id:
        await message.answer(
            "❌ Ошибка: характер не выбран. Попробуй начать заново с /start"
        )
        await state.clear()
        return
    
    if not photo_file_id:
        await message.answer(
            "❌ Ошибка: фото не загружено. Попробуй начать заново с /start"
        )
        await state.clear()
        return
    
    # Получаем данные характера из JSON
    characters = data_loader.get_characters()
    character = characters.get(character_id, {})
    
    if not character:
        await message.answer(
            f"❌ Ошибка: характер с ID '{character_id}' не найден в базе данных.\n"
            f"Доступные характеры: {', '.join(characters.keys())}"
        )
        await state.clear()
        return
    
    # Получаем данные для отображения
    character_name = character.get("name", "Неизвестно")
    character_emoji = character.get("emoji", "")
    bonus_description = character.get("bonus_description", "Нет бонуса")
    
    # Создаем питомца
    pet_service = PetService(session)
    pet = await pet_service.create_pet(
        user_id=user.id,
        name=filtered_name,
        photo_file_id=photo_file_id,
        character_id=character_id,
        character_bonus=character.get("bonus", {})
    )
    
    # ===== ДОБАВЛЯЕМ ФОТО В АЛЬБОМ (АВТОМАТИЧЕСКИ ОДОБРЕННО) =====
    try:
        photo_service = PhotoService(session)
        album_photo = await photo_service.add_photo_with_moderation(
            pet_id=pet.id,
            telegram_file_id=photo_file_id,
            caption=filtered_name,
            is_main=True,
            auto_approve=True  # Аватар сразу одобрен
        )
        logger.info(f"📸 Фото добавлено в альбом (одобрено): photo_id={album_photo.id} для питомца {pet.id}")
    except Exception as e:
        logger.error(f"❌ Ошибка добавления фото в альбом: {e}")
    
    # Очищаем состояние
    await state.clear()
    
    # Формируем текст характера
    character_text = f"{character_emoji} {character_name}" if character_emoji else character_name
    
    # Отправляем поздравление и запускаем онбординг
    await message.answer_photo(
        photo=photo_file_id,
        caption=(
            f"🎉 <b>Поздравляю! Питомец создан!</b>\n\n"
            f"🐾 <b>Имя:</b> {filtered_name}\n"
            f"😊 <b>Характер:</b> {character_text}\n"
            f"🏅 <b>Бонус:</b> {bonus_description}\n"
            f"🆔 <b>ID:</b> <code>{pet.game_id}</code>\n\n"
            f"А теперь давай пройдём небольшое обучение! 🎓"
        ),
        parse_mode="HTML"
    )
    
    # Запускаем онбординг
    from handlers.onboarding import start_onboarding
    await start_onboarding(message, session, user.id, pet.id)