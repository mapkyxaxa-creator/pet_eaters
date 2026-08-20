import logging
import random
import asyncio

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories.user_repository import UserRepository
from database.repositories.pet_repository import PetRepository
from database.repositories.inventory_repository import InventoryRepository
from database.repositories.house_repository import HouseRepository
from states.onboarding import OnboardingStates
from keyboards.onboarding import (
    get_onboarding_adventure_keyboard,
    get_onboarding_feed_keyboard,
    get_onboarding_profile_keyboard,
    get_onboarding_social_keyboard,
    get_onboarding_house_keyboard,
    get_onboarding_final_keyboard,
    get_skip_onboarding_keyboard
)
from keyboards.main_menu import get_main_menu_keyboard_sync
from services.data_loader import data_loader
from services.adventure_service import AdventureService
from services.level_service import LevelService
from services.achievement_service import AchievementService
from services.food_service import FoodService
from services.daily_service import DailyService
from services.quest_service import QuestService
from services.house_service import HouseService

logger = logging.getLogger(__name__)

router = Router()


def get_food_by_id(food_id: str):
    foods = data_loader.get("foods", {})
    return foods.get(food_id)


def extract_food_id(callback_data: str) -> str:
    """Извлечь food_id из callback_data, поддерживая ID с подчёркиваниями"""
    return callback_data.split("_", 2)[2]


async def get_user_from_event(event: Message | CallbackQuery, session: AsyncSession):
    """Получить пользователя из события с прямой проверкой"""
    from database.repositories.user_repository import UserRepository
    
    if isinstance(event, Message):
        telegram_id = event.from_user.id if event.from_user else None
    else:
        telegram_id = event.from_user.id if event.from_user else None
    
    if not telegram_id:
        return None
    
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(telegram_id)
    
    if not user:
        try:
            first_name = event.from_user.first_name if event.from_user else None
            username = event.from_user.username if event.from_user else None
            user = await user_repo.create(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name
            )
            await session.flush()
            logger.info(f"✅ Создан пользователь {telegram_id} при запросе")
        except Exception as e:
            logger.error(f"❌ Ошибка создания пользователя: {e}")
            return None
    
    return user


async def get_or_create_user_and_pet(event: Message | CallbackQuery, session: AsyncSession):
    """Получить или создать пользователя и питомца"""
    user = await get_user_from_event(event, session)
    if not user:
        return None, None
    
    pet_repo = PetRepository(session)
    pet = await pet_repo.get_by_user_id(user.id)
    
    return user, pet


async def give_starting_items(session: AsyncSession, user_id: int, pet_id: int) -> None:
    inventory_repo = InventoryRepository(session)
    starting_foods = [
        {"id": "bread", "quantity": 2},
        {"id": "cookie", "quantity": 2},
        {"id": "pizza", "quantity": 1}
    ]
    for food_data in starting_foods:
        await inventory_repo.add_item(user_id, food_data["id"], food_data["quantity"])
    
    house_service = HouseService(session)
    try:
        await house_service.buy_furniture(pet_id, "sofa", "living_room")
    except Exception as e:
        logger.error(f"Ошибка добавления мебели в онбординге: {e}")
    try:
        await house_service.buy_furniture(pet_id, "lamp", "bedroom")
    except Exception as e:
        logger.error(f"Ошибка добавления мебели в онбординге: {e}")


