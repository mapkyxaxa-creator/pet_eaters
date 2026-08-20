from database.models import Pet
from services.data_loader import data_loader
from typing import Optional


def format_pet_profile(
    pet: Pet,
    character_data: dict,
    level_service=None,
    coins: int = 0,
    premium_balance: int = 0,
    user_first_name: Optional[str] = None
) -> str:
    """Форматирование профиля питомца"""
    hunger_percent = pet.get_hunger_percent()
    hunger_emoji = get_hunger_emoji(hunger_percent)
    
    # Расчёт XP для следующего уровня
    if level_service:
        xp_for_next = level_service.get_xp_for_level(pet.level)
    else:
        balance = data_loader.get_balance()
        xp_base = balance.get("xp_base", 100)
        xp_per_level = balance.get("xp_per_level", 50)
        xp_for_next = xp_base + (pet.level - 1) * xp_per_level
    
    xp_progress = int((pet.experience / xp_for_next) * 100) if xp_for_next > 0 else 0
    
    lines = [
        f"🐾 <b>{pet.name}</b>",
        f"{character_data.get('emoji', '')} <b>Характер:</b> {character_data.get('name', 'Неизвестно')}",
        "",
        f"💰 <b>Монет:</b> {coins} 🪙",
        f"🐾 <b>Лапок:</b> {premium_balance}",
        f"📊 <b>Уровень:</b> {pet.level} ({pet.experience}/{xp_for_next} XP, {xp_progress}%)",
        f"❤️ <b>Счастье:</b> {pet.happiness}/100",
        f"⚡ <b>Энергия:</b> {pet.energy}/100",
        f"{hunger_emoji} <b>Сытость:</b> {pet.hunger}/{pet.stomach_capacity} ({hunger_percent:.0f}%)",
        "",
        f"🍀 <b>Удача:</b> {pet.luck*100:.1f}%",
        f"👃 <b>Нюх:</b> {pet.smell}",
        f"🍽️ <b>Скорость еды:</b> {pet.eating_speed}",
        "",
        f"🆔 <b>ID питомца:</b> <code>{pet.game_id}</code>",
    ]
    
    if user_first_name:
        lines.append(f"👤 <b>Владелец:</b> {user_first_name}")
    
    # Титул
    titles_data = data_loader.get("titles", {})
    current_title = titles_data.get(pet.title_id, {})
    title_text = f"{current_title.get('emoji', '')} {current_title.get('name', 'Нет титула')}" if pet.title_id else "🐣 Новичок"
    lines.append(f"👑 <b>Титул:</b> {title_text}")
    lines.append("")
    
    # Статистика
    lines.extend([
        f"📊 <b>Статистика:</b>",
        f"🍽️ Съедено: {pet.total_eaten}",
        f"🗺️ Приключений: {pet.total_adventures}",
        f"🏆 Побед: {pet.competition_wins}",
        f"❤️ Лайков: {pet.total_likes}",
    ])
    
    # Косметика
    if pet.cosmetic_id:
        cosmetics_data = data_loader.get("cosmetics", {}).get("cosmetics", [])
        for c in cosmetics_data:
            if c.get("id") == pet.cosmetic_id:
                lines.append(f"🎨 Косметика: {c.get('emoji')} {c.get('name')}")
                break
    
    if pet.frame_id:
        frames_data = data_loader.get("frames", {}).get("frames", [])
        for f in frames_data:
            if f.get("id") == pet.frame_id:
                lines.append(f"🖼️ Рамка: {f.get('emoji')} {f.get('name')}")
                break
    
    return "\n".join(lines)


def get_hunger_emoji(hunger_percent: float) -> str:
    """Получение эмодзи в зависимости от сытости"""
    if hunger_percent <= 0:
        return "💀"
    elif hunger_percent < 30:
        return "😫"
    elif hunger_percent < 60:
        return "😐"
    elif hunger_percent < 100:
        return "😊"
    elif hunger_percent <= 120:
        return "😋"
    elif hunger_percent <= 150:
        return "🤢"
    else:
        return "💀"


def format_adventure_result(adventure, location_id: str) -> str:
    """
    Форматирование результата приключения
    
    Args:
        adventure: Объект AdventureHistory из БД
        location_id: ID локации
    
    Returns:
        str: Отформатированный текст результата
    """
    locations = data_loader.get("locations", {})
    location = locations.get(location_id, {})
    location_emoji = location.get("emoji", "🗺️")
    location_name = location.get("name", "Неизвестная локация")
    
    lines = [
        f"{location_emoji} <b>Приключение завершено!</b>",
        f"📍 {location_name}",
        ""
    ]
    
    # Получаем данные из adventure
    xp = getattr(adventure, 'xp_gained', 0) or 0
    coins = getattr(adventure, 'coins_gained', 0) or 0
    item_id = getattr(adventure, 'reward_item_id', None)
    item_amount = getattr(adventure, 'reward_amount', 0) or 0
    event_text = getattr(adventure, 'event_text', '') or ''
    
    if xp > 0:
        lines.append(f"⭐ Опыт: +{xp}")
    
    if coins > 0:
        lines.append(f"🪙 Монеты: +{coins}")
    elif coins < 0:
        lines.append(f"💔 Монеты: {coins}")
    
    if item_id and item_amount > 0:
        foods = data_loader.get("foods", {})
        food = foods.get(item_id, {})
        if food:
            food_name = food.get("name", item_id)
            food_emoji = food.get("emoji", "🍖")
            lines.append(f"{food_emoji} Найдено: {food_name} x{item_amount}")
        else:
            lines.append(f"🎁 Найдено: {item_id} x{item_amount}")
    
    if event_text:
        lines.append("")
        lines.append(f"✨ {event_text}")
    
    if len(lines) <= 2:
        lines.append("🎉 Приключение успешно завершено!")
    
    return "\n".join(lines)


def format_progress_bar(current: int, total: int, width: int = 10) -> str:
    """Форматирование полосы прогресса"""
    if total <= 0:
        return "░" * width
    
    percent = min(current / total, 1.0)
    filled = int(percent * width)
    empty = width - filled
    
    bar = "█" * filled + "░" * empty
    return bar