"""
Хендлер для сюжетных глав
"""
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from services.story_service import StoryService
from utils.user_utils import ensure_user, ensure_pet
from utils.message_utils import send_or_edit, delete_message
from keyboards.main_menu import get_main_menu_keyboard_sync

logger = logging.getLogger(__name__)

router = Router()


# ==================== ОСНОВНАЯ ЛОГИКА ====================

async def show_story(event: Message, session: AsyncSession) -> None:
    """Показать прогресс сюжета (из сообщения)"""
    user = await ensure_user(event, session)
    if not user:
        return
    
    pet = await ensure_pet(event, session, user)
    if not pet:
        return
    
    story_service = StoryService(session)
    status = story_service.get_chapter_status(pet)
    
    text = f"📖 **Сюжет: История поисков**\n\n"
    text += f"Прогресс: {status['completed']}/{status['total']} ({status['percentage']}%)\n\n"
    
    for chapter_status in status['chapters']:
        chapter = chapter_status['chapter']
        name = chapter.get('name', 'Без названия')
        emoji = chapter.get('emoji', '📖')
        
        if chapter_status['is_completed']:
            text += f"✅ {emoji} {name} — пройдено\n"
        elif chapter_status['is_available']:
            text += f"🟢 {emoji} {name} — доступно!\n"
        else:
            min_level = chapter.get('min_level', 1)
            text += f"🔒 {emoji} {name} — уровень {min_level}\n"
    
    text += "\n🎮 **Управление:**"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Подробнее о главе", callback_data="story_detail")],
        [InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")]
    ])
    
    await event.answer(text, reply_markup=keyboard, parse_mode="Markdown")


async def show_story_from_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Показать прогресс сюжета (из callback)"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    story_service = StoryService(session)
    status = story_service.get_chapter_status(pet)
    
    text = f"📖 **Сюжет: История поисков**\n\n"
    text += f"Прогресс: {status['completed']}/{status['total']} ({status['percentage']}%)\n\n"
    
    for chapter_status in status['chapters']:
        chapter = chapter_status['chapter']
        name = chapter.get('name', 'Без названия')
        emoji = chapter.get('emoji', '📖')
        
        if chapter_status['is_completed']:
            text += f"✅ {emoji} {name} — пройдено\n"
        elif chapter_status['is_available']:
            text += f"🟢 {emoji} {name} — доступно!\n"
        else:
            min_level = chapter.get('min_level', 1)
            text += f"🔒 {emoji} {name} — уровень {min_level}\n"
    
    text += "\n🎮 **Управление:**"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Подробнее о главе", callback_data="story_detail")],
        [InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")]
    ])
    
    await send_or_edit(callback, text, reply_markup=keyboard, parse_mode="Markdown")


# ==================== КОМАНДА /story ====================

@router.message(Command("story"))
async def cmd_story(message: Message, session: AsyncSession) -> None:
    """Команда /story"""
    await show_story(message, session)


# ==================== CALLBACK'И ====================

@router.callback_query(F.data == "story_detail")
async def story_detail(callback: CallbackQuery, session: AsyncSession) -> None:
    """Показать подробности текущей/следующей главы"""
    user = await ensure_user(callback, session)
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        await callback.answer("❌ У вас нет питомца", show_alert=True)
        return
    
    story_service = StoryService(session)
    
    next_chapter = story_service.get_next_chapter(pet)
    if not next_chapter:
        await callback.answer("🎉 Вы прошли все главы!", show_alert=True)
        return
    
    name = next_chapter.get('name', 'Без названия')
    emoji = next_chapter.get('emoji', '📖')
    location = next_chapter.get('location', 'неизвестно')
    min_level = next_chapter.get('min_level', 1)
    description = next_chapter.get('description', 'Описание отсутствует')
    rewards = next_chapter.get('rewards', {})
    coins = rewards.get('coins', 0)
    xp = rewards.get('xp', 0)
    title = rewards.get('title', '')
    
    is_available = pet.level >= min_level and pet.story_progress + 1 == next_chapter.get('order', 0)
    
    text = f"{emoji} **{name}**\n\n"
    text += f"📌 **Локация:** {location}\n"
    text += f"📊 **Минимальный уровень:** {min_level}\n"
    text += f"📝 **Описание:** {description}\n\n"
    text += f"🎁 **Награды:**\n"
    text += f"• 🪙 {coins} монет\n"
    text += f"• ⭐ {xp} опыта\n"
    if title:
        text += f"• 🏆 Титул: {title}\n"
    
    if not is_available:
        text += f"\n🔒 **Недоступно:** Требуется уровень {min_level} (ваш уровень: {pet.level})"
    else:
        text += f"\n✅ **Доступно!**"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Диалоги главы", callback_data=f"story_dialogue_{next_chapter.get('id')}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="story_back")]
    ])
    
    await send_or_edit(callback, text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()





@router.callback_query(F.data.startswith("story_dialogue_"))
async def story_dialogue(callback: CallbackQuery, session: AsyncSession) -> None:
    """Показать диалоги главы"""
    chapter_id = callback.data.replace("story_dialogue_", "")
    
    story_service = StoryService(session)
    chapter = story_service.get_chapter_by_id(chapter_id)
    
    if not chapter:
        await callback.answer("Глава не найдена", show_alert=True)
        return
    
    dialogues = story_service.get_chapter_dialogue(chapter_id)
    choices = story_service.get_chapter_choices(chapter_id)
    
    text = f"📜 **Диалоги: {chapter.get('emoji')} {chapter.get('name')}**\n\n"
    
    for dialogue in dialogues:
        npc = dialogue.get('npc', 'unknown')
        text_content = dialogue.get('text', '')
        
        if npc == 'pet':
            text += f"🐾 **Питомец:** {text_content}\n\n"
        elif npc == 'rich':
            text += f"👤 **Рич:** {text_content}\n\n"
        else:
            text += f"**{npc}:** {text_content}\n\n"
    
    keyboard_buttons = []
    if choices:
        for choice in choices:
            choice_id = choice.get('id')
            choice_text = choice.get('text', '')
            keyboard_buttons.append(
                InlineKeyboardButton(
                    text=f"💬 {choice_text}",
                    callback_data=f"story_choice_{chapter_id}_{choice_id}"
                )
            )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            keyboard_buttons,
            [InlineKeyboardButton(text="🔙 Назад к главе", callback_data="story_detail")]
        ])
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад к главе", callback_data="story_detail")]
        ])
    
    await send_or_edit(callback, text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("story_choice_"))
async def story_choice(callback: CallbackQuery, session: AsyncSession) -> None:
    """Обработчик выбора в диалоге"""
    data_parts = callback.data.replace("story_choice_", "").split("_")
    chapter_id = data_parts[0]
    choice_id = data_parts[1] if len(data_parts) > 1 else None
    
    if not choice_id:
        await callback.answer("Ошибка: выбор не найден", show_alert=True)
        return
    
    story_service = StoryService(session)
    chapter = story_service.get_chapter_by_id(chapter_id)
    
    if not chapter:
        await callback.answer("Глава не найдена", show_alert=True)
        return
    
    choices = story_service.get_chapter_choices(chapter_id)
    choice = next((c for c in choices if c.get('id') == choice_id), None)
    
    if not choice:
        await callback.answer("Выбор не найден", show_alert=True)
        return
    
    # Получаем ответ по выбору
    response_text = choice.get('response', '')
    npc = choice.get('npc', 'rich')
    
    text = f"📜 **Диалоги: {chapter.get('emoji')} {chapter.get('name')}**\n\n"
    
    # Показываем все диалоги снова
    dialogues = story_service.get_chapter_dialogue(chapter_id)
    for dialogue in dialogues:
        d_npc = dialogue.get('npc', 'unknown')
        d_text = dialogue.get('text', '')
        
        if d_npc == 'pet':
            text += f"🐾 **Питомец:** {d_text}\n\n"
        elif d_npc == 'rich':
            text += f"👤 **Рич:** {d_text}\n\n"
        else:
            text += f"**{d_npc}:** {d_text}\n\n"
    
    # Показываем выбранный ответ
    text += f"\n---\n\n"
    text += f"💬 **Вы выбрали:** {choice.get('text', '')}\n\n"
    
    if npc == 'pet':
        text += f"🐾 **Питомец:** {response_text}\n\n"
    elif npc == 'rich':
        text += f"👤 **Рич:** {response_text}\n\n"
    else:
        text += f"**{npc}:** {response_text}\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к главе", callback_data="story_detail")]
    ])
    
    await send_or_edit(callback, text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data == "story_back")
async def story_back(callback: CallbackQuery, session: AsyncSession) -> None:
    """Вернуться к основному меню сюжета"""
    await show_story_from_callback(callback, session)  # ✅ ПРАВИЛЬНО!
    await callback.answer()