async def complete_onboarding(session: AsyncSession, user_id: int, pet_id: int, event: Message | CallbackQuery) -> None:
    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(user_id)
    if user:
        user.onboarding_step = 7
        await session.commit()
    
    await give_starting_items(session, user_id, pet_id)
    
    pet_repo = PetRepository(session)
    pet = await pet_repo.get_by_id(pet_id)
    pet_name = pet.name if pet else "питомец"
    
    if pet:
        pet.happiness = min(100, pet.happiness + 10)
        await session.commit()
    
    keyboard = get_main_menu_keyboard_sync()
    text = (
        f"🎉 <b>Онбординг завершён!</b>\n\n"
        f"Теперь {pet_name} полностью готов к большим приключениям! 🚀\n\n"
        f"Ты получил стартовый набор:\n"
        f"💰 500 монет\n"
        f"🍞 2 хлеба\n"
        f"🍪 2 печенья\n"
        f"🍕 1 пицца\n"
        f"🛋️ 1 диван\n"
        f"💡 1 лампа\n"
        f"😊 +10 к счастью\n\n"
        f"Удачи, и помни — чем больше еды, тем лучше жизнь! 🍽️"
    )
    
    if isinstance(event, Message):
        await event.answer(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await event.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


async def start_onboarding(event: Message | CallbackQuery, session: AsyncSession, user_id: int, pet_id: int) -> None:
    pet_repo = PetRepository(session)
    pet = await pet_repo.get_by_id(pet_id)
    if not pet:
        if isinstance(event, Message):
            await event.answer("❌ Ошибка: питомец не найден.")
        else:
            await event.answer("❌ Ошибка: питомец не найден.", show_alert=True)
        return
    
    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(user_id)
    if user:
        user.onboarding_step = 1
        await session.commit()
    
    keyboard = get_onboarding_adventure_keyboard()
    text = (
        f"🎯 <b>Шаг 1 из 6: Первое приключение</b>\n\n"
        f"Отлично! {pet.name} уже не может сидеть на месте.\n\n"
        f"Давай отправим его в первое приключение? 🌳\n\n"
        f"<i>Приключение займёт 20-25 секунд и принесёт гарантированные награды.</i>"
    )
    
    if isinstance(event, Message):
        await event.answer(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await event.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


# ============================================================
# ШАГ 1: ПРИКЛЮЧЕНИЕ
# ============================================================

@router.callback_query(F.data == "onboarding_adventure")
async def handle_onboarding_adventure(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    user, pet = await get_or_create_user_and_pet(callback, session)
    if not user or not pet:
        await callback.answer("❌ Пользователь или питомец не найден", show_alert=True)
        return
    
    pet.energy = max(0, pet.energy - 10)
    await session.flush()
    
    await callback.message.edit_text(
        f"⏳ <b>{pet.name} отправился в приключение!</b>\n\n🌳 Исследует Парк...\nПодожди немного... ⏱️",
        parse_mode="HTML",
        reply_markup=None
    )
    await callback.answer()
    
    wait_time = random.randint(20, 25)
    await asyncio.sleep(wait_time)
    
    level_service = LevelService(session)
    achievement_service = AchievementService(session)
    adventure_service = AdventureService(session, level_service, achievement_service)
    
    # ===== ИСПРАВЛЕНО: передаём telegram_id, а не user.id =====
    result = await adventure_service.start_adventure(
        user_id=user.telegram_id,
        pet_id=pet.id,
        location_id="park"
    )
    
    if result["success"]:
        adventure_id = result["adventure_id"]
        await adventure_service.complete_adventure(adventure_id)
    
    await session.refresh(pet)
    
    foods = data_loader.get("foods", {})
    food_names = list(foods.keys())
    common_foods = [f for f in food_names if foods.get(f, {}).get("rarity") == "common"]
    uncommon_foods = [f for f in food_names if foods.get(f, {}).get("rarity") == "uncommon"]
    random_common = random.choice(common_foods) if common_foods else "bread"
    random_uncommon = random.choice(uncommon_foods) if uncommon_foods else "cookie"
    
    inventory_repo = InventoryRepository(session)
    await inventory_repo.add_item(user.id, random_common, 1)
    await inventory_repo.add_item(user.id, random_uncommon, 1)
    
    user.coins += 50
    pet.experience += 20
    await session.flush()
    
    await level_service.add_experience(pet, 20)
    await session.refresh(user)
    await session.refresh(pet)
    
    user.onboarding_step = 2
    await session.commit()
    await state.set_state(OnboardingStates.step_2_feed)
    
    food_data = get_food_by_id(random_common)
    food_name = food_data.get("name", random_common) if food_data else random_common
    food_emoji = food_data.get("emoji", "🍽️") if food_data else "🍽️"
    
    keyboard = get_onboarding_feed_keyboard(random_common, food_name)
    await callback.message.edit_text(
        f"🎉 <b>Приключение завершено!</b>\n\n{pet.name} вернулся с трофеями!\n\n"
        f"📦 Награды:\n🍽️ {food_emoji} {food_name} x1\n💰 50 монет\n⭐ 20 XP\n\n"
        f"🍕 <b>Шаг 2 из 6: Первое кормление</b>\n\n{pet.name} проголодался после приключения!\nДавай покормим его?",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# ============================================================
# ШАГ 2: КОРМЛЕНИЕ
# ============================================================

@router.callback_query(F.data.startswith("onboarding_feed_"))
async def handle_onboarding_feed(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    user, pet = await get_or_create_user_and_pet(callback, session)
    if not user or not pet:
        await callback.answer("❌ Пользователь или питомец не найден", show_alert=True)
        return
    
    food_id = extract_food_id(callback.data)
    
    inventory_repo = InventoryRepository(session)
    item = await inventory_repo.get_item(user.id, food_id)
    if not item or item.quantity <= 0:
        await callback.answer("❌ Нет такой еды в инвентаре")
        return
    
    food_data = get_food_by_id(food_id)
    if not food_data:
        await callback.answer("❌ Еда не найдена")
        return
    
    level_service = LevelService(session)
    achievement_service = AchievementService(session)
    food_service = FoodService(session, level_service, achievement_service)
    
    # ===== ИСПРАВЛЕНО: передаём telegram_id, а не user.id =====
    result = await food_service.eat_food(
        user_id=user.telegram_id,
        pet_id=pet.id,
        food_id=food_id
    )
    
    if not result["success"]:
        await callback.answer(f"❌ {result.get('message', 'Ошибка кормления')}")
        return
    
    user.onboarding_step = 3
    await session.commit()
    await state.set_state(OnboardingStates.step_3_profile)
    
    hunger_percent = pet.get_hunger_percent()
    hunger_emoji = "😊"
    if hunger_percent >= 150:
        hunger_emoji = "💀"
    elif hunger_percent >= 120:
        hunger_emoji = "🤢"
    elif hunger_percent >= 100:
        hunger_emoji = "😋"
    
    keyboard = get_onboarding_profile_keyboard()
    await callback.message.edit_text(
        f"🍽️ <b>Шаг 2 завершён!</b>\n\n{pet.name} съел {food_data.get('emoji', '')} {food_data.get('name', food_id)}!\n\n"
        f"Текущая сытость: {hunger_emoji} {hunger_percent:.0f}%\n\n"
        f"📊 <b>Шаг 3 из 6: Профиль и характеристики</b>\n\nТеперь посмотрим, как выглядит {pet.name} целиком.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "onboarding_inventory")
async def handle_onboarding_inventory(callback: CallbackQuery, session: AsyncSession) -> None:
    user, pet = await get_or_create_user_and_pet(callback, session)
    if not user or not pet:
        await callback.answer("❌ Пользователь или питомец не найден", show_alert=True)
        return
    
    inventory_repo = InventoryRepository(session)
    items = await inventory_repo.get_all_items(user.id)
    
    if not items:
        await callback.answer("📭 Инвентарь пуст")
        return
    
    text = f"🎒 <b>Инвентарь {pet.name}</b>\n\n"
    for item in items:
        food_data = get_food_by_id(item.item_id)
        if food_data:
            text += f"{food_data.get('emoji', '')} {food_data.get('name', item.item_id)} x{item.quantity}\n"
        else:
            text += f"{item.item_id} x{item.quantity}\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="onboarding_back_to_feed")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "onboarding_back_to_feed")
async def handle_onboarding_back_to_feed(callback: CallbackQuery, session: AsyncSession) -> None:
    user, pet = await get_or_create_user_and_pet(callback, session)
    if not user or not pet:
        await callback.answer("❌ Пользователь или питомец не найден", show_alert=True)
        return
    
    inventory_repo = InventoryRepository(session)
    items = await inventory_repo.get_all_items(user.id)
    foods = {item.item_id: item.quantity for item in items if item.quantity > 0}
    
    food_id = next(iter(foods.keys())) if foods else None
    if not food_id:
        await callback.message.edit_text("❌ У тебя нет еды в инвентаре!\n\nПопробуй сначала пройти приключение.", reply_markup=None)
        await callback.answer()
        return
    
    food_data = get_food_by_id(food_id)
    food_name = food_data.get("name", food_id) if food_data else food_id
    keyboard = get_onboarding_feed_keyboard(food_id, food_name)
    await callback.message.edit_text(
        f"🍕 <b>Шаг 2 из 6: Первое кормление</b>\n\n{pet.name} проголодался после приключения!\nДавай покормим его!",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


# ============================================================
# ШАГ 3-6: НАВИГАЦИЯ
# ============================================================

@router.callback_query(F.data == "onboarding_next")
async def handle_onboarding_next(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    user, pet = await get_or_create_user_and_pet(callback, session)
    if not user or not pet:
        await callback.answer("❌ Пользователь или питомец не найден", show_alert=True)
        return
    
    current_step = user.onboarding_step
    
    if current_step == 3:
        user.onboarding_step = 4
        await session.commit()
        await state.set_state(OnboardingStates.step_4_social)
        keyboard = get_onboarding_social_keyboard()
        await callback.message.edit_text(
            f"👥 <b>Шаг 4 из 6: Социальный момент</b>\n\nКстати, твоего питомца уже можно показать друзьям!\n\n"
            f"Вот его ссылка:\n<code>https://t.me/твойбот?start=pet_{pet.game_id}</code>\n\nПоделись с друзьями и получай лайки! ❤️",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    elif current_step == 4:
        user.onboarding_step = 5
        await session.commit()
        await state.set_state(OnboardingStates.step_5_house)
        keyboard = get_onboarding_house_keyboard()
        await callback.message.edit_text(
            f"🏠 <b>Шаг 5 из 6: Дом</b>\n\nУ {pet.name} уже есть свой домик!\nПока он скромный, но его можно улучшать.\n\n"
            f"Ты получил 2 предмета мебели: диван и лампу.\nМожешь поставить их в доме!",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    elif current_step == 5:
        user.onboarding_step = 6
        await session.commit()
        await state.set_state(OnboardingStates.step_6_final)
        keyboard = get_onboarding_final_keyboard()
        await callback.message.edit_text(
            f"🎯 <b>Шаг 6 из 6: Ежедневные механики + Финал</b>\n\nПоследнее важное:\n\nКаждый день тебя ждут:\n"
            f"• 🎁 Ежедневная награда\n• 📋 Новые задания\n• ⚡ Восстановление энергии и сытости\n\nГотов начать свой путь?",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        await complete_onboarding(session, user.id, pet.id, callback)
    await callback.answer()


@router.callback_query(F.data == "onboarding_share")
async def handle_onboarding_share(callback: CallbackQuery, session: AsyncSession) -> None:
    user, pet = await get_or_create_user_and_pet(callback, session)
    if not user or not pet:
        await callback.answer("❌ Пользователь или питомец не найден", show_alert=True)
        return
    
    bot_username = (await callback.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start=pet_{pet.game_id}"
    
    await callback.answer("📤 Ссылка скопирована! Поделись с друзьями!")
    await callback.message.edit_text(
        f"📤 <b>Ссылка на {pet.name}</b>\n\n<code>{link}</code>\n\n"
        f"❤️ Ты получил +1 лайк за то, что поделился!\n\n<i>Нажми «Продолжить», чтобы перейти к следующему шагу.</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➡️ Продолжить", callback_data="onboarding_next")]
        ]),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "onboarding_random_pet")
async def handle_onboarding_random_pet(callback: CallbackQuery, session: AsyncSession) -> None:
    user, pet = await get_or_create_user_and_pet(callback, session)
    if not user or not pet:
        await callback.answer("❌ Пользователь или питомец не найден", show_alert=True)
        return
    
    pet_repo = PetRepository(session)
    all_pets = await pet_repo.get_all()
    other_pets = [p for p in all_pets if p.id != pet.id]
    
    if not other_pets:
        await callback.answer("😅 Пока нет других питомцев")
        return
    
    random_pet = random.choice(other_pets)
    character = data_loader.get("characters", {}).get(random_pet.character_id, {})
    hunger_percent = random_pet.get_hunger_percent()
    
    text = f"🐾 <b>Случайный питомец</b>\n\nИмя: {random_pet.name}\n"
    text += f"Характер: {character.get('emoji', '')} {character.get('name', 'Неизвестно')}\n"
    text += f"Уровень: {random_pet.level}\nСытость: {hunger_percent:.0f}%\n"
    text += f"❤️ Лайков: {random_pet.total_likes}\n🆔 ID: <code>{random_pet.game_id}</code>\n\n<i>Можешь поставить лайк этому питомцу!</i>"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❤️ Поставить лайк", callback_data=f"like_{random_pet.id}")],
        [InlineKeyboardButton(text="🔄 Другого", callback_data="onboarding_random_pet")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="onboarding_next")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "onboarding_place_furniture")
async def handle_onboarding_place_furniture(callback: CallbackQuery, session: AsyncSession) -> None:
    user, pet = await get_or_create_user_and_pet(callback, session)
    if not user or not pet:
        await callback.answer("❌ Пользователь или питомец не найден", show_alert=True)
        return
    
    house_service = HouseService(session)
    
    try:
        await house_service.buy_furniture(pet.id, "sofa", "living_room")
        await house_service.buy_furniture(pet.id, "lamp", "bedroom")
        await callback.answer("✅ Мебель установлена в доме!")
    except Exception as e:
        logger.error(f"Ошибка установки мебели: {e}")
        await callback.answer("❌ Не удалось установить мебель")
        return
    
    await callback.message.edit_text(
        f"🛋️ <b>Мебель установлена!</b>\n\n🛋️ Диван теперь в гостиной\n💡 Лампа теперь в спальне\n\nТы можешь продолжать обустраивать дом позже.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➡️ Продолжить", callback_data="onboarding_next")]
        ]),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "onboarding_daily_reward")
async def handle_onboarding_daily_reward(callback: CallbackQuery, session: AsyncSession) -> None:
    user, pet = await get_or_create_user_and_pet(callback, session)
    if not user or not pet:
        await callback.answer("❌ Пользователь или питомец не найден", show_alert=True)
        return
    
    daily_service = DailyService(session)
    
    # ===== ИСПРАВЛЕНО: передаём telegram_id, а не user.id =====
    result = await daily_service.claim_daily_reward(user.telegram_id)
    
    if not result["success"]:
        await callback.answer(f"❌ {result.get('message', 'Не удалось получить награду')}")
        return
    
    await callback.message.edit_text(
        f"🎁 <b>Ежедневная награда получена!</b>\n\nТы получил:\n💰 +{result.get('coins', 50)} монет\n⭐ +{result.get('xp', 10)} XP\n\nЗавтра снова заходи за наградой! 🗓️",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➡️ Продолжить", callback_data="onboarding_next")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "onboarding_quests")
async def handle_onboarding_quests(callback: CallbackQuery, session: AsyncSession) -> None:
    user, pet = await get_or_create_user_and_pet(callback, session)
    if not user or not pet:
        await callback.answer("❌ Пользователь или питомец не найден", show_alert=True)
        return
    
    quest_service = QuestService(session)
    
    # ===== ИСПРАВЛЕНО: передаём telegram_id, а не user.id =====
    quests = await quest_service.get_daily_quests(user.telegram_id)
    
    if not quests:
        await callback.message.edit_text(
            f"📋 <b>Нет активных заданий</b>\n\nНовые задания появятся позже. Продолжай приключения! 🚀",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➡️ Продолжить", callback_data="onboarding_next")]
            ]),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    text = f"📋 <b>Активные задания</b>\n\n"
    for quest in quests:
        progress = f"{quest.get('progress', 0)}/{quest.get('data', {}).get('condition_value', 1)}"
        emoji = "✅" if quest.get('completed', False) else "⬜"
        text += f"{emoji} {quest.get('data', {}).get('name', 'Задание')}: {progress}\n"
    
    text += "\n<i>Выполняй задания и получай награды!</i>"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Продолжить", callback_data="onboarding_next")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "onboarding_finish")
async def handle_onboarding_finish(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    user, pet = await get_or_create_user_and_pet(callback, session)
    if not user or not pet:
        await callback.answer("❌ Пользователь или питомец не найден", show_alert=True)
        return
    
    await state.clear()
    await complete_onboarding(session, user.id, pet.id, callback)
    await callback.answer("🎉 Онбординг завершён!")


@router.callback_query(F.data == "skip_onboarding")
async def handle_skip_onboarding(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    keyboard = get_skip_onboarding_keyboard()
    await callback.message.edit_text(
        "⚠️ <b>Ты уверен, что хочешь пропустить обучение?</b>\n\nТы пропустишь полезную информацию, но сможешь начать играть сразу.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "confirm_skip_onboarding")
async def handle_confirm_skip_onboarding(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    user, pet = await get_or_create_user_and_pet(callback, session)
    if not user or not pet:
        await callback.answer("❌ Пользователь или питомец не найден", show_alert=True)
        return
    
    await state.clear()
    await complete_onboarding(session, user.id, pet.id, callback)
    await callback.answer("✅ Обучение пропущено")


@router.callback_query(F.data == "cancel_skip_onboarding")
async def handle_cancel_skip_onboarding(callback: CallbackQuery, session: AsyncSession) -> None:
    user, pet = await get_or_create_user_and_pet(callback, session)
    if not user or not pet:
        await callback.answer("❌ Пользователь или питомец не найден", show_alert=True)
        return
    
    current_step = user.onboarding_step
    
    if current_step == 1:
        keyboard = get_onboarding_adventure_keyboard()
        await callback.message.edit_text(
            f"🎯 <b>Шаг 1 из 6: Первое приключение</b>\n\nОтлично! {pet.name} уже не может сидеть на месте.\n\nДавай отправим его в первое приключение? 🌳",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    elif current_step == 2:
        inventory_repo = InventoryRepository(session)
        items = await inventory_repo.get_all_items(user.id)
        foods = {item.item_id: item.quantity for item in items if item.quantity > 0}
        food_id = next(iter(foods.keys())) if foods else None
        
        if not food_id:
            await callback.message.edit_text("❌ Нет еды в инвентаре", reply_markup=None)
            await callback.answer()
            return
        
        food_data = get_food_by_id(food_id)
        food_name = food_data.get("name", food_id) if food_data else food_id
        keyboard = get_onboarding_feed_keyboard(food_id, food_name)
        await callback.message.edit_text(
            f"🍕 <b>Шаг 2 из 6: Первое кормление</b>\n\n{pet.name} проголодался после приключения!\nДавай покормим его?",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text("Продолжайте обучение", reply_markup=None)
    await callback.answer()