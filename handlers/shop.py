from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from services.economy_service import EconomyService
from services.payment_service import PaymentService
from services.data_loader import data_loader
from utils.user_utils import ensure_user, ensure_pet, get_user_id
from utils.message_utils import send_or_edit, delete_message
from keyboards.main_menu import get_main_menu_keyboard, get_main_menu_keyboard_sync
from keyboards.food import get_shop_keyboard

router = Router()


class ShopStates(StatesGroup):
    """Состояния для магазина"""
    browsing = State()


# ==================== ГЛАВНОЕ МЕНЮ МАГАЗИНА ====================

async def show_shop_main(event: Message | CallbackQuery, session: AsyncSession, state: FSMContext = None) -> None:
    """Показать главное меню магазина с вкладками"""
    user = await ensure_user(event, session)
    if not user:
        return

    pet = await ensure_pet(event, session, user)
    if not pet:
        return

    payment_service = PaymentService(session)
    balance = await payment_service.get_balance(get_user_id(event))

    text = (
        f"🏪 <b>Магазин</b>\n\n"
        f"💰 У тебя: {user.coins} 🪙 монет\n"
        f"🐾 У тебя: {balance.get('premium_currency', 0)} лапок\n\n"
        f"<b>Выбери раздел:</b>"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🍕 Еда", callback_data="shop_tab_food"),
                InlineKeyboardButton(text="🔒 Лапки", callback_data="shop_tab_premium_currency"),
            ],
            [
                InlineKeyboardButton(text="🔒 Косметика", callback_data="shop_tab_cosmetics"),
                InlineKeyboardButton(text="🔒 Premium", callback_data="shop_tab_premium"),
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"),
            ]
        ]
    )

    if state:
        await state.clear()

    await send_or_edit(event, text, reply_markup=keyboard)


# ==================== ВКЛАДКА: ЕДА ====================

async def show_shop_food(event: Message | CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    """Показать магазин еды"""
    user = await ensure_user(event, session)
    if not user:
        return

    foods = data_loader.get("foods", {})
    rarity_order = {"common": 0, "uncommon": 1, "rare": 2, "epic": 3, "legendary": 4}
    sorted_foods = sorted(
        foods.items(),
        key=lambda x: rarity_order.get(x[1].get("rarity", "common"), 0)
    )

    keyboard = get_shop_keyboard(sorted_foods)
    
    back_button = InlineKeyboardButton(text="🔙 В меню магазина", callback_data="shop_main")
    new_keyboard = keyboard.inline_keyboard + [[back_button]]
    keyboard = InlineKeyboardMarkup(inline_keyboard=new_keyboard)

    await send_or_edit(
        event,
        f"🍕 <b>Магазин еды</b>\n\n"
        f"💰 У тебя: {user.coins} монет\n\n"
        f"Выбери товар для покупки:",
        reply_markup=keyboard
    )

    if isinstance(event, CallbackQuery):
        await event.answer()
    
    if state:
        await state.set_state(ShopStates.browsing)


# ==================== ЗАГЛУШКИ ДЛЯ ПЛАТНЫХ РАЗДЕЛОВ ====================

async def show_paywall(event: Message | CallbackQuery, session: AsyncSession, section_name: str) -> None:
    """Показать заглушку для платного раздела"""
    text = (
        f"🔒 <b>{section_name}</b>\n\n"
        f"Этот раздел будет доступен в следующем обновлении.\n\n"
        f"💡 Следи за новостями в игре!\n\n"
        f"А пока ты можешь:\n"
        f"• 🍕 Покупать еду за монеты\n"
        f"• ⚔️ Отправляться в приключения\n"
        f"• 🏠 Обустраивать дом\n"
        f"• 🐾 Общаться с другими игроками"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 В меню магазина", callback_data="shop_main")]
        ]
    )

    await send_or_edit(event, text, reply_markup=keyboard)


# ==================== CALLBACK'И ДЛЯ ПЛАТНЫХ РАЗДЕЛОВ ====================

@router.callback_query(F.data == "shop_tab_premium_currency")
async def shop_tab_premium_currency(callback: CallbackQuery, session: AsyncSession) -> None:
    """Заглушка: Лапки"""
    await show_paywall(callback, session, "🐾 Магазин лапок")


