"""Обработчик для общего чата питомцев"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import asyncio

from services.chat_service import ChatService
from utils.user_utils import ensure_user
from utils.message_utils import send_or_edit, delete_message
from keyboards.main_menu import get_main_menu_keyboard

router = Router()


@router.message(Command("chat"))
async def cmd_chat(message: Message, session: AsyncSession) -> None:
    """Команда /chat - показать общий чат питомцев"""
    user = await ensure_user(message, session)
    if not user:
        return
    
    await show_chat(message, session, is_callback=False)


@router.callback_query(F.data == "chat")
async def chat_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Callback для кнопки чата питомцев"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    await delete_message(callback)
    await show_chat(callback, session, is_callback=True)


@router.callback_query(F.data == "refresh_chat")
async def refresh_chat_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Обновить чат"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    await show_chat(callback, session, is_callback=True, refresh=True)


async def show_chat(
    source: Message | CallbackQuery,
    session: AsyncSession,
    is_callback: bool = False,
    refresh: bool = False
) -> None:
    """
    Показать общий чат питомцев
    
    Args:
        source: Message или CallbackQuery
        session: Сессия БД
        is_callback: True если source это CallbackQuery
        refresh: True если обновление
    """
    chat_service = ChatService(session)
    
    # Получаем последние 30 сообщений
    messages = await chat_service.get_chat(limit=30)
    
    # Формируем текст
    if not messages:
        text = (
            "💬 <b>ОБЩИЙ ЧАТ ПИТОМЦЕВ</b>\n\n"
            "Пока здесь пусто. Питомцы ещё не начали общаться!\n"
            "Отправляй своего питомца в приключения, и он появится в чате! 🚀"
        )
    else:
        text = "💬 <b>ОБЩИЙ ЧАТ ПИТОМЦЕВ</b>\n\n"
        
        # Отображаем сообщения в обратном порядке (свежие сверху)
        for msg in reversed(messages):
            formatted = await chat_service.format_chat_message(msg)
            
            # Добавляем время
            created_at = msg.get('created_at')
            if created_at:
                time_str = created_at.strftime('%H:%M')
                date_str = created_at.strftime('%d.%m')
                
                # Проверяем, сегодня ли сообщение
                now = datetime.utcnow()
                if created_at.date() == now.date():
                    date_display = 'Сегодня'
                elif created_at.date() == (now - timedelta(days=1)).date():
                    date_display = 'Вчера'
                else:
                    date_display = date_str
                
                text += f"<i>{date_display}, {time_str}</i>\n"
            
            text += f"{formatted}\n\n"
    
    # Создаём клавиатуру
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_chat"),
                InlineKeyboardButton(text="🔙 В меню", callback_data="main_menu"),
            ]
        ]
    )
    
    # Отправляем или редактируем
    if is_callback:
        # Для CallbackQuery используем send_or_edit
        if refresh:
            await send_or_edit(
                source,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            await source.answer("🔄 Чат обновлён!")
        else:
            await source.message.answer(
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            await source.answer()
    else:
        # Для Message
        await source.answer(
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )