from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import Dict, Any
from database.models import Pet


def get_locations_keyboard(locations: Dict[str, Any], pet: Pet) -> InlineKeyboardMarkup:
    """Клавиатура для выбора локации"""
    keyboard = []
    row = []
    
    for loc_id, loc_data in locations.items():
        min_level = loc_data.get("min_level", 0)
        is_available = pet.level >= min_level
        
        if is_available:
            text = f"{loc_data.get('emoji', '')} {loc_data.get('name', loc_id)}"
            callback = f"adv_location_{loc_id}"
        else:
            text = f"🔒 {loc_data.get('name', loc_id)} (ур.{min_level})"
            callback = "adv_locked"
        
        row.append(InlineKeyboardButton(text=text, callback_data=callback))
        
        if len(row) == 2:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="adv_back")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_adventure_confirm_keyboard(location_id: str) -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения приключения"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Отправить!", callback_data=f"adv_confirm_{location_id}"),
                InlineKeyboardButton(text="🔙 Назад", callback_data="adv_confirm_back")
            ]
        ]
    )


def get_adventure_status_keyboard(adventure_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для статуса приключения"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Обновить статус", callback_data=f"adv_status_{adventure_id}")
            ],
            [
                InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")
            ]
        ]
    )


def get_adventure_after_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после завершения приключения"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚔️ Новое приключение", callback_data="adventure_new"),
                InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")
            ]
        ]
    )