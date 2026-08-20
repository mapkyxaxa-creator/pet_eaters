from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from services.social_service import SocialService
from utils.user_utils import ensure_user
from utils.message_utils import send_or_edit, delete_message
from keyboards.main_menu import get_main_menu_keyboard

router = Router()


@router.message(Command("rating"))
async def cmd_rating(message: Message, session: AsyncSession) -> None:
    """Команда /rating — рейтинг"""
    await show_rating(message, session, "level")


async def show_rating(message: Message, session: AsyncSession, rating_type: str = "level") -> None:
    """Показать рейтинг"""
    user = await ensure_user(message, session)
    if not user:
        return
    
    social_service = SocialService(session)
    result = await social_service.get_rating(rating_type, limit=10)
    
    if not result["success"]:
        await message.answer(f"❌ {result['message']}")
        return
    
    # Формируем текст
    type_names = {
        "level": "📊 По уровню",
        "likes": "❤️ По лайкам"
    }
    
    text = f"🏆 <b>Рейтинг</b>\n"
    text += f"{type_names.get(rating_type, 'По уровню')}\n\n"
    
    medals = ["🥇", "🥈", "🥉"]
    
    if not result["rating"]:
        text += "Пока нет игроков в рейтинге\n"
    else:
        for i, item in enumerate(result["rating"]):
            medal = medals[i] if i < 3 else f"{i+1}."
            text += f"{medal} <b>{item['pet_name']}</b>\n"
            text += f"   👤 {item['owner_name']}\n"
            text += f"   📊 Уровень: {item['level']} | ❤️ {item['likes']}\n\n"
    
    # Клавиатура для переключения между рейтингами
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 По уровню" + (" ✅" if rating_type == "level" else ""),
                    callback_data="rating_level"
                ),
                InlineKeyboardButton(
                    text="❤️ По лайкам" + (" ✅" if rating_type == "likes" else ""),
                    callback_data="rating_likes"
                )
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")
            ]
        ]
    )
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


async def show_rating_from_callback(callback: CallbackQuery, session: AsyncSession, rating_type: str = "level") -> None:
    """Показать рейтинг из callback"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    await delete_message(callback)
    
    social_service = SocialService(session)
    result = await social_service.get_rating(rating_type, limit=10)
    
    if not result["success"]:
        await callback.message.answer(f"❌ {result['message']}")
        await callback.answer()
        return
    
    type_names = {
        "level": "📊 По уровню",
        "likes": "❤️ По лайкам"
    }
    
    text = f"🏆 <b>Рейтинг</b>\n"
    text += f"{type_names.get(rating_type, 'По уровню')}\n\n"
    
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
                InlineKeyboardButton(
                    text="📊 По уровню" + (" ✅" if rating_type == "level" else ""),
                    callback_data="rating_level"
                ),
                InlineKeyboardButton(
                    text="❤️ По лайкам" + (" ✅" if rating_type == "likes" else ""),
                    callback_data="rating_likes"
                )
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")
            ]
        ]
    )
    
    await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("rating_"))
async def rating_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Переключение типа рейтинга"""
    rating_type = callback.data.split("_")[1]
    await show_rating_from_callback(callback, session, rating_type)