from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_mailbox_keyboard(gifts_count: int = 0) -> InlineKeyboardMarkup:
    """Клавиатура для почты"""
    keyboard = []
    
    if gifts_count > 0:
        keyboard.append([
            InlineKeyboardButton(
                text="📥 Получить все",
                callback_data="claim_all_gifts"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton(text="🔄 Обновить", callback_data="mailbox"),
        InlineKeyboardButton(text="🗑️ Очистить", callback_data="mailbox_clear"),
    ])
    keyboard.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"),
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_gift_action_keyboard(gift_id: int, is_claimed: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура для отдельного подарка"""
    if is_claimed:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📬 Почта", callback_data="mailbox")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
            ]
        )
    
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📥 Получить подарок",
                    callback_data=f"claim_gift_{gift_id}"
                )
            ],
            [
                InlineKeyboardButton(text="📬 Почта", callback_data="mailbox"),
                InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")
            ]
        ]
    )
