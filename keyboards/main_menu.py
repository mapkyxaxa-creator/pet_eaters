from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from services.social_service import SocialService
from services.feed_service import FeedService
from config import config


async def get_main_menu_keyboard(session: AsyncSession = None, user_id: int = None) -> InlineKeyboardMarkup:
    """
    Главное меню с динамическими счётчиками
    """
    
    unread_gifts = 0
    unread_notifications = 0
    pending_moderation = 0
    
    if session and user_id:
        social_service = SocialService(session)
        unread_gifts = await social_service.get_unread_gifts_count(user_id)
        
        feed_service = FeedService(session)
        unread_notifications = await feed_service.get_unread_notifications_count(user_id)
        
        # Проверяем, является ли пользователь админом
        if user_id in config.ADMIN_IDS:
            from services.moderation_service import ModerationService
            moderation_service = ModerationService(session)
            pending_moderation = await moderation_service.get_pending_count()
    
    if unread_gifts > 0:
        mailbox_text = f"📬 Почта ({unread_gifts})"
    else:
        mailbox_text = "📬 Почта"
    
    if unread_notifications > 0:
        notifications_text = f"🔔 Уведомления ({unread_notifications})"
    else:
        notifications_text = "🔔 Уведомления"
    
    # Формируем клавиатуру
    keyboard_rows = [
        # РЯД 1: ОСНОВНЫЕ ДЕЙСТВИЯ
        [
            InlineKeyboardButton(text="⚔️ Приключения", callback_data="adventures"),
            InlineKeyboardButton(text="🏠 Дом", callback_data="house"),
            InlineKeyboardButton(text="🏆 Соревнования", callback_data="competition"),
        ],
        # РЯД 2: СОЦИАЛЬНОЕ
        [
            InlineKeyboardButton(text="📸 Лента", callback_data="feed"),
            InlineKeyboardButton(text="💬 Чат питомцев", callback_data="chat"),
            InlineKeyboardButton(text=mailbox_text, callback_data="mailbox"),
        ],
        # РЯД 3: ИНВЕНТАРЬ И ПРОФИЛЬ
        [
            InlineKeyboardButton(text="🎒 Инвентарь", callback_data="inventory"),
            InlineKeyboardButton(text="🐾 Профиль", callback_data="profile"),
            InlineKeyboardButton(text="📅 Ежедневное", callback_data="daily"),
        ],
        # РЯД 4: УВЕДОМЛЕНИЯ И ПРОГРЕСС
        [
            InlineKeyboardButton(text=notifications_text, callback_data="notifications"),
            InlineKeyboardButton(text="🏆 Прогресс", callback_data="progress"),
            InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help"),
        ],
    ]
    
    # Добавляем кнопку модерации для админа
    if pending_moderation > 0:
        moderation_text = f"📸 Модерация ({pending_moderation})"
        keyboard_rows.append([
            InlineKeyboardButton(text=moderation_text, callback_data="moderation")
        ])
    elif pending_moderation == 0 and user_id and user_id in config.ADMIN_IDS:
        keyboard_rows.append([
            InlineKeyboardButton(text="📸 Модерация", callback_data="moderation")
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard_rows)


def get_main_menu_keyboard_sync() -> InlineKeyboardMarkup:
    """Синхронная версия (без счётчиков)"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚔️ Приключения", callback_data="adventures"),
                InlineKeyboardButton(text="🏠 Дом", callback_data="house"),
                InlineKeyboardButton(text="🏆 Соревнования", callback_data="competition"),
            ],
            [
                InlineKeyboardButton(text="📸 Лента", callback_data="feed"),
                InlineKeyboardButton(text="💬 Чат питомцев", callback_data="chat"),
                InlineKeyboardButton(text="📬 Почта", callback_data="mailbox"),
            ],
            [
                InlineKeyboardButton(text="🎒 Инвентарь", callback_data="inventory"),
                InlineKeyboardButton(text="🐾 Профиль", callback_data="profile"),
                InlineKeyboardButton(text="📅 Ежедневное", callback_data="daily"),
            ],
            [
                InlineKeyboardButton(text="🔔 Уведомления", callback_data="notifications"),
                InlineKeyboardButton(text="🏆 Прогресс", callback_data="progress"),
                InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help"),
            ],
        ]
    )