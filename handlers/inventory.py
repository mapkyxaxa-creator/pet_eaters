from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from services.inventory_service import InventoryService
from services.economy_service import EconomyService
from services.data_loader import data_loader
from utils.user_utils import ensure_user, ensure_pet
from utils.message_utils import send_or_edit, delete_message
from keyboards.main_menu import get_main_menu_keyboard_sync
from keyboards.food import get_inventory_keyboard
from handlers.common import get_inventory_service, get_food_service

router = Router()


@router.message(Command("inventory"))
async def cmd_inventory(message: Message, session: AsyncSession) -> None:
    """Команда /inventory — инвентарь"""
    user = await ensure_user(message, session)
    if not user:
        return
    
    # Получаем данные из workflow
    data = message.bot.data if hasattr(message.bot, 'data') else {}
    inventory_service = get_inventory_service(session, data)
    items = await inventory_service.get_inventory(user.id)
    
    items = [item for item in items if item.get("quantity", 0) > 0]
    
    if not items:
        await message.answer(
            "🎒 <b>Инвентарь пуст</b>\n\n"
            "Купи еду в магазине командой /shop",
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard_sync()
        )
        return
    
    rarity_order = {"common": 0, "uncommon": 1, "rare": 2, "epic": 3, "legendary": 4}
    items.sort(key=lambda x: rarity_order.get(x.get("rarity", "common"), 0))
    
    keyboard = get_inventory_keyboard(items)
    total_items = sum(item["quantity"] for item in items)
    
    await message.answer(
        f"🎒 <b>Инвентарь</b>\n\n"
        f"Всего предметов: {total_items}\n"
        f"💰 Монет: {user.coins}\n\n"
        f"Выбери предмет:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


async def cmd_inventory_from_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Обертка для вызова cmd_inventory из callback"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    await delete_message(callback)
    
    # Получаем данные из workflow
    data = callback.bot.data if hasattr(callback.bot, 'data') else {}
    inventory_service = get_inventory_service(session, data)
    items = await inventory_service.get_inventory(user.id)
    
    items = [item for item in items if item.get("quantity", 0) > 0]
    
    if not items:
        await callback.message.answer(
            "🎒 <b>Инвентарь пуст</b>\n\n"
            "Купи еду в магазине командой /shop",
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard_sync()
        )
        await callback.answer()
        return
    
    rarity_order = {"common": 0, "uncommon": 1, "rare": 2, "epic": 3, "legendary": 4}
    items.sort(key=lambda x: rarity_order.get(x.get("rarity", "common"), 0))
    
    keyboard = get_inventory_keyboard(items)
    total_items = sum(item["quantity"] for item in items)
    
    await callback.message.answer(
        f"🎒 <b>Инвентарь</b>\n\n"
        f"Всего предметов: {total_items}\n"
        f"💰 Монет: {user.coins}\n\n"
        f"Выбери предмет:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("inv_item_"))
async def inv_item_detail(callback: CallbackQuery, session: AsyncSession) -> None:
    """Просмотр деталей предмета"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    item_id = callback.data.split("_", 2)[2]
    
    foods = data_loader.get("foods", {})
    
    if item_id not in foods:
        await send_or_edit(
            callback,
            text=f"❌ Предмет '{item_id}' не найден в базе данных"
        )
        return
    
    food = foods.get(item_id)
    
    # Получаем данные из workflow
    data = callback.bot.data if hasattr(callback.bot, 'data') else {}
    inventory_service = get_inventory_service(session, data)
    quantity = await inventory_service.get_item_count(user.id, item_id)
    
    if quantity <= 0:
        await send_or_edit(
            callback,
            text=f"❌ У вас нет {food.get('emoji', '')} {food.get('name', item_id)} в инвентаре\n\n"
                 f"Купите его в магазине /shop",
            reply_markup=get_main_menu_keyboard_sync()
        )
        return
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🍽️ Съесть",
                    callback_data=f"inv_eat_{item_id}"
                ),
                InlineKeyboardButton(
                    text="💰 Продать",
                    callback_data=f"sell_{item_id}"
                )
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="inv_back")
            ]
        ]
    )
    
    await send_or_edit(
        callback,
        text=f"📦 <b>{food.get('emoji', '')} {food.get('name', item_id)}</b>\n\n"
             f"📊 Редкость: {food.get('rarity', 'common')}\n"
             f"🍽️ Сытость: +{food.get('hunger', 0)}\n"
             f"✨ Опыт: +{food.get('experience', 0)}\n"
             f"💰 Цена покупки: {food.get('coin_value', 0)} монет\n"
             f"💰 Цена продажи: {food.get('sell_price', 0)} монет\n"
             f"📦 Количество: {quantity} шт.\n"
             f"📝 {food.get('description', '')}",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("inv_eat_"))
async def inv_eat_item(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Поедание предмета из инвентаря (с подтверждением)"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    item_id = callback.data.split("_", 2)[2]
    
    foods = data_loader.get("foods", {})
    
    if item_id not in foods:
        await send_or_edit(callback, text=f"❌ Такой еды не существует: {item_id}")
        return
    
    food = foods.get(item_id)
    
    # Получаем данные из workflow
    data = callback.bot.data if hasattr(callback.bot, 'data') else {}
    inventory_service = get_inventory_service(session, data)
    quantity = await inventory_service.get_item_count(user.id, item_id)
    
    if quantity <= 0:
        await send_or_edit(
            callback,
            text=f"❌ У тебя нет {food.get('emoji', '')} {food.get('name', item_id)} в инвентаре!"
        )
        return
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"✅ Да, съесть {food.get('emoji', '')} {food.get('name', item_id)}",
                    callback_data=f"confirm_inv_eat_{item_id}"
                )
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data=f"inv_item_{item_id}")
            ]
        ]
    )
    
    await send_or_edit(
        callback,
        text=f"🍽️ <b>Подтверждение</b>\n\n"
             f"Ты хочешь съесть {food.get('emoji', '')} <b>{food.get('name', item_id)}</b>?\n"
             f"Сытость: +{food.get('hunger', 0)}\n"
             f"Опыт: +{food.get('experience', 0)}\n\n"
             f"У тебя есть: {quantity} шт.",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_inv_eat_"))
async def confirm_inv_eat(callback: CallbackQuery, session: AsyncSession) -> None:
    """Подтверждение поедания из инвентаря"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    item_id = callback.data.split("_", 3)[3]
    
    # Получаем данные из workflow
    data = callback.bot.data if hasattr(callback.bot, 'data') else {}
    inventory_service = get_inventory_service(session, data)
    quantity = await inventory_service.get_item_count(user.id, item_id)
    
    if quantity <= 0:
        await send_or_edit(
            callback,
            text=f"❌ У вас нет этой еды в инвентаре!\n\nКупите её в магазине /shop",
            reply_markup=get_main_menu_keyboard_sync()
        )
        return
    
    food_service = get_food_service(session, data)
    
    result = await food_service.eat_food(
        user_id=callback.from_user.id,
        pet_id=pet.id,
        food_id=item_id
    )
    
    if not result["success"]:
        await send_or_edit(
            callback,
            text=f"❌ {result['message']}",
            reply_markup=get_main_menu_keyboard_sync()
        )
        return
    
    # Проверяем достижения коллекционера
    await inventory_service.check_collection_achievements(user.id, pet.id)
    
    await send_or_edit(
        callback,
        text=result["message"],
        reply_markup=get_main_menu_keyboard_sync()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sell_"))
async def sell_item(callback: CallbackQuery, session: AsyncSession) -> None:
    """Продажа предмета"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    item_id = callback.data.split("_", 1)[1]
    
    economy_service = EconomyService(session)
    result = await economy_service.sell_item(
        user_id=callback.from_user.id,
        item_id=item_id,
        quantity=1
    )
    
    if not result["success"]:
        await send_or_edit(
            callback,
            text=f"❌ {result['message']}",
            reply_markup=get_main_menu_keyboard_sync()
        )
        return
    
    # Проверяем достижения коллекционера после продажи
    pet = await ensure_pet(callback, session, user)
    if pet:
        data = callback.bot.data if hasattr(callback.bot, 'data') else {}
        inventory_service = get_inventory_service(session, data)
        await inventory_service.check_collection_achievements(user.id, pet.id)
    
    await send_or_edit(
        callback,
        text=f"{result['message']}\n\n💰 У тебя теперь: {result['remaining_coins']} монет",
        reply_markup=get_main_menu_keyboard_sync()
    )
    await callback.answer()


@router.callback_query(F.data == "inv_back")
async def inv_back(callback: CallbackQuery, session: AsyncSession) -> None:
    """Возврат в инвентарь"""
    await delete_message(callback)
    await cmd_inventory_from_callback(callback, session)
    await callback.answer()


@router.callback_query(F.data == "inventory")
async def inventory_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Callback для кнопки 'Инвентарь'"""
    await cmd_inventory_from_callback(callback, session)