from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict, Any, Tuple


def get_food_keyboard(foods: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Клавиатура для выбора еды"""
    keyboard = []
    row = []
    
    for food in foods:
        row.append(
            InlineKeyboardButton(
                text=f"{food.get('emoji', '')} {food.get('name', '')} ({food.get('quantity', 0)})",
                callback_data=f"eat_{food.get('id', '')}"
            )
        )
        if len(row) == 2:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_shop_keyboard(foods: List[Tuple[str, Dict[str, Any]]]) -> InlineKeyboardMarkup:
    """Клавиатура для магазина"""
    keyboard = []
    row = []
    
    rarity_emojis = {
        "common": "⚪",
        "uncommon": "🟢",
        "rare": "🔵",
        "epic": "🟣",
        "legendary": "🟡"
    }
    
    for food_id, food in foods:
        rarity = food.get("rarity", "common")
        emoji = rarity_emojis.get(rarity, "")
        
        row.append(
            InlineKeyboardButton(
                text=f"{food.get('emoji', '')} {food.get('name', '')} {emoji} {food.get('coin_value', 0)}💰",
                callback_data=f"shop_buy_{food_id}"
            )
        )
        if len(row) == 2:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_inventory_keyboard(items: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Клавиатура для инвентаря"""
    keyboard = []
    row = []
    
    rarity_emojis = {
        "common": "⚪",
        "uncommon": "🟢",
        "rare": "🔵",
        "epic": "🟣",
        "legendary": "🟡"
    }
    
    for item in items:
        rarity = item.get("rarity", "common")
        emoji = rarity_emojis.get(rarity, "")
        
        row.append(
            InlineKeyboardButton(
                text=f"{item.get('emoji', '')} {item.get('name', '')} x{item.get('quantity', 0)} {emoji}",
                callback_data=f"inv_item_{item.get('id', '')}"
            )
        )
        if len(row) == 2:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)