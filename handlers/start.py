from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime  # <-- ДОБАВЛЕНО

from database.repositories.user_repository import UserRepository
from database.repositories.pet_repository import PetRepository
from keyboards.main_menu import get_main_menu_keyboard_sync
from services.data_loader import data_loader
from services.social_service import SocialService
from services.level_service import LevelService
from utils.user_utils import ensure_user
from utils.message_utils import send_or_edit
from handlers.common import get_achievement_service

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext) -> None:
    """Обработчик команды /start"""
    await state.clear()
    
    # Проверяем, есть ли параметр deep link
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("pet_"):
        game_id = args[1][4:]
        await show_pet_by_game_id(message, session, game_id)
        return
    
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(message.from_user.id)
    
    if not user:
        user = await user_repo.create(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )
    else:
        # ===== ОБНОВЛЯЕМ ВРЕМЯ ПОСЛЕДНЕЙ АКТИВНОСТИ =====
        user.last_active = datetime.utcnow()
        await session.flush()
    
    pet_repo = PetRepository(session)
    has_pet = await pet_repo.has_pet(user.id)
    
    if not has_pet:
        characters = data_loader.get("characters", {})
        keyboard_buttons = []
        row = []
        for char_id, data in characters.items():
            row.append(
                InlineKeyboardButton(
                    text=f"{data.get('emoji', '')} {data.get('name', '')}",
                    callback_data=f"create_pet_{char_id}"
                )
            )
            if len(row) == 2:
                keyboard_buttons.append(row)
                row = []
        if row:
            keyboard_buttons.append(row)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await message.answer(
            "🐾 <b>Добро пожаловать в игру «Питомцы: Большой Жор»!</b>\n\n"
            "Я — Рич, главный NPC этого мира! 🐶\n\n"
            "Выбери характер своего питомца:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        pet = await pet_repo.get_by_user_id(user.id)
        
        # Проверяем онбординг
        if user.onboarding_step == 0:
            # Онбординг не начат - запускаем
            from handlers.onboarding import start_onboarding
            await message.answer(
                f"🐾 <b>С возвращением, {user.first_name}!</b>\n\n"
                f"Твой питомец <b>{pet.name}</b> уже ждет тебя!\n\n"
                f"Давай пройдём обучение! 🎓"
            )
            await start_onboarding(message, session, user.id, pet.id)
            return
        elif user.onboarding_step >= 1 and user.onboarding_step <= 6:
            # Онбординг в процессе
            from handlers.onboarding import start_onboarding
            await message.answer(
                f"🐾 <b>Продолжим обучение!</b>\n\n"
                f"Ты на шаге {user.onboarding_step} из 6."
            )
            await start_onboarding(message, session, user.id, pet.id)
            return
        
        # Восстанавливаем энергию при входе
        from services.adventure_service import AdventureService
        data = message.bot.data if hasattr(message.bot, 'data') else {}
        level_service = LevelService(session)
        from services.achievement_service import AchievementService
        achievement_service = AchievementService(session, data.get('achievement_repo'))
        adventure_service = AdventureService(session, level_service, achievement_service)
        await adventure_service.recover_energy(pet)
        
        hunger_percent = pet.get_hunger_percent()
        
        # ===== ПРОВЕРЯЕМ СЮЖЕТ =====
        from services.story_service import StoryService
        story_service = StoryService(session)
        next_chapter = story_service.get_next_chapter(pet)
        story_notification = ""
        if next_chapter:
            story_notification = f"\n\n📖 <b>НОВАЯ ГЛАВА ДОСТУПНА!</b>\n"
            story_notification += f"{next_chapter.get('emoji', '')} {next_chapter.get('name', '')}\n"
            story_notification += f"Отправляйся в приключение, чтобы начать!"
        
        # ===== ПРОВЕРЯЕМ ДОСТИЖЕНИЯ =====
        data = message.bot.data if hasattr(message.bot, 'data') else {}
        achievement_service = get_achievement_service(session, data)
        unlocked = await achievement_service.check_all_achievements(pet.id)
        
        achievement_notification = ""
        if unlocked:
            achievement_notification = "\n\n🏆 <b>НОВЫЕ ДОСТИЖЕНИЯ!</b>\n"
            for ach in unlocked:
                ach_data = ach.get("data", {})
                achievement_notification += f"{ach_data.get('emoji', '')} {ach_data.get('name', '')}\n"
        
        notification = story_notification + achievement_notification
        
        level_service = LevelService(session)
        xp_for_next = level_service.get_xp_for_level(pet.level)
        xp_progress = int((pet.experience / xp_for_next) * 100) if xp_for_next > 0 else 0
        
        await message.answer(
            f"🐾 <b>С возвращением, {user.first_name}!</b>\n\n"
            f"Твой питомец <b>{pet.name}</b> уже ждет тебя!\n"
            f"📊 Уровень: {pet.level} ({pet.experience}/{xp_for_next} XP, {xp_progress}%)\n"
            f"❤️ Сытость: {hunger_percent:.0f}%\n"
            f"💰 Монет: {user.coins}\n"
            f"🆔 ID питомца: <code>{pet.game_id}</code>"
            f"{notification}",
            reply_markup=get_main_menu_keyboard_sync(),
            parse_mode="HTML"
        )


async def show_pet_by_game_id(message: Message, session: AsyncSession, game_id: str) -> None:
    """Показать питомца по game_id"""
    pet_repo = PetRepository(session)
    pet = await pet_repo.get_by_game_id(game_id)
    
    if not pet:
        await message.answer(
            f"❌ Питомец с ID <code>{game_id}</code> не найден.\n\n"
            "Возможно, ID введен неверно или питомец был удален.",
            parse_mode="HTML"
        )
        return
    
    social_service = SocialService(session)
    viewer_id = message.from_user.id
    
    user_repo = UserRepository(session)
    viewer = await user_repo.get_by_telegram_id(viewer_id)
    
    profile_data = await social_service.get_pet_profile(viewer_id, pet.id)
    if not profile_data["success"]:
        await message.answer(f"❌ {profile_data['message']}")
        return
    
    owner = profile_data["owner"]
    character = data_loader.get("characters", {}).get(pet.character_id, {})
    
    hunger_percent = pet.get_hunger_percent()
    hunger_emoji = "😊"
    if hunger_percent >= 150:
        hunger_emoji = "💀"
    elif hunger_percent >= 120:
        hunger_emoji = "🤢"
    elif hunger_percent >= 100:
        hunger_emoji = "😋"
    
    level_service = LevelService(session)
    xp_for_next = level_service.get_xp_for_level(pet.level)
    xp_progress = int((pet.experience / xp_for_next) * 100) if xp_for_next > 0 else 0
    
    text = f"🐾 <b>{pet.name}</b>\n"
    text += f"{character.get('emoji', '')} <b>Характер:</b> {character.get('name', 'Неизвестно')}\n\n"
    text += f"📊 <b>Уровень:</b> {pet.level} ({pet.experience}/{xp_for_next} XP, {xp_progress}%)\n"
    text += f"{hunger_emoji} <b>Сытость:</b> {hunger_percent:.0f}%\n"
    text += f"❤️ <b>Лайков:</b> {pet.total_likes}\n"
    text += f"👑 <b>Титул:</b> {profile_data['title_text']}\n"
    text += f"🆔 <b>ID:</b> <code>{pet.game_id}</code>\n"
    text += f"👤 <b>Владелец:</b> {owner.first_name or owner.username}\n"
    
    keyboard = []
    
    if viewer and pet.user_id != viewer.id:
        if profile_data["has_liked"]:
            keyboard.append([InlineKeyboardButton(
                text="💔 Убрать лайк",
                callback_data=f"unlike_{pet.id}"
            )])
        else:
            keyboard.append([InlineKeyboardButton(
                text="❤️ Поставить лайк",
                callback_data=f"like_{pet.id}"
            )])
        
        keyboard.append([InlineKeyboardButton(
            text="🎁 Отправить подарок",
            callback_data=f"gift_{pet.id}"
        )])
    else:
        keyboard.append([InlineKeyboardButton(
            text="📤 Поделиться",
            callback_data=f"share_{pet.id}"
        )])
    
    keyboard.append([InlineKeyboardButton(
        text="🏠 В главное меню",
        callback_data="main_menu"
    )])
    
    await message.answer_photo(
        photo=pet.photo_file_id,
        caption=text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML"
    )