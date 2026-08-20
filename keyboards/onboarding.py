from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_onboarding_adventure_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для шага 1 - приключение"""
    buttons = [
        [InlineKeyboardButton(text="🌳 Отправить в Парк", callback_data="onboarding_adventure")],
        [InlineKeyboardButton(text="⏭️ Пропустить обучение", callback_data="skip_onboarding")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_onboarding_feed_keyboard(food_id: str, food_name: str) -> InlineKeyboardMarkup:
    """Клавиатура для шага 2 - кормление"""
    buttons = [
        [InlineKeyboardButton(
            text=f"🍕 Покормить {food_name}",
            callback_data=f"onboarding_feed_{food_id}"
        )],
        [InlineKeyboardButton(text="🎒 Посмотреть всю еду", callback_data="onboarding_inventory")],
        [InlineKeyboardButton(text="⏭️ Пропустить обучение", callback_data="skip_onboarding")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_onboarding_profile_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для шага 3 - профиль"""
    buttons = [
        [InlineKeyboardButton(text="✅ Всё ясно", callback_data="onboarding_next")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_onboarding_social_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для шага 4 - социальный момент"""
    buttons = [
        [InlineKeyboardButton(text="📤 Поделиться ссылкой", callback_data="onboarding_share")],
        [InlineKeyboardButton(text="❤️ Посмотреть случайного питомца", callback_data="onboarding_random_pet")],
        [InlineKeyboardButton(text="➡️ Продолжить", callback_data="onboarding_next")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_onboarding_house_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для шага 5 - дом"""
    buttons = [
        [InlineKeyboardButton(text="🛋️ Поставить мебель", callback_data="onboarding_place_furniture")],
        [InlineKeyboardButton(text="⏭️ Позже", callback_data="onboarding_next")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_onboarding_final_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для шага 6 - финал"""
    buttons = [
        [InlineKeyboardButton(text="🎁 Забрать ежедневную награду", callback_data="onboarding_daily_reward")],
        [InlineKeyboardButton(text="📋 Посмотреть задания", callback_data="onboarding_quests")],
        [InlineKeyboardButton(text="🏠 Перейти в меню", callback_data="onboarding_finish")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_skip_onboarding_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения пропуска обучения"""
    buttons = [
        [InlineKeyboardButton(text="✅ Да, пропустить", callback_data="confirm_skip_onboarding")],
        [InlineKeyboardButton(text="❌ Нет, продолжить", callback_data="cancel_skip_onboarding")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
