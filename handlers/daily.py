from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from services.daily_service import DailyService
from services.quest_service import QuestService
from services.data_loader import data_loader
from utils.user_utils import ensure_user
from utils.message_utils import send_or_edit, delete_message
from keyboards.main_menu import get_main_menu_keyboard_sync

router = Router()


# ==================== ГЛАВНОЕ МЕНЮ ЕЖЕДНЕВНОГО ====================

async def show_daily_main(event: Message | CallbackQuery, session: AsyncSession) -> None:
    """Показать главное меню ежедневного с вкладками"""
    user = await ensure_user(event, session)
    if not user:
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎁 Награда", callback_data="daily_tab_reward"),
                InlineKeyboardButton(text="📋 Задания", callback_data="daily_tab_quests"),
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"),
            ]
        ]
    )

    # По умолчанию показываем вкладку с наградой
    await show_daily_reward_tab(event, session, keyboard)


# ==================== ВКЛАДКА: ЕЖЕДНЕВНАЯ НАГРАДА ====================

async def show_daily_reward_tab(event: Message | CallbackQuery, session: AsyncSession, keyboard: InlineKeyboardMarkup = None) -> None:
    """Показать вкладку с ежедневной наградой"""
    user = await ensure_user(event, session)
    if not user:
        return

    daily_service = DailyService(session)
    info = await daily_service.get_daily_info(event.from_user.id)

    if not info["success"]:
        await send_or_edit(event, info["message"])
        return

    text = "🎁 <b>Ежедневная награда</b>\n\n"
    text += f"🔥 <b>Стрик:</b> {info['streak']} дней\n"
    text += f"📊 <b>День:</b> {info['current_day']}/30\n\n"

    reward = info.get("reward")
    if reward:
        reward_type = reward.get("reward_type")
        reward_amount = reward.get("reward_amount", 0)
        reward_item = reward.get("reward_item")

        if reward_type == "coins":
            text += f"💰 <b>Награда:</b> {reward_amount} монет\n"
        elif reward_type == "item":
            foods = data_loader.get("foods", {})
            item_data = foods.get(reward_item, {})
            item_name = item_data.get("name", reward_item)
            item_emoji = item_data.get("emoji", "")
            text += f"{item_emoji} <b>Награда:</b> {item_name} x{reward_amount}\n"

    if info["can_claim"]:
        text += "\n✅ <b>Ты можешь получить награду!</b>"
        claim_button = InlineKeyboardButton(text="🎁 Получить награду", callback_data="daily_claim_reward")
    else:
        text += f"\n⏳ <b>Следующая награда:</b> {info['next_claim'].strftime('%d.%m %H:%M')}"
        claim_button = None

    # Строим клавиатуру
    if keyboard is None:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="🎁 Награда ✅", callback_data="daily_tab_reward"),
                    InlineKeyboardButton(text="📋 Задания", callback_data="daily_tab_quests"),
                ],
                [
                    InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"),
                ]
            ]
        )

    # Добавляем кнопку "Получить награду" если доступна
    keyboard_buttons = keyboard.inline_keyboard.copy()
    if claim_button:
        # Вставляем перед кнопкой "Назад"
        if keyboard_buttons and len(keyboard_buttons) > 0:
            keyboard_buttons.insert(-1, [claim_button])
        else:
            keyboard_buttons.append([claim_button])

    full_keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await send_or_edit(event, text, reply_markup=full_keyboard, parse_mode="HTML")


# ==================== ВКЛАДКА: ЗАДАНИЯ ====================

