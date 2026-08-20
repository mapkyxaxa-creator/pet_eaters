"""
Хендлер для уведомлений
"""
import json
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from services.feed_service import FeedService
from utils.user_utils import ensure_user
from utils.message_utils import send_or_edit, delete_message
from keyboards.main_menu import get_main_menu_keyboard

router = Router()


@router.message(Command("notifications"))
async def cmd_notifications(message: Message, session: AsyncSession) -> None:
    """Команда /notifications"""
    user = await ensure_user(message, session)
    if not user:
        return

    await show_notifications(message, session)


@router.callback_query(F.data == "notifications")
async def notifications_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Кнопка уведомлений"""
    user = await ensure_user(callback, session)
    if not user:
        return

    await delete_message(callback)
    await show_notifications(callback, session)
    await callback.answer()


async def show_notifications(event: Message | CallbackQuery, session: AsyncSession) -> None:
    """Показать уведомления"""
    user = await ensure_user(event, session)
    if not user:
        return

    feed_service = FeedService(session)
    notifications = await feed_service.get_notifications(user.id, limit=20)

    if not notifications:
        text = "🔔 <b>Уведомления</b>\n\n"
        text += "📭 У тебя пока нет уведомлений."

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 В меню", callback_data="main_menu")]
            ]
        )

        if isinstance(event, Message):
            await event.answer(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await send_or_edit(event, text, reply_markup=keyboard)
        return

    # Отмечаем все как прочитанные
    await feed_service.mark_all_notifications_read(user.id)

    text = "🔔 <b>Уведомления</b>\n\n"

    for n in notifications[:10]:
        # Декодируем data если есть
        data_str = ""
        if n.get("data"):
            try:
                data = json.loads(n["data"]) if isinstance(n["data"], str) else n["data"]
                if data:
                    data_str = f" ({', '.join([f'{k}: {v}' for k, v in data.items()])})"
            except:
                pass

        status = "🆕" if not n["is_read"] else "📌"
        text += f"{status} {n['text']}{data_str}\n"
        text += f"   🕐 {n['created_at'].strftime('%d.%m %H:%M')}\n\n"

    if len(notifications) > 10:
        text += f"\n<i>...и еще {len(notifications) - 10} уведомлений</i>"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="notifications")],
            [InlineKeyboardButton(text="🔙 В меню", callback_data="main_menu")]
        ]
    )

    if isinstance(event, Message):
        await event.answer(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await send_or_edit(event, text, reply_markup=keyboard)


# ============================================================
# КНОПКА В ГЛАВНОМ МЕНЮ (ДОБАВЛЕНА В main_menu.py)
# ============================================================
# В main_menu.py уже есть кнопка:
# InlineKeyboardButton(text=notifications_text, callback_data="notifications")