@router.callback_query(F.data == "shop_tab_cosmetics")
async def shop_tab_cosmetics(callback: CallbackQuery, session: AsyncSession) -> None:
    """Заглушка: Косметика"""
    await show_paywall(callback, session, "🎨 Магазин косметики")


@router.callback_query(F.data == "shop_tab_premium")
async def shop_tab_premium(callback: CallbackQuery, session: AsyncSession) -> None:
    """Заглушка: Premium"""
    await show_paywall(callback, session, "👑 Premium подписка")


# ==================== ПОКУПКА ЕДЫ ====================

@router.callback_query(ShopStates.browsing, F.data.startswith("shop_buy_"))
async def shop_buy(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Покупка товара (еда)"""
    user = await ensure_user(callback, session)
    if not user:
        return

    food_id = callback.data.split("_", 2)[2]

    foods = data_loader.get("foods", {})
    food = foods.get(food_id)

    if not food:
        await send_or_edit(callback, text="❌ Такой еды не существует")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1 шт.", callback_data=f"shop_quantity_1_{food_id}"),
                InlineKeyboardButton(text="5 шт.", callback_data=f"shop_quantity_5_{food_id}"),
                InlineKeyboardButton(text="10 шт.", callback_data=f"shop_quantity_10_{food_id}"),
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="shop_tab_food")
            ]
        ]
    )

    await send_or_edit(
        callback,
        text=f"🛒 <b>{food.get('emoji', '')} {food.get('name', food_id)}</b>\n\n"
             f"💰 Цена: {food.get('coin_value', 0)} монет/шт.\n"
             f"🍽️ Сытость: +{food.get('hunger', 0)}\n"
             f"✨ Опыт: +{food.get('experience', 0)}\n"
             f"📊 Редкость: {food.get('rarity', 'common')}\n\n"
             f"Выбери количество:",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("shop_quantity_"))
async def shop_quantity(callback: CallbackQuery, session: AsyncSession) -> None:
    """Покупка с выбранным количеством (еда)"""
    user = await ensure_user(callback, session)
    if not user:
        return

    parts = callback.data.split("_", 3)
    quantity = int(parts[2])
    food_id = parts[3]

    economy_service = EconomyService(session)
    result = await economy_service.buy_item(
        user_id=callback.from_user.id,
        item_id=food_id,
        quantity=quantity
    )

    if not result["success"]:
        await send_or_edit(
            callback,
            text=f"❌ {result['message']}",
            reply_markup=get_main_menu_keyboard()
        )
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Продолжить покупки", callback_data="shop_tab_food")],
            [InlineKeyboardButton(text="🔙 В меню магазина", callback_data="shop_main")]
        ]
    )

    await send_or_edit(
        callback,
        text=f"{result['message']}\n\n💰 Осталось монет: {result['remaining_coins']}",
        reply_markup=keyboard
    )
    await callback.answer()


# ==================== КОМАНДЫ ====================

@router.callback_query(F.data == "shop")
async def shop_callback(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Кнопка Магазин в главном меню"""
    await show_shop_main(callback, session, state)


@router.callback_query(F.data == "shop_main")
async def shop_main_callback(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Назад в главное меню магазина"""
    await show_shop_main(callback, session, state)


@router.callback_query(F.data == "shop_tab_food")
async def shop_tab_food(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Вкладка Еда"""
    await show_shop_food(callback, session, state)


@router.message(Command("shop"))
async def cmd_shop(message: Message, session: AsyncSession, state: FSMContext) -> None:
    """Команда /shop"""
    await show_shop_main(message, session, state)


@router.message(Command("shop_premium"))
async def cmd_shop_premium(message: Message, session: AsyncSession) -> None:
    """Команда /shop_premium — заглушка"""
    await show_paywall(message, session, "🐾 Магазин лапок")


@router.message(Command("cosmetics"))
async def cmd_cosmetics(message: Message, session: AsyncSession) -> None:
    """Команда /cosmetics — заглушка"""
    await show_paywall(message, session, "🎨 Магазин косметики")


@router.message(Command("premium"))
async def cmd_premium(message: Message, session: AsyncSession) -> None:
    """Команда /premium — заглушка"""
    await show_paywall(message, session, "👑 Premium подписка")