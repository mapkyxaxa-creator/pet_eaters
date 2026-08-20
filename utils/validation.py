import re
from typing import Tuple

# Импортируем фильтр мата
from utils.profanity_filter import contains_profanity, filter_profanity


def validate_pet_name(name: str) -> Tuple[bool, str]:
    """
    Валидация имени питомца
    
    Returns:
        (is_valid, error_message)
    """
    if not name or len(name.strip()) == 0:
        return False, "Имя не может быть пустым"
    
    name = name.strip()
    
    if len(name) < 2:
        return False, "Имя должно содержать минимум 2 символа"
    
    if len(name) > 20:
        return False, "Имя не должно превышать 20 символов"
    
    # Разрешены: буквы, цифры, пробелы, дефис, апостроф
    if not re.match(r'^[a-zA-Zа-яА-ЯёЁ0-9\s\-\']+$', name):
        return False, "Имя может содержать только буквы, цифры и пробелы"
    
    # ===== ПРОВЕРКА НА МАТ =====
    if contains_profanity(name):
        filtered = filter_profanity(name)
        return False, f"⚠️ Имя содержит недопустимые слова. Предлагаем вариант: {filtered}"
    
    return True, ""


def validate_energy(energy: int) -> bool:
    """Проверка энергии на валидность"""
    return 0 <= energy <= 100


def validate_hunger(hunger: int, max_hunger: int) -> bool:
    """Проверка сытости на валидность"""
    return 0 <= hunger <= max_hunger