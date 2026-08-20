from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict, Any


def get_house_main_keyboard(house_level: int = 1, can_claim: bool = True) -> InlineKeyboardMarkup:
    """Главное меню дома"""
    keyboard = [
        [
            InlineKeyboardButton(text="📊 Информация", callback_data="house_info"),
            InlineKeyboardButton(text="⬆️ Улучшить", callback_data="house_upgrade")
        ],
        [
            InlineKeyboardButton(text="🛋️ Мебель", callback_data="house_furniture"),
            InlineKeyboardButton(text="🏠 Комнаты", callback_data="house_rooms")
        ],
        [
            InlineKeyboardButton(text="🏠 Шаблоны", callback_data="house_templates"),
            InlineKeyboardButton(text="👥 Посетить дом", callback_data="house_visit")
        ],
        [
            InlineKeyboardButton(
                text="🎁 Забрать бонус" if can_claim else "⏳ Бонус уже получен",
                callback_data="house_bonus" if can_claim else "house_bonus_disabled"
            )
        ],
        [
            InlineKeyboardButton(text="🔙 В главное меню", callback_data="main_menu")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_house_rooms_keyboard(rooms: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Клавиатура для выбора комнаты (без замков)"""
    keyboard = []
    for room in rooms:
        keyboard.append([
            InlineKeyboardButton(
                text=f"{room.get('emoji', '📦')} {room.get('name', room.get('type', ''))}",
                callback_data=f"house_room_{room.get('type')}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="house_main")
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_house_room_keyboard(room_type: str, furniture_count: int) -> InlineKeyboardMarkup:
    """Клавиатура для конкретной комнаты"""
    keyboard = [
        [
            InlineKeyboardButton(
                text=f"🪑 Мебель ({furniture_count})",
                callback_data=f"house_room_furniture_{room_type}"
            )
        ],
        [
            InlineKeyboardButton(
                text="🛒 Купить мебель",
                callback_data=f"house_buy_furniture_{room_type}"
            )
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="house_rooms")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_house_furniture_keyboard(furniture_list: List[Dict[str, Any]], room_type: str) -> InlineKeyboardMarkup:
    """Клавиатура для списка мебели в комнате"""
    keyboard = []
    for f in furniture_list:
        keyboard.append([
            InlineKeyboardButton(
                text=f"{f.get('emoji', '📦')} {f.get('name', '')} x{f.get('quantity', 1)}",
                callback_data=f"house_furniture_detail_{room_type}_{f.get('id')}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(text="🏠 Вся мебель", callback_data=f"house_all_furniture_{room_type}")
    ])
    keyboard.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data=f"house_room_{room_type}")
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_house_furniture_detail_keyboard(room_type: str, furniture_id: str) -> InlineKeyboardMarkup:
    """Клавиатура для деталей мебели"""
    keyboard = [
        [
            InlineKeyboardButton(
                text="🗑️ Убрать",
                callback_data=f"house_remove_furniture_{room_type}_{furniture_id}"
            )
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data=f"house_room_furniture_{room_type}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_house_buy_furniture_keyboard(furniture_items: List[Dict[str, Any]], room_type: str) -> InlineKeyboardMarkup:
    """Клавиатура для покупки мебели"""
    keyboard = []
    for f in furniture_items[:10]:  # Ограничиваем количество
        price_text = ""
        if f.get("price_coins", 0) > 0:
            price_text = f"{f['price_coins']}🪙"
        if f.get("price_premium", 0) > 0:
            if price_text:
                price_text += " "
            price_text += f"{f['price_premium']}🐾"

        keyboard.append([
            InlineKeyboardButton(
                text=f"{f.get('emoji', '📦')} {f.get('name', '')} ({price_text})",
                callback_data=f"house_buy_{room_type}_{f.get('id')}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data=f"house_room_{room_type}")
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_house_templates_keyboard(templates: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Клавиатура для выбора шаблона дома"""
    keyboard = []
    for template in templates:
        status = "🔒" if template.get("is_locked", False) else "🆓"
        price_text = f"{template.get('cost', 0)}🪙" if template.get('cost', 0) > 0 else "бесплатно"
        keyboard.append([
            InlineKeyboardButton(
                text=f"{template.get('emoji', '🏠')} {template.get('name', '')} ({price_text})",
                callback_data=f"house_template_{template.get('id')}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="house_main")
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_house_visit_keyboard(available_houses: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Клавиатура для выбора дома для посещения"""
    keyboard = []
    for house in available_houses[:10]:  # Ограничиваем количество
        keyboard.append([
            InlineKeyboardButton(
                text=f"{house.get('emoji', '🏠')} {house.get('pet_name', 'Питомец')} (ур. {house.get('level', 1)})",
                callback_data=f"house_visit_pet_{house.get('pet_id')}"
            )
        ])

    if not available_houses:
        keyboard.append([
            InlineKeyboardButton(text="😴 Нет доступных домов", callback_data="house_main")
        ])

    keyboard.append([
        InlineKeyboardButton(text="🔄 Обновить", callback_data="house_visit_refresh"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="house_main")
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_house_upgrade_keyboard(house_level: int, max_level: int) -> InlineKeyboardMarkup:
    """Клавиатура для улучшения дома"""
    keyboard = []

    if house_level < max_level:
        keyboard.append([
            InlineKeyboardButton(
                text=f"⬆️ Улучшить до {house_level + 1} уровня",
                callback_data="house_upgrade_confirm"
            )
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(text="✅ Максимальный уровень", callback_data="house_main")
        ])

    keyboard.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="house_main")
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)