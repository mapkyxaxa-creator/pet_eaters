from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories.user_repository import UserRepository
from database.repositories.pet_repository import PetRepository
from database.models import Pet
from services.social_service import SocialService
from services.level_service import LevelService
from services.feed_service import FeedService
from services.data_loader import data_loader
from utils.user_utils import ensure_user, ensure_pet
from utils.message_utils import send_or_edit, delete_message
from keyboards.main_menu import get_main_menu_keyboard_sync

router = Router()


class GiftStates(StatesGroup):
    """Состояния для подарков"""
    choosing_item = State()
    entering_quantity = State()
    entering_message = State()
    confirming = State()


# ============================================================
# 1. ПРОСМОТР ПРОФИЛЯ ПОЛЬЗОВАТЕЛЯ
# ============================================================

@router.message(Command("view"))
async def cmd_view(message: Message, session: AsyncSession) -> None:
    """Команда /view @username - просмотр профиля другого игрока"""
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(
            "❌ Укажи пользователя: /view @username\n"
            "Например: /view @john_doe"
        )
        return
    
    username = parts[1].replace("@", "").strip()
    await show_user_profile(message, session, username)


async def show_user_profile(message: Message, session: AsyncSession, username: str) -> None:
    """Показать профиль другого пользователя"""
    user_repo = UserRepository(session)
    user = await user_repo.get_by_username(username)
    
    if not user:
        await message.answer(f"❌ Пользователь @{username} не найден")
        return
    
    pet_repo = PetRepository(session)
    pet = await pet_repo.get_by_user_id(user.id)
    
    if not pet:
        await message.answer(f"🐾 У пользователя @{username} еще нет питомца")
        return
    
    social_service = SocialService(session)
    viewer_id = message.from_user.id
    
    profile_data = await social_service.get_pet_profile(viewer_id, pet.id)
    if not profile_data["success"]:
        await message.answer(f"❌ {profile_data['message']}")
        return
    
    characters = data_loader.get("characters", {})
    character = characters.get(pet.character_id, {})
    
    hunger_percent = pet.get_hunger_percent()
    hunger_emoji = "😊"
    if hunger_percent >= 150:
        hunger_emoji = "💀"
    elif hunger_percent >= 120:
        hunger_emoji = "🤢"
    elif hunger_percent >= 100:
        hunger_emoji = "😋"
    
    level_service = LevelService(session)
    xp_for_next = level_service.get_xp_for_level(pet.level)
    xp_progress = int((pet.experience / xp_for_next) * 100) if xp_for_next > 0 else 0
    
    # ===== ПРОВЕРЯЕМ ПОДПИСКУ =====
    viewer_pet = await pet_repo.get_by_user_id(viewer_id)
    feed_service = FeedService(session)
    is_subscribed = False
    if viewer_pet:
        is_subscribed = await feed_service.is_subscribed(viewer_pet.id, pet.id)
    
    text = f"🐾 <b>{pet.name}</b>\n"
    text += f"{character.get('emoji', '')} <b>Характер:</b> {character.get('name', 'Неизвестно')}\n\n"
    text += f"📊 <b>Уровень:</b> {pet.level} ({pet.experience}/{xp_for_next} XP, {xp_progress}%)\n"
    text += f"{hunger_emoji} <b>Сытость:</b> {hunger_percent:.0f}%\n"
    text += f"❤️ <b>Лайков:</b> {pet.total_likes}\n"
    text += f"👑 <b>Титул:</b> {profile_data['title_text']}\n"
    text += f"🆔 <b>ID:</b> <code>{pet.game_id}</code>\n"
    text += f"👤 <b>Владелец:</b> {user.first_name or user.username}\n"
    
    keyboard = []
    
    if profile_data["has_liked"]:
        keyboard.append([InlineKeyboardButton(
            text="💔 Убрать лайк",
            callback_data=f"unlike_{pet.id}"
        )])
    else:
        keyboard.append([InlineKeyboardButton(
            text="❤️ Поставить лайк",
            callback_data=f"like_{pet.id}"
        )])
    
    # ===== КНОПКА ПОДПИСКИ =====
    if is_subscribed:
        keyboard.append([InlineKeyboardButton(
            text="➖ Отписаться",
            callback_data=f"unsubscribe_{pet.id}"
        )])
    else:
        keyboard.append([InlineKeyboardButton(
            text="➕ Подписаться",
            callback_data=f"subscribe_{pet.id}"
        )])
    
    keyboard.append([InlineKeyboardButton(
        text="🎁 Отправить подарок",
        callback_data=f"gift_{pet.id}"
    )])
    
    keyboard.append([InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="main_menu"
    )])
    
    await message.answer_photo(
        photo=pet.photo_file_id,
        caption=text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML"
    )


# ============================================================
# 2. ЛАЙКИ
# ============================================================

@router.callback_query(F.data.startswith("like_"))
async def like_pet(callback: CallbackQuery, session: AsyncSession) -> None:
    """Поставить лайк питомцу"""
    pet_id = int(callback.data.split("_")[1])
    
    user = await ensure_user(callback, session)
    if not user:
        return
    
    social_service = SocialService(session)
    result = await social_service.like_pet(callback.from_user.id, pet_id)
    
    if result["success"]:
        message = result["message"]
        if result.get("unlocked_titles"):
            titles_text = "\n\n🏆 <b>Новые титулы!</b>\n"
            for title in result["unlocked_titles"]:
                titles_text += f"{title['emoji']} {title['name']} — {title['description']}\n"
            message += titles_text
        
        await callback.answer(message, show_alert=False)
        
        await callback.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="💔 Убрать лайк",
                            callback_data=f"unlike_{pet_id}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="➕ Подписаться",
                            callback_data=f"subscribe_{pet_id}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="🎁 Отправить подарок",
                            callback_data=f"gift_{pet_id}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="🔙 Назад",
                            callback_data="main_menu"
                        )
                    ]
                ]
            )
        )
    else:
        await callback.answer(f"❌ {result['message']}", show_alert=True)


@router.callback_query(F.data.startswith("unlike_"))
async def unlike_pet(callback: CallbackQuery, session: AsyncSession) -> None:
    """Убрать лайк"""
    pet_id = int(callback.data.split("_")[1])
    
    user = await ensure_user(callback, session)
    if not user:
        return
    
    social_service = SocialService(session)
    result = await social_service.unlike_pet(callback.from_user.id, pet_id)
    
    if result["success"]:
        await callback.answer(result["message"], show_alert=False)
        await callback.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="❤️ Поставить лайк",
                            callback_data=f"like_{pet_id}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="➕ Подписаться",
                            callback_data=f"subscribe_{pet_id}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="🎁 Отправить подарок",
                            callback_data=f"gift_{pet_id}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="🔙 Назад",
                            callback_data="main_menu"
                        )
                    ]
                ]
            )
        )
    else:
        await callback.answer(f"❌ {result['message']}", show_alert=True)


# ============================================================
# 3. ПОДПИСКИ В ПРОФИЛЕ
# ============================================================

@router.callback_query(F.data.startswith("subscribe_"))
async def subscribe_from_profile(callback: CallbackQuery, session: AsyncSession) -> None:
    """Подписаться на питомца из профиля"""
    target_pet_id = int(callback.data.split("_")[1])
    
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    if pet.id == target_pet_id:
        await callback.answer("❌ Нельзя подписаться на себя", show_alert=True)
        return
    
    feed_service = FeedService(session)
    result = await feed_service.subscribe(pet.id, target_pet_id)
    
    await callback.answer(result["message"], show_alert=False)
    
    # Обновляем клавиатуру
    await callback.message.edit_reply_markup(
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="❤️ Поставить лайк",
                        callback_data=f"like_{target_pet_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="➖ Отписаться",
                        callback_data=f"unsubscribe_{target_pet_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🎁 Отправить подарок",
                        callback_data=f"gift_{target_pet_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔙 Назад",
                        callback_data="main_menu"
                    )
                ]
            ]
        )
    )


@router.callback_query(F.data.startswith("unsubscribe_"))
async def unsubscribe_from_profile(callback: CallbackQuery, session: AsyncSession) -> None:
    """Отписаться от питомца из профиля"""
    target_pet_id = int(callback.data.split("_")[1])
    
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    feed_service = FeedService(session)
    result = await feed_service.unsubscribe(pet.id, target_pet_id)
    
    await callback.answer(result["message"], show_alert=False)
    
    # Обновляем клавиатуру
    await callback.message.edit_reply_markup(
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="❤️ Поставить лайк",
                        callback_data=f"like_{target_pet_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="➕ Подписаться",
                        callback_data=f"subscribe_{target_pet_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🎁 Отправить подарок",
                        callback_data=f"gift_{target_pet_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔙 Назад",
                        callback_data="main_menu"
                    )
                ]
            ]
        )
    )


# ============================================================
# 4. ПОДАРКИ
# ============================================================

@router.callback_query(F.data.regexp(r"^gift_\d+$"))
async def start_gift(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Начать отправку подарка"""
    pet_id = int(callback.data.split("_")[1])
    
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet_repo = PetRepository(session)
    pet = await pet_repo.get_by_id(pet_id)
    if not pet:
        await callback.answer("❌ Питомец не найден", show_alert=True)
        return
    
    await state.update_data(
        to_user_id=pet.user_id,
        to_pet_name=pet.name
    )
    
    await show_gift_item_selection(callback, state, session, user, pet.name)


async def show_gift_item_selection(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user,
    to_pet_name: str
) -> None:
    """Показать список еды для подарка"""
    from services.inventory_service import InventoryService
    inventory_service = InventoryService(session)
    items = await inventory_service.get_inventory(user.id)
    
    foods = [item for item in items if item.get("hunger", 0) > 0 and item.get("quantity", 0) > 0]
    
    if not foods:
        chat_id = callback.message.chat.id
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.bot.send_message(
            chat_id=chat_id,
            text="❌ У тебя нет еды для подарка!\nКупи еду в магазине /shop",
            reply_markup=get_main_menu_keyboard_sync()
        )
        await callback.answer()
        return
    
    keyboard = []
    for food in foods[:8]:
        keyboard.append([
            InlineKeyboardButton(
                text=f"{food.get('emoji', '')} {food.get('name', '')} x{food.get('quantity', 0)}",
                callback_data=f"gift_item_{food.get('id', '')}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])
    
    chat_id = callback.message.chat.id
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    await callback.bot.send_message(
        chat_id=chat_id,
        text=f"🎁 <b>Отправка подарка</b>\n\n"
             f"Кому: {to_pet_name}\n\n"
             f"Выбери, что хочешь подарить:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML"
    )
    
    await state.set_state(GiftStates.choosing_item)
    await callback.answer()


@router.callback_query(GiftStates.choosing_item, F.data.startswith("gift_item_"))
async def gift_choose_item(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Выбор предмета для подарка"""
    item_id = callback.data.split("_", 2)[2]
    await state.update_data(item_id=item_id)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1", callback_data="gift_qty_1"),
                InlineKeyboardButton(text="3", callback_data="gift_qty_3"),
                InlineKeyboardButton(text="5", callback_data="gift_qty_5"),
                InlineKeyboardButton(text="10", callback_data="gift_qty_10")
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="gift_back")
            ]
        ]
    )
    
    foods = data_loader.get("foods", {})
    food = foods.get(item_id, {})
    
    try:
        await callback.message.edit_text(
            f"🎁 <b>Отправка подарка</b>\n\n"
            f"Выбрано: {food.get('emoji', '')} {food.get('name', item_id)}\n\n"
            f"Сколько штук хочешь подарить?",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception:
        chat_id = callback.message.chat.id
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.bot.send_message(
            chat_id=chat_id,
            text=f"🎁 <b>Отправка подарка</b>\n\n"
                 f"Выбрано: {food.get('emoji', '')} {food.get('name', item_id)}\n\n"
                 f"Сколько штук хочешь подарить?",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    
    await state.set_state(GiftStates.entering_quantity)
    await callback.answer()


@router.callback_query(GiftStates.entering_quantity, F.data.startswith("gift_qty_"))
async def gift_choose_quantity(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Выбор количества"""
    quantity = int(callback.data.split("_")[2])
    await state.update_data(quantity=quantity)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Без сообщения", callback_data="gift_msg_none")
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="gift_back_qty")
            ]
        ]
    )
    
    try:
        await callback.message.edit_text(
            f"🎁 <b>Отправка подарка</b>\n\n"
            f"Количество: {quantity} шт.\n\n"
            f"Хочешь добавить сообщение?\n"
            f"Напиши его в чат (до 100 символов) или нажми 'Без сообщения'",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception:
        chat_id = callback.message.chat.id
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.bot.send_message(
            chat_id=chat_id,
            text=f"🎁 <b>Отправка подарка</b>\n\n"
                 f"Количество: {quantity} шт.\n\n"
                 f"Хочешь добавить сообщение?\n"
                 f"Напиши его в чат (до 100 символов) или нажми 'Без сообщения'",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    
    await state.set_state(GiftStates.entering_message)
    await callback.answer()


@router.callback_query(GiftStates.entering_message, F.data == "gift_msg_none")
async def gift_no_message(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Без сообщения"""
    await state.update_data(message=None)
    await confirm_gift(callback, state, session)


@router.message(GiftStates.entering_message)
async def gift_enter_message(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Ввод сообщения"""
    text = message.text.strip()
    if len(text) > 100:
        await message.answer("❌ Сообщение не должно превышать 100 символов")
        return
    
    await state.update_data(message=text)
    await confirm_gift_from_message(message, state, session)


async def confirm_gift(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Подтверждение отправки подарка"""
    data = await state.get_data()
    to_pet_name = data.get("to_pet_name")
    item_id = data.get("item_id")
    quantity = data.get("quantity", 1)
    message = data.get("message")
    
    foods = data_loader.get("foods", {})
    food = foods.get(item_id, {})
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Отправить", callback_data="gift_confirm"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="gift_cancel")
            ]
        ]
    )
    
    text = f"🎁 <b>Подтверждение подарка</b>\n\n"
    text += f"Кому: {to_pet_name}\n"
    text += f"Подарок: {food.get('emoji', '')} {food.get('name', item_id)} x{quantity}\n"
    if message:
        text += f"Сообщение: {message}\n"
    
    chat_id = callback.message.chat.id
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    await callback.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(GiftStates.confirming)


async def confirm_gift_from_message(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Подтверждение отправки подарка из сообщения"""
    data = await state.get_data()
    to_pet_name = data.get("to_pet_name")
    item_id = data.get("item_id")
    quantity = data.get("quantity", 1)
    msg = data.get("message")
    
    foods = data_loader.get("foods", {})
    food = foods.get(item_id, {})
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Отправить", callback_data="gift_confirm"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="gift_cancel")
            ]
        ]
    )
    
    text = f"🎁 <b>Подтверждение подарка</b>\n\n"
    text += f"Кому: {to_pet_name}\n"
    text += f"Подарок: {food.get('emoji', '')} {food.get('name', item_id)} x{quantity}\n"
    if msg:
        text += f"Сообщение: {msg}\n"
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(GiftStates.confirming)


@router.callback_query(GiftStates.confirming, F.data == "gift_confirm")
async def gift_confirm_send(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Отправить подарок"""
    data = await state.get_data()
    
    from_user_id = callback.from_user.id
    to_user_id = data.get("to_user_id")
    item_id = data.get("item_id")
    quantity = data.get("quantity", 1)
    message = data.get("message")
    
    social_service = SocialService(session)
    result = await social_service.send_gift(
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        item_id=item_id,
        quantity=quantity,
        message=message,
        bot=callback.bot
    )
    
    await state.clear()
    
    chat_id = callback.message.chat.id
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    if result["success"]:
        await callback.bot.send_message(
            chat_id=chat_id,
            text=f"🎉 <b>Подарок отправлен!</b>\n\n"
                 f"{result['item_emoji']} {result['item_name']} x{result['quantity']}\n\n"
                 f"Получатель получит уведомление.",
            reply_markup=get_main_menu_keyboard_sync(),
            parse_mode="HTML"
        )
    else:
        await callback.bot.send_message(
            chat_id=chat_id,
            text=f"❌ {result['message']}",
            reply_markup=get_main_menu_keyboard_sync(),
            parse_mode="HTML"
        )
    
    await callback.answer()


@router.callback_query(F.data == "gift_cancel")
async def gift_cancel(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Отмена отправки подарка"""
    await state.clear()
    
    chat_id = callback.message.chat.id
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    await callback.bot.send_message(
        chat_id=chat_id,
        text="❌ Отправка подарка отменена",
        reply_markup=get_main_menu_keyboard_sync()
    )
    await callback.answer()


@router.callback_query(F.data == "gift_back")
async def gift_back(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Назад к выбору предмета"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    data = await state.get_data()
    to_pet_name = data.get("to_pet_name", "")
    
    await state.set_state(GiftStates.choosing_item)
    await show_gift_item_selection(callback, state, session, user, to_pet_name)


@router.callback_query(F.data == "gift_back_qty")
async def gift_back_qty(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Назад к выбору количества"""
    data = await state.get_data()
    item_id = data.get("item_id")
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1", callback_data="gift_qty_1"),
                InlineKeyboardButton(text="3", callback_data="gift_qty_3"),
                InlineKeyboardButton(text="5", callback_data="gift_qty_5"),
                InlineKeyboardButton(text="10", callback_data="gift_qty_10")
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="gift_back")
            ]
        ]
    )
    
    foods = data_loader.get("foods", {})
    food = foods.get(item_id, {})
    
    try:
        await callback.message.edit_text(
            f"🎁 <b>Отправка подарка</b>\n\n"
            f"Выбрано: {food.get('emoji', '')} {food.get('name', item_id)}\n\n"
            f"Сколько штук хочешь подарить?",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception:
        chat_id = callback.message.chat.id
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.bot.send_message(
            chat_id=chat_id,
            text=f"🎁 <b>Отправка подарка</b>\n\n"
                 f"Выбрано: {food.get('emoji', '')} {food.get('name', item_id)}\n\n"
                 f"Сколько штук хочешь подарить?",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    
    await state.set_state(GiftStates.entering_quantity)
    await callback.answer()

# ============================================================
# 4. СЛУЧАЙНЫЙ ПИТОМЕЦ
# ============================================================

@router.callback_query(F.data == "random_pet")
async def handle_random_pet(callback: CallbackQuery, session: AsyncSession) -> None:
    """Показать случайного питомца"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    social_service = SocialService(session)
    random_pet = await social_service.get_random_pet(pet.id)
    
    if not random_pet:
        await callback.answer("😅 Пока нет других питомцев")
        return
    
    characters = data_loader.get("characters", {})
    character = characters.get(random_pet.character_id, {})
    hunger_percent = random_pet.get_hunger_percent()
    
    text = f"🐾 <b>Случайный питомец</b>\n\n"
    text += f"Имя: {random_pet.name}\n"
    text += f"Характер: {character.get('emoji', '')} {character.get('name', 'Неизвестно')}\n"
    text += f"Уровень: {random_pet.level}\n"
    text += f"Сытость: {hunger_percent:.0f}%\n"
    text += f"❤️ Лайков: {random_pet.total_likes}\n"
    text += f"🆔 ID: <code>{random_pet.game_id}</code>\n\n"
    text += "<i>Можешь поставить лайк этому питомцу!</i>"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❤️ Поставить лайк", callback_data=f"like_{random_pet.id}")],
        [InlineKeyboardButton(text="🔄 Другого", callback_data="random_pet")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()