async def show_daily_quests_tab(event: Message | CallbackQuery, session: AsyncSession) -> None:
    """Показать вкладку с ежедневными заданиями"""
    user = await ensure_user(event, session)
    if not user:
        return

    quest_service = QuestService(session)
    quests = await quest_service.get_daily_quests(event.from_user.id)

    # Базовая клавиатура с вкладками
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎁 Награда", callback_data="daily_tab_reward"),
                InlineKeyboardButton(text="📋 Задания ✅", callback_data="daily_tab_quests"),
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"),
            ]
        ]
    )

    if not quests:
        text = "📋 <b>Ежедневные задания</b>\n\n"
        text += "❌ Нет доступных заданий.\n"
        text += "Задания обновляются каждый день в 00:00."
        await send_or_edit(event, text, reply_markup=keyboard, parse_mode="HTML")
        return

    text = "📋 <b>Ежедневные задания</b>\n\n"
    quest_buttons = []

    for quest in quests:
        data = quest["data"]
        progress = quest["progress"]
        completed = quest["completed"]
        claimed = quest["claimed"]
        quest_id = quest["id"]

        status = "✅" if completed and claimed else "⏳" if completed else "⬜"
        max_progress = data.get("condition_value", 1)

        text += f"{status} {data.get('emoji', '')} <b>{data.get('name', '')}</b>\n"
        text += f"   {data.get('description', '')}\n"
        text += f"   Прогресс: {progress}/{max_progress}\n"

        if data.get("reward_coins"):
            text += f"   💰 {data.get('reward_coins')} монет"
        if data.get("reward_xp"):
            text += f"  ✨ {data.get('reward_xp')} XP"
        if data.get("reward_item"):
            text += f"  🎁 {data.get('reward_item')}"
        text += "\n\n"

        if completed and not claimed:
            quest_buttons.append([
                InlineKeyboardButton(
                    text=f"🎁 Забрать награду ({data.get('emoji', '')})",
                    callback_data=f"daily_claim_quest_{quest_id}"
                )
            ])

    # Собираем финальную клавиатуру
    keyboard_buttons = keyboard.inline_keyboard.copy()
    
    # Вставляем кнопки с заданиями перед "Назад"
    if quest_buttons:
        for btn_row in quest_buttons:
            keyboard_buttons.insert(-1, btn_row)
    
    full_keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await send_or_edit(event, text, reply_markup=full_keyboard, parse_mode="HTML")


# ==================== CALLBACK'И ====================

@router.callback_query(F.data == "daily")
async def daily_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Callback для кнопки 'Ежедневное' в главном меню"""
    user = await ensure_user(callback, session)
    if not user:
        return
    await delete_message(callback)
    await show_daily_main(callback, session)
    await callback.answer()


@router.callback_query(F.data == "daily_tab_reward")
async def daily_tab_reward(callback: CallbackQuery, session: AsyncSession) -> None:
    """Переключиться на вкладку 'Награда'"""
    user = await ensure_user(callback, session)
    if not user:
        return
    await show_daily_reward_tab(callback, session)
    await callback.answer()


@router.callback_query(F.data == "daily_tab_quests")
async def daily_tab_quests(callback: CallbackQuery, session: AsyncSession) -> None:
    """Переключиться на вкладку 'Задания'"""
    user = await ensure_user(callback, session)
    if not user:
        return
    await show_daily_quests_tab(callback, session)
    await callback.answer()


@router.callback_query(F.data == "daily_claim_reward")
async def daily_claim_reward(callback: CallbackQuery, session: AsyncSession) -> None:
    """Получить ежедневную награду"""
    user = await ensure_user(callback, session)
    if not user:
        return

    daily_service = DailyService(session)
    result = await daily_service.claim_daily_reward(callback.from_user.id)

    if result["success"]:
        await callback.answer("🎉 Награда получена!", show_alert=True)
        await show_daily_reward_tab(callback, session)
    else:
        await callback.answer(f"❌ {result['message']}", show_alert=True)


@router.callback_query(F.data.startswith("daily_claim_quest_"))
async def daily_claim_quest(callback: CallbackQuery, session: AsyncSession) -> None:
    """Забрать награду за задание"""
    quest_id = callback.data.replace("daily_claim_quest_", "")

    user = await ensure_user(callback, session)
    if not user:
        return

    quest_service = QuestService(session)
    result = await quest_service.claim_quest_reward(
        user_id=callback.from_user.id,
        quest_id=quest_id
    )

    if result["success"]:
        await callback.answer("✅ Награда получена!", show_alert=True)
        await show_daily_quests_tab(callback, session)
    else:
        await callback.answer(f"❌ {result['message']}", show_alert=True)


# ==================== КОМАНДЫ ====================

@router.message(Command("daily"))
async def cmd_daily(message: Message, session: AsyncSession) -> None:
    """Команда /daily — ежедневное"""
    await show_daily_main(message, session)


@router.message(Command("quests"))
async def cmd_quests(message: Message, session: AsyncSession) -> None:
    """Команда /quests — открывает ежедневное на вкладке 'Задания'"""
    user = await ensure_user(message, session)
    if not user:
        return
    await show_daily_quests_tab(message, session)