import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from services.house_service import HouseService
from services.data_loader import data_loader
from utils.user_utils import ensure_user, ensure_pet
from utils.message_utils import send_or_edit, delete_message
from keyboards.house import (
    get_house_main_keyboard,
    get_house_rooms_keyboard,
    get_house_room_keyboard,
    get_house_furniture_keyboard,
    get_house_furniture_detail_keyboard,
    get_house_buy_furniture_keyboard,
    get_house_templates_keyboard,
    get_house_visit_keyboard,
    get_house_upgrade_keyboard
)
from keyboards.main_menu import get_main_menu_keyboard_sync

logger = logging.getLogger(__name__)
router = Router()


# === КОМАНДА /house ===

@router.message(Command("house"))
async def cmd_house(message: Message, session: AsyncSession) -> None:
    """Команда /house — открыть дом"""
    user = await ensure_user(message, session)
    if not user:
        return
    
    pet = await ensure_pet(message, session, user)
    if not pet:
        return
    
    house_service = HouseService(session)
    result = await house_service.get_house_info(pet.id)
    
    if not result["success"]:
        await message.answer("❌ Не удалось загрузить информацию о доме")
        return
    
    house = result["house"]
    bonuses = house.get("bonuses", {})
    
    text = f"{house.get('template_emoji', '🏠')} <b>Дом питомца {pet.name}</b>\n\n"
    text += f"📊 <b>Информация:</b>\n"
    text += f"   🏠 Шаблон: {house.get('template_name', 'Базовый')}\n"
    text += f"   ⬆️ Уровень: {house.get('level', 1)}\n"
    text += f"   🏠 Комнат: {len(house.get('rooms', []))}\n\n"
    
    text += f"✨ <b>Бонусы дома:</b>\n"
    text += f"   ⚡ Восстановление энергии: +{bonuses.get('energy_recovery_boost', 0)}%\n"
    text += f"   😊 Счастье: +{bonuses.get('happiness_boost', 0)}\n"
    text += f"   🍽️ Уменьшение голода: -{bonuses.get('hunger_reduction', 0)}%\n"
    text += f"   🍀 Удача: +{bonuses.get('luck_boost', 0)}%\n\n"
    
    text += f"📈 <b>Статистика:</b>\n"
    text += f"   👥 Всего посетителей: {house.get('total_visitors', 0)}\n"
    text += f"   🚪 Посещений за неделю: {house.get('visits_this_week', 0)}"
    
    await message.answer(
        text,
        reply_markup=get_house_main_keyboard(house.get('level', 1)),
        parse_mode="HTML"
    )


# === ГЛАВНОЕ МЕНЮ ДОМА ===

@router.callback_query(F.data == "house")
async def house_main(callback: CallbackQuery, session: AsyncSession) -> None:
    """Главное меню дома"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    house_service = HouseService(session)
    result = await house_service.get_house_info(pet.id)
    
    if not result["success"]:
        await send_or_edit(
            callback,
            text="❌ Не удалось загрузить информацию о доме",
            reply_markup=get_house_main_keyboard()
        )
        return
    
    house = result["house"]
    bonuses = house.get("bonuses", {})
    
    # Проверяем, можно ли получить бонус
    can_claim = await house_service.can_claim_daily_bonus(pet.id)
    
    text = f"{house.get('template_emoji', '🏠')} <b>Дом питомца {pet.name}</b>\n\n"
    text += f"📊 <b>Информация:</b>\n"
    text += f"   🏠 Шаблон: {house.get('template_name', 'Базовый')}\n"
    text += f"   ⬆️ Уровень: {house.get('level', 1)}\n"
    text += f"   🏠 Комнат: {len(house.get('rooms', []))}\n\n"
    
    text += f"✨ <b>Бонусы дома:</b>\n"
    text += f"   ⚡ Восстановление энергии: +{bonuses.get('energy_recovery_boost', 0)}%\n"
    text += f"   😊 Счастье: +{bonuses.get('happiness_boost', 0)}\n"
    text += f"   🍽️ Уменьшение голода: -{bonuses.get('hunger_reduction', 0)}%\n"
    text += f"   🍀 Удача: +{bonuses.get('luck_boost', 0)}%\n\n"
    
    text += f"📈 <b>Статистика:</b>\n"
    text += f"   👥 Всего посетителей: {house.get('total_visitors', 0)}\n"
    text += f"   🚪 Посещений за неделю: {house.get('visits_this_week', 0)}"
    
    await send_or_edit(
        callback,
        text=text,
        reply_markup=get_house_main_keyboard(house.get('level', 1), can_claim),
        parse_mode="HTML"
    )


# === КОМНАТЫ ===

@router.callback_query(F.data == "house_rooms")
async def house_rooms(callback: CallbackQuery, session: AsyncSession) -> None:
    """Показать комнаты дома (без замков)"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    house_service = HouseService(session)
    result = await house_service.get_house_info(pet.id)
    
    if not result["success"]:
        await callback.answer("❌ Не удалось загрузить комнаты", show_alert=True)
        return
    
    rooms = result["house"].get("rooms", [])
    
    if not rooms:
        text = "🏠 У вас пока нет комнат. Улучшите дом!"
        await send_or_edit(callback, text, reply_markup=get_house_rooms_keyboard([]))
        return
    
    text = "🏠 <b>Комнаты дома</b>\n\n"
    for room in rooms:
        text += f"{room.get('emoji', '📦')} <b>{room.get('name', room.get('type', ''))}</b>\n"
        if room.get("is_unlocked"):
            bonuses = room.get("bonuses", {})
            bonus_text = ", ".join([f"{k}: +{v}" for k, v in bonuses.items() if v > 0])
            if bonus_text:
                text += f"   ✨ {bonus_text}\n"
            furniture = room.get("furniture", [])
            if furniture:
                furn_text = ", ".join([f"{f.get('emoji', '📦')}{f.get('name', '')} x{f.get('quantity', 1)}" for f in furniture[:3]])
                text += f"   🪑 {furn_text}\n"
        else:
            text += f"   🔒 Требуется уровень {room.get('unlock_level', '?')}\n"
        text += "\n"
    
    await send_or_edit(
        callback,
        text=text,
        reply_markup=get_house_rooms_keyboard(rooms)
    )


@router.callback_query(F.data.startswith("house_room_"))
async def house_room_detail(callback: CallbackQuery, session: AsyncSession) -> None:
    """Детали комнаты"""
    room_type = callback.data.replace("house_room_", "")
    
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    house_service = HouseService(session)
    result = await house_service.get_house_info(pet.id)
    
    if not result["success"]:
        await callback.answer("❌ Не удалось загрузить информацию", show_alert=True)
        return
    
    rooms = result["house"].get("rooms", [])
    room = next((r for r in rooms if r.get("type") == room_type), None)
    
    if not room:
        await callback.answer("❌ Комната не найдена", show_alert=True)
        return
    
    if not room.get("is_unlocked"):
        await callback.answer("🔒 Комната не разблокирована", show_alert=True)
        return
    
    furniture = room.get("furniture", [])
    bonuses = room.get("bonuses", {})
    
    text = f"{room.get('emoji', '📦')} <b>{room.get('name', room_type)}</b>\n"
    text += f"📝 {room.get('description', '')}\n\n"
    
    if bonuses:
        text += f"✨ <b>Бонусы:</b>\n"
        for key, value in bonuses.items():
            text += f"   +{value} {key}\n"
        text += "\n"
    
    if furniture:
        text += f"🪑 <b>Мебель ({len(furniture)}):</b>\n"
        for f in furniture:
            text += f"   {f.get('emoji', '📦')} {f.get('name', '')} x{f.get('quantity', 1)}\n"
    else:
        text += "🪑 В комнате пока нет мебели"
    
    await send_or_edit(
        callback,
        text=text,
        reply_markup=get_house_room_keyboard(room_type, len(furniture))
    )


# === МЕБЕЛЬ ===

@router.callback_query(F.data.startswith("house_room_furniture_"))
async def house_furniture_list(callback: CallbackQuery, session: AsyncSession) -> None:
    """Список мебели в комнате"""
    room_type = callback.data.replace("house_room_furniture_", "")
    
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    house_service = HouseService(session)
    result = await house_service.get_house_info(pet.id)
    
    if not result["success"]:
        await callback.answer("❌ Не удалось загрузить информацию", show_alert=True)
        return
    
    rooms = result["house"].get("rooms", [])
    room = next((r for r in rooms if r.get("type") == room_type), None)
    
    if not room or not room.get("is_unlocked"):
        await callback.answer("❌ Комната не найдена или не разблокирована", show_alert=True)
        return
    
    furniture = room.get("furniture", [])
    
    if not furniture:
        text = f"🪑 В комнате {room.get('name', room_type)} нет мебели"
        await send_or_edit(callback, text, reply_markup=get_house_room_keyboard(room_type, 0))
        return
    
    text = f"🪑 <b>Мебель в {room.get('name', room_type)}</b>\n\n"
    for f in furniture:
        bonuses = f.get("bonuses", {})
        bonus_text = ", ".join([f"+{v} {k}" for k, v in bonuses.items() if v > 0])
        text += f"{f.get('emoji', '📦')} <b>{f.get('name', '')}</b> x{f.get('quantity', 1)}\n"
        if bonus_text:
            text += f"   ✨ {bonus_text}\n"
        text += "\n"
    
    await send_or_edit(
        callback,
        text=text,
        reply_markup=get_house_furniture_keyboard(furniture, room_type)
    )


@router.callback_query(F.data.startswith("house_furniture_detail_"))
async def house_furniture_detail(callback: CallbackQuery, session: AsyncSession) -> None:
    """Детали мебели"""
    parts = callback.data.replace("house_furniture_detail_", "").split("_")
    if len(parts) < 2:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    room_type = parts[0]
    furniture_id = "_".join(parts[1:])
    
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    house_service = HouseService(session)
    result = await house_service.get_house_info(pet.id)
    
    if not result["success"]:
        await callback.answer("❌ Не удалось загрузить информацию", show_alert=True)
        return
    
    rooms = result["house"].get("rooms", [])
    room = next((r for r in rooms if r.get("type") == room_type), None)
    
    if not room:
        await callback.answer("❌ Комната не найдена", show_alert=True)
        return
    
    furniture = next((f for f in room.get("furniture", []) if f.get("id") == furniture_id), None)
    
    if not furniture:
        await callback.answer("❌ Мебель не найдена", show_alert=True)
        return
    
    bonuses = furniture.get("bonuses", {})
    
    text = f"{furniture.get('emoji', '📦')} <b>{furniture.get('name', '')}</b>\n"
    text += f"📦 Количество: x{furniture.get('quantity', 1)}\n\n"
    
    if bonuses:
        text += f"✨ <b>Бонусы:</b>\n"
        for key, value in bonuses.items():
            text += f"   +{value} {key}\n"
    
    await send_or_edit(
        callback,
        text=text,
        reply_markup=get_house_furniture_detail_keyboard(room_type, furniture_id)
    )


@router.callback_query(F.data.startswith("house_remove_furniture_"))
async def house_remove_furniture(callback: CallbackQuery, session: AsyncSession) -> None:
    """Удалить мебель"""
    parts = callback.data.replace("house_remove_furniture_", "").split("_")
    if len(parts) < 2:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    room_type = parts[0]
    furniture_id = "_".join(parts[1:])
    
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    house_service = HouseService(session)
    result = await house_service.remove_furniture(pet.id, furniture_id, room_type)
    
    if result["success"]:
        await callback.answer("🗑️ Мебель удалена", show_alert=True)
        await house_room_detail(callback, session)
    else:
        await callback.answer(f"❌ {result.get('message', 'Ошибка')}", show_alert=True)


# === ПОКУПКА МЕБЕЛИ ===

@router.callback_query(F.data.startswith("house_buy_furniture_"))
async def house_buy_furniture_list(callback: CallbackQuery, session: AsyncSession) -> None:
    """Показать список доступной мебели для покупки"""
    logger.info(f"=== house_buy_furniture_list CALLBACK ===")
    logger.info(f"Full callback.data: {callback.data}")
    
    room_type = callback.data.replace("house_buy_furniture_", "")
    logger.info(f"✅ Extracted room_type: '{room_type}'")
    
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    house_service = HouseService(session)
    furniture_items = await house_service.get_available_furniture(room_type)
    
    if not furniture_items:
        text = f"🛒 Нет доступной мебели для комнаты {room_type}"
        await send_or_edit(callback, text, reply_markup=get_house_room_keyboard(room_type, 0))
        return
    
    text = f"🛒 <b>Доступная мебель для комнаты</b>\n\n"
    for f in furniture_items[:10]:
        price_text = ""
        if f.get("price_coins", 0) > 0:
            price_text += f"{f['price_coins']} 🪙"
        if f.get("price_premium", 0) > 0:
            if price_text:
                price_text += " "
            price_text += f"{f['price_premium']} 🐾"
        
        rarity_emoji = {"common": "⬜", "uncommon": "🟩", "rare": "🟦", "epic": "🟪", "legendary": "🟧"}.get(f.get("rarity", "common"), "⬜")
        
        text += f"{rarity_emoji} {f.get('emoji', '📦')} <b>{f.get('name', '')}</b>\n"
        text += f"   📝 {f.get('description', '')}\n"
        text += f"   💰 {price_text}\n"
        
        # Бонусы на русском
        if f.get("bonuses"):
            bonus_parts = []
            for key, value in f['bonuses'].items():
                if value > 0:
                    if key == "happiness_boost":
                        bonus_parts.append(f"+{value} к счастью")
                    elif key == "luck_boost":
                        bonus_parts.append(f"+{value} к удаче")
                    elif key == "energy_recovery_boost":
                        bonus_parts.append(f"+{value} к восстановлению энергии")
                    elif key == "hunger_reduction":
                        bonus_parts.append(f"-{value} к уменьшению голода")
                    else:
                        bonus_parts.append(f"+{value} {key}")
            if bonus_parts:
                text += f"   ✨ {', '.join(bonus_parts)}\n"
        
        text += "\n"
    
    await send_or_edit(
        callback,
        text=text,
        reply_markup=get_house_buy_furniture_keyboard(furniture_items, room_type)
    )


@router.callback_query(F.data.startswith("house_buy_"))
async def house_buy_furniture(callback: CallbackQuery, session: AsyncSession) -> None:
    """Купить мебель"""
    logger.info(f"=== house_buy_furniture CALLBACK ===")
    logger.info(f"Full callback.data: {callback.data}")
    
    # ИСПОЛЬЗУЕМ РАЗДЕЛИТЕЛЬ | ВМЕСТО _
    parts = callback.data.replace("house_buy_", "").split("|")
    logger.info(f"Parsed parts: {parts}")
    
    if len(parts) < 2:
        logger.warning(f"❌ Invalid parts length: {len(parts)}, parts: {parts}")
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    room_type = parts[0]
    furniture_id = parts[1]
    logger.info(f"✅ Extracted room_type: '{room_type}', furniture_id: '{furniture_id}'")
    
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    house_service = HouseService(session)
    
    logger.info(f"🛒 Calling buy_furniture with: pet_id={pet.id}, furniture_id='{furniture_id}', room_type='{room_type}'")
    result = await house_service.buy_furniture(pet.id, furniture_id, room_type)
    logger.info(f"📦 buy_furniture result: success={result.get('success')}, message={result.get('message')}")
    
    if result["success"]:
        await callback.answer(f"✅ {result['message']}", show_alert=True)
        await house_room_detail(callback, session)
    else:
        await callback.answer(f"❌ {result.get('message', 'Ошибка')}", show_alert=True)


# === ШАБЛОНЫ ===

@router.callback_query(F.data == "house_templates")
async def house_templates(callback: CallbackQuery, session: AsyncSession) -> None:
    """Показать доступные шаблоны дома"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    house_service = HouseService(session)
    templates = await house_service.get_available_templates(pet.id)
    
    if not templates:
        text = "🏠 У вас уже лучший шаблон дома!"
        await send_or_edit(callback, text, reply_markup=get_house_main_keyboard())
        return
    
    text = "🏠 <b>Доступные шаблоны дома</b>\n\n"
    for template in templates:
        status = "🔒" if template.get("is_locked", False) else "🆓"
        price_text = f"{template.get('cost', 0)} 🪙" if template.get('cost', 0) > 0 else "бесплатно"
        text += f"{status} {template.get('emoji', '🏠')} <b>{template.get('name', '')}</b>\n"
        text += f"   📝 {template.get('description', '')}\n"
        text += f"   💰 {price_text}\n"
        bonuses = template.get("bonuses", {})
        if bonuses:
            bonus_text = ", ".join([f"+{v} {k}" for k, v in bonuses.items() if v > 0])
            text += f"   ✨ {bonus_text}\n"
        text += "\n"
    
    await send_or_edit(
        callback,
        text=text,
        reply_markup=get_house_templates_keyboard(templates)
    )


@router.callback_query(F.data.startswith("house_template_"))
async def house_buy_template(callback: CallbackQuery, session: AsyncSession) -> None:
    """Купить шаблон дома"""
    template_id = callback.data.replace("house_template_", "")
    
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    house_service = HouseService(session)
    
    # Проверяем, доступен ли шаблон
    templates = await house_service.get_available_templates(pet.id)
    template = next((t for t in templates if t.get("id") == template_id), None)
    
    if not template:
        await callback.answer("❌ Шаблон недоступен", show_alert=True)
        return
    
    if template.get("is_locked", True):
        await callback.answer("🔒 Шаблон заблокирован", show_alert=True)
        return
    
    result = await house_service.upgrade_house_template(pet.id, template_id)
    
    if result["success"]:
        await callback.answer("✅ Шаблон обновлён!", show_alert=True)
        await house_main(callback, session)
    else:
        await callback.answer(f"❌ {result.get('message', 'Ошибка')}", show_alert=True)


# === УЛУЧШЕНИЕ ===

@router.callback_query(F.data == "house_upgrade")
async def house_upgrade(callback: CallbackQuery, session: AsyncSession) -> None:
    """Показать информацию об улучшении"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    house_service = HouseService(session)
    result = await house_service.get_house_info(pet.id)
    
    if not result["success"]:
        await callback.answer("❌ Не удалось загрузить информацию", show_alert=True)
        return
    
    house = result["house"]
    current_level = house.get("level", 1)
    max_level = house.get("max_level", 10)
    
    upgrade_costs = data_loader.get("houses", {}).get("upgrade_costs", {})
    next_cost = upgrade_costs.get(f"level_{current_level + 1}", None)
    
    text = f"⬆️ <b>Улучшение дома</b>\n\n"
    text += f"📊 Текущий уровень: {current_level}\n"
    
    if current_level < max_level:
        text += f"📊 Следующий уровень: {current_level + 1}\n"
        text += f"💰 Стоимость: {next_cost} 🪙\n\n"
        
        if next_cost:
            text += f"Улучшение даст:\n"
            text += f"   ⚡ +5% к восстановлению энергии\n"
            text += f"   😊 +2 к счастью\n"
            text += f"   🏠 Возможно, новая комната\n"
    else:
        text += "✅ Дом максимального уровня!\n"
    
    await send_or_edit(
        callback,
        text=text,
        reply_markup=get_house_upgrade_keyboard(current_level, max_level)
    )


@router.callback_query(F.data == "house_upgrade_confirm")
async def house_upgrade_confirm(callback: CallbackQuery, session: AsyncSession) -> None:
    """Подтвердить улучшение дома"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    house_service = HouseService(session)
    result = await house_service.upgrade_house(pet.id)
    
    if result["success"]:
        await callback.answer(f"✅ {result['message']}", show_alert=True)
        await house_main(callback, session)
    else:
        await callback.answer(f"❌ {result.get('message', 'Ошибка')}", show_alert=True)


# === ПОСЕЩЕНИЕ ===

@router.callback_query(F.data == "house_visit")
async def house_visit(callback: CallbackQuery, session: AsyncSession) -> None:
    """Показать дома для посещения"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    house_service = HouseService(session)
    
    # Получаем дома других игроков
    houses = await house_service.house_repo.get_all_visitable(pet.id)
    
    if not houses:
        text = "👥 Пока нет доступных домов для посещения. Попробуйте позже!"
        await send_or_edit(callback, text, reply_markup=get_house_main_keyboard())
        return
    
    available = []
    for house in houses:
        # Получаем питомца
        target_pet = await house_service.pet_repo.get_by_id(house.pet_id)
        if target_pet:
            available.append({
                "pet_id": target_pet.id,
                "pet_name": target_pet.name,
                "emoji": "🏠",
                "level": house.level,
                "house_id": house.id
            })
    
    text = "👥 <b>Доступные дома для посещения</b>\n\n"
    text += "💡 Посещайте дома других игроков,\n"
    text += "чтобы получать бонусы!\n\n"
    
    for h in available[:10]:
        text += f"{h.get('emoji', '🏠')} {h.get('pet_name', 'Питомец')} (ур. {h.get('level', 1)})\n"
    
    await send_or_edit(
        callback,
        text=text,
        reply_markup=get_house_visit_keyboard(available)
    )


@router.callback_query(F.data.startswith("house_visit_pet_"))
async def house_visit_pet(callback: CallbackQuery, session: AsyncSession) -> None:
    """Посетить дом питомца"""
    target_pet_id = int(callback.data.replace("house_visit_pet_", ""))
    
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    house_service = HouseService(session)
    result = await house_service.visit_house(pet.id, target_pet_id)
    
    if result["success"]:
        await callback.answer("✅ Дом посещён! Получены бонусы!", show_alert=True)
        await house_main(callback, session)
    else:
        await callback.answer(f"❌ {result.get('message', 'Ошибка')}", show_alert=True)


@router.callback_query(F.data == "house_visit_refresh")
async def house_visit_refresh(callback: CallbackQuery, session: AsyncSession) -> None:
    """Обновить список домов"""
    await house_visit(callback, session)


# === НАВИГАЦИЯ ===

@router.callback_query(F.data == "house_main")
async def house_main_navigation(callback: CallbackQuery, session: AsyncSession) -> None:
    """Вернуться в главное меню дома"""
    await house_main(callback, session)


@router.callback_query(F.data == "house_info")
async def house_info(callback: CallbackQuery, session: AsyncSession) -> None:
    """Показать информацию о доме"""
    await house_main(callback, session)


# === ВСЯ МЕБЕЛЬ В ДОМЕ ===

@router.callback_query(F.data == "house_furniture")
async def house_furniture_all(callback: CallbackQuery, session: AsyncSession) -> None:
    """Показать всю мебель в доме питомца"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    house_service = HouseService(session)
    result = await house_service.get_house_info(pet.id)
    
    if not result["success"]:
        await callback.answer("❌ Не удалось загрузить информацию о доме", show_alert=True)
        return
    
    house = result["house"]
    rooms = house.get("rooms", [])
    
    # Собираем всю мебель из всех комнат
    all_furniture = []
    room_names = {}
    
    for room in rooms:
        if not room.get("is_unlocked"):
            continue
        room_type = room.get("type", "")
        room_name = room.get("name", room_type)
        room_emoji = room.get("emoji", "📦")
        furniture_list = room.get("furniture", [])
        
        for f in furniture_list:
            all_furniture.append({
                "room_type": room_type,
                "room_name": room_name,
                "room_emoji": room_emoji,
                "furniture": f
            })
        room_names[room_type] = {"name": room_name, "emoji": room_emoji}
    
    if not all_furniture:
        text = f"🪑 <b>В доме {pet.name} нет мебели</b>\n\n"
        text += "💡 Купите мебель в магазине, чтобы обустроить дом!\n"
        text += "📦 Зайдите в любую комнату и нажмите «Купить мебель»"
        
        keyboard = [
            [InlineKeyboardButton(text="🔙 Назад", callback_data="house_main")]
        ]
        await send_or_edit(
            callback,
            text=text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
            parse_mode="HTML"
        )
        return
    
    text = f"🪑 <b>Вся мебель в доме {pet.name}</b>\n\n"
    
    current_room = None
    for item in all_furniture:
        room_name = item["room_name"]
        room_emoji = item["room_emoji"]
        f = item["furniture"]
        
        if current_room != room_name:
            if current_room is not None:
                text += "\n"
            text += f"{room_emoji} <b>{room_name}</b>\n"
            current_room = room_name
        
        emoji = f.get("emoji", "📦")
        name = f.get("name", "Неизвестно")
        quantity = f.get("quantity", 1)
        bonuses = f.get("bonuses", {})
        
        text += f"   {emoji} {name} x{quantity}"
        
        if bonuses:
            bonus_parts = []
            for key, value in bonuses.items():
                if value > 0:
                    if key == "energy_recovery_boost":
                        bonus_parts.append(f"⚡ +{value}%")
                    elif key == "happiness_boost":
                        bonus_parts.append(f"😊 +{value}")
                    elif key == "hunger_reduction":
                        bonus_parts.append(f"🍽️ -{value}%")
                    elif key == "luck_boost":
                        bonus_parts.append(f"🍀 +{value}%")
                    else:
                        bonus_parts.append(f"+{value} {key}")
            if bonus_parts:
                text += f" ({', '.join(bonus_parts)})"
        
        text += "\n"
    
    total_items = sum(item["furniture"].get("quantity", 1) for item in all_furniture)
    unique_items = len(all_furniture)
    text += f"\n📊 <b>Статистика:</b> {unique_items} уникальных предметов, всего {total_items} шт."
    
    keyboard = [
        [InlineKeyboardButton(text="🔙 Назад", callback_data="house_main")]
    ]
    
    await send_or_edit(
        callback,
        text=text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML"
    )