from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from services.inventory_service import InventoryService
from services.data_loader import data_loader
from utils.user_utils import ensure_user, ensure_pet
from utils.message_utils import send_or_edit, delete_message
from keyboards.main_menu import get_main_menu_keyboard_sync
from keyboards.food import get_food_keyboard
from handlers.common import get_food_service, get_inventory_service

router = Router()


class EatStates(StatesGroup):
    """Состояния для еды"""
    choosing_food = State()


@router.message(Command("eat"))
async def cmd_eat(message: Message, session: AsyncSession, state: FSMContext) -> None:
    """Команда /eat — покормить питомца"""
    user = await ensure_user(message, session)
    if not user:
        return
    
    pet = await ensure_pet(message, session, user)
    if not pet:
        return
    
    # Получаем данные из workflow
    data = message.bot.data if hasattr(message.bot, 'data') else {}
    inventory_service = get_inventory_service(session, data)
    inventory = await inventory_service.get_inventory(user.id)
    
    foods = [item for item in inventory if item.get("hunger", 0) > 0 and item.get("quantity", 0) > 0]
    
    if not foods:
        await message.answer(
            "🍽️ <b>У тебя нет еды!</b>\n\n"
            "Купи еду в магазине командой /shop",
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard_sync()
        )
        return
    
    keyboard = get_food_keyboard(foods)
    
    await message.answer(
        f"🍽️ <b>Кормление питомца {pet.name}</b>\n\n"
        f"Выбери еду, которую хочешь дать питомцу:\n"
        f"Текущая сытость: {pet.get_hunger_percent():.0f}%",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await state.set_state(EatStates.choosing_food)


async def cmd_eat_from_callback(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    """Обертка для вызова cmd_eat из callback"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    await delete_message(callback)
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    # Получаем данные из workflow
    data = callback.bot.data if hasattr(callback.bot, 'data') else {}
    inventory_service = get_inventory_service(session, data)
    inventory = await inventory_service.get_inventory(user.id)
    
    foods = [item for item in inventory if item.get("hunger", 0) > 0 and item.get("quantity", 0) > 0]
    
    if not foods:
        await callback.message.answer(
            "🍽️ <b>У тебя нет еды!</b>\n\n"
            "Купи еду в магазине командой /shop",
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard_sync()
        )
        await callback.answer()
        return
    
    keyboard = get_food_keyboard(foods)
    
    await callback.message.answer(
        f"🍽️ <b>Кормление питомца {pet.name}</b>\n\n"
        f"Выбери еду, которую хочешь дать питомцу:\n"
        f"Текущая сытость: {pet.get_hunger_percent():.0f}%",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await state.set_state(EatStates.choosing_food)
    await callback.answer()


@router.callback_query(EatStates.choosing_food, F.data.startswith("eat_confirm_"))
async def process_eat_confirm(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Подтверждение поедания"""
    food_id = callback.data.split("_", 2)[2]
    
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    # Получаем данные из workflow
    data = callback.bot.data if hasattr(callback.bot, 'data') else {}
    inventory_service = get_inventory_service(session, data)
    quantity = await inventory_service.get_item_count(user.id, food_id)
    
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
        food_id=food_id
    )
    
    if not result["success"]:
        await send_or_edit(
            callback,
            text=f"❌ {result['message']}",
            reply_markup=get_main_menu_keyboard_sync()
        )
        return
    
    # Проверяем достижения коллекционера через inventory_service с правильными зависимостями
    await inventory_service.check_collection_achievements(user.id, pet.id)
    
    await send_or_edit(
        callback,
        text=result["message"],
        reply_markup=get_main_menu_keyboard_sync()
    )
    await callback.answer()


@router.callback_query(EatStates.choosing_food, F.data.startswith("eat_"))
async def process_eat(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Обработка выбора еды для поедания"""
    food_id = callback.data.split("_", 1)[1]
    
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    foods = data_loader.get("foods", {})
    
    if food_id not in foods:
        await send_or_edit(callback, text=f"❌ Такой еды не существует: {food_id}")
        return
    
    food = foods.get(food_id)
    
    # Получаем данные из workflow
    data = callback.bot.data if hasattr(callback.bot, 'data') else {}
    inventory_service = get_inventory_service(session, data)
    has_item = await inventory_service.get_item_count(user.id, food_id)
    
    if has_item <= 0:
        await send_or_edit(
            callback,
            text=f"❌ У тебя нет {food.get('emoji', '')} {food.get('name', food_id)} в инвентаре!"
        )
        return
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🍽️ Съесть {food.get('emoji', '')} {food.get('name', food_id)}",
                    callback_data=f"eat_confirm_{food_id}"
                )
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="eat_back")
            ]
        ]
    )
    
    await send_or_edit(
        callback,
        text=f"🍽️ <b>Покормить питомца?</b>\n\n"
             f"{food.get('emoji', '')} <b>{food.get('name', food_id)}</b>\n"
             f"Редкость: {food.get('rarity', 'common')}\n"
             f"Сытость: +{food.get('hunger', 0)}\n"
             f"Опыт: +{food.get('experience', 0)}\n\n"
             f"У тебя есть: {has_item} шт.",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "eat_back")
async def eat_back(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Возврат к выбору еды"""
    await state.clear()
    await delete_message(callback)
    await cmd_eat_from_callback(callback, session, state)
    await callback.answer()