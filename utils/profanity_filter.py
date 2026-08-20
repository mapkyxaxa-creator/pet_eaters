"""
Фильтр нецензурной лексики
"""
import re

# Список запрещённых слов (можно расширять)
BAD_WORDS = [
    "мат", "хуй", "пизда", "бля", "ёб", "еба", "сука", "мудак",
    "хуесос", "говно", "дрист", "срака", "залупа", "петух",
    "шлюха", "блядь", "еблан", "пидор", "гандон", "манда",
    "хер", "ебать", "ебаться", "заебал", "заеба", "пиздец",
    "пиздить", "срать", "пердеть", "жопа", "жопка", "очко",
    "какашка", "какаха", "гавно", "мудила", "мудень",
    "хуила", "хуило", "ебак", "ебальник", "ебеня",
    "пиздабол", "срач", "срака", "гандон", "пидор"
]


def contains_profanity(text: str) -> bool:
    """
    Проверить, содержит ли текст запрещённые слова
    
    Args:
        text: Текст для проверки
    
    Returns:
        bool: True если есть мат, False если чисто
    """
    if not text:
        return False
    text_lower = text.lower()
    for word in BAD_WORDS:
        if word in text_lower:
            return True
    return False


def filter_profanity(text: str, replacement: str = "***") -> str:
    """
    Заменить запрещённые слова на звёздочки
    
    Args:
        text: Текст для обработки
        replacement: Символы для замены
    
    Returns:
        str: Очищенный текст
    """
    if not text:
        return text
    result = text
    for word in BAD_WORDS:
        result = re.sub(word, replacement, result, flags=re.IGNORECASE)
    return result


def validate_text(text: str, field_name: str = "Текст") -> tuple:
    """
    Проверить текст на наличие мата
    
    Args:
        text: Текст для проверки
        field_name: Название поля для сообщения об ошибке
    
    Returns:
        tuple: (is_valid, error_message, filtered_text)
    """
    if not text:
        return False, f"{field_name} не может быть пустым", text
    
    if contains_profanity(text):
        filtered = filter_profanity(text)
        return False, f"⚠️ {field_name} содержит недопустимые слова. Используйте другие слова.", filtered
    
    return True, "", text
