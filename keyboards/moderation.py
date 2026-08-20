from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict, Any


def get_moderation_main_keyboard() -> InlineKeyboardMarkup:
    """Главная клавиатура модерации"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📸 Список на модерацию",
                    callback_data="moderation_list"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Обновить",
                    callback_data="moderation_refresh"
                ),
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data="main_menu"
                )
            ]
        ]
    )


def get_moderation_list_keyboard(photos: List[Dict[str, Any]], page: int = 0, total: int = 0) -> InlineKeyboardMarkup:
    """Клавиатура списка фото на модерации"""
    keyboard = []
    
    for idx, item in enumerate(photos):
        photo = item["photo"]
        pet = item["pet"]
        user = item["user"]
        
        pet_name = pet.name if pet else "Без имени"
        owner_name = user.first_name or user.username or "Пользователь"
        
        button_text = f"📸 {pet_name} (@{owner_name}) #{idx+1}"
        keyboard.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"moderation_view_{photo.id}"
            )
        ])
    
    # Навигация
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=f"moderation_page_{page-1}"
            )
        )
    
    nav_buttons.append(
        InlineKeyboardButton(
            text=f"📊 {page+1}/{max(1, (total+4)//5)}",
            callback_data="moderation_info"
        )
    )
    
    if len(photos) >= 5:
        nav_buttons.append(
            InlineKeyboardButton(
                text="Вперед ➡️",
                callback_data=f"moderation_page_{page+1}"
            )
        )
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([
        InlineKeyboardButton(
            text="🔄 Обновить",
            callback_data="moderation_refresh"
        ),
        InlineKeyboardButton(
            text="🔙 Назад",
            callback_data="moderation_main"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_moderation_photo_keyboard(photo_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для отдельного фото на модерации"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Одобрить",
                    callback_data=f"moderation_approve_{photo_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"moderation_reject_{photo_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📸 Следующее",
                    callback_data="moderation_next"
                ),
                InlineKeyboardButton(
                    text="📋 Список",
                    callback_data="moderation_list"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data="moderation_main"
                )
            ]
        ]
    )


def get_moderation_approve_keyboard(photo_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения одобрения"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, одобрить",
                    callback_data=f"moderation_approve_confirm_{photo_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=f"moderation_view_{photo_id}"
                )
            ]
        ]
    )


def get_moderation_reject_keyboard(photo_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для отклонения с причиной"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚫 Не подходит",
                    callback_data=f"moderation_reject_confirm_{photo_id}_not_suitable"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📸 Низкое качество",
                    callback_data=f"moderation_reject_confirm_{photo_id}_low_quality"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚫 Непитомец",
                    callback_data=f"moderation_reject_confirm_{photo_id}_not_pet"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📸 Другое",
                    callback_data=f"moderation_reject_confirm_{photo_id}_other"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=f"moderation_view_{photo_id}"
                )
            ]
        ]
    )


def get_moderation_success_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после успешного действия"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📸 Следующее",
                    callback_data="moderation_next"
                ),
                InlineKeyboardButton(
                    text="📋 Список",
                    callback_data="moderation_list"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data="moderation_main"
                )
            ]
        ]
    )


def get_moderation_empty_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура когда нет фото на модерации"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Обновить",
                    callback_data="moderation_refresh"
                ),
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data="main_menu"
                )
            ]
        ]
    )
