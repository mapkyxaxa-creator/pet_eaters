"""Сервис для работы с общим чатом питомцев"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from database.repositories.chat_repository import ChatRepository
from database.models import Pet


# Список редких достижений, которые попадают в чат
RARE_ACHIEVEMENTS = [
    "eater_1000",        # Едок 1000
    "eater_10000",       # Едок 10000
    "level_25",          # Уровень 25
    "level_50",          # Уровень 50
    "collector_30",      # Коллекционер 30
    "collector_50",      # Мастер коллекций
    "competition_win_10",  # Чемпион
    "competition_win_50",  # Легенда
    "lucky",             # Счастливчик
    "legendary_glutton", # Легендарный обжора
    "legendary_pet",     # Легендарный питомец
    "overeat_king",      # Король переедания
    "adventurer_100",    # Первооткрыватель
    "competition_win_1", # Первая победа
    "collector_10",      # Коллекционер 10
    "level_10",          # Уровень 10
    "adventurer_50",     # Исследователь
]


class ChatService:
    """Сервис для управления чатом питомцев"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = ChatRepository(session)
    
    @staticmethod
    def should_add_to_chat(event_type: str, data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Проверить, должно ли событие попасть в чат
        
        Args:
            event_type: Тип события
            data: Дополнительные данные
        
        Returns:
            bool: True если событие должно быть в чате
        """
        # Всегда добавляем основные события
        if event_type in [
            'legendary_found',
            'epic_found',
            'level_up',
            'title_earned',
            'cosmetic_bought',
            'likes_milestone',
            'gift_received',
            'competition_win',        # <-- ДОБАВЛЕНО
            'house_upgrade',          # <-- ДОБАВЛЕНО
            'story_chapter_completed' # <-- ДОБАВЛЕНО
        ]:
            return True
        
        # Достижения - только редкие
        if event_type == 'achievement_earned':
            if data and 'achievement_id' in data:
                return data['achievement_id'] in RARE_ACHIEVEMENTS
            return False
        
        return False
    
    async def add_event(
        self,
        pet: Pet,
        event_type: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Добавить событие в чат (с фильтрацией)
        
        Args:
            pet: Объект питомца
            event_type: Тип события
            message: Текст сообщения
            data: Дополнительные данные
        
        Returns:
            Optional[Dict]: Созданное сообщение или None если не прошло фильтр
        """
        # Проверяем фильтр
        if not self.should_add_to_chat(event_type, data):
            return None
        
        # Добавляем сообщение
        chat_message = await self.repository.add_message(
            pet_id=pet.id,
            event_type=event_type,
            message=message,
            data=data
        )
        
        return {
            'id': chat_message.id,
            'pet_id': chat_message.pet_id,
            'pet_name': pet.name,
            'pet_photo': pet.photo_file_id,
            'pet_character_id': pet.character_id,
            'pet_level': pet.level,
            'event_type': chat_message.event_type,
            'message': chat_message.message,
            'data': data,
            'created_at': chat_message.created_at
        }
    
    async def get_chat(self, limit: int = 30) -> List[Dict[str, Any]]:
        """
        Получить последние сообщения чата
        
        Args:
            limit: Максимальное количество сообщений
        
        Returns:
            List[Dict]: Список сообщений
        """
        return await self.repository.get_recent(limit)
    
    async def get_pet_chat(self, pet_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Получить сообщения конкретного питомца
        
        Args:
            pet_id: ID питомца
            limit: Максимальное количество сообщений
        
        Returns:
            List[Dict]: Список сообщений
        """
        return await self.repository.get_by_pet(pet_id, limit)
    
    async def format_chat_message(self, msg: Dict[str, Any]) -> str:
        """
        Отформатировать сообщение для отображения
        
        Args:
            msg: Словарь с данными сообщения
        
        Returns:
            str: Отформатированное сообщение
        """
        # Получаем эмодзи персонажа
        emoji_map = {
            'dog': '🐶',
            'cat': '🐱',
            'fox': '🦊',
            'wolf': '🐺',
            'rabbit': '🐰',
            'bear': '🐻',
            'panda': '🐼',
            'lion': '🦁',
            'tiger': '🐯',
            'dragon': '🐉',
            'unicorn': '🦄',
            'bird': '🐦',
            'penguin': '🐧',
            'owl': '🦉',
            'elephant': '🐘',
            'monkey': '🐒',
            'koala': '🐨',
            'sloth': '🦥',
            'raccoon': '🦝',
            'skunk': '🦨',
        }
        
        character_id = msg.get('pet_character_id', '')
        emoji = emoji_map.get(character_id, '🐾')
        
        pet_name = msg.get('pet_name', 'Питомец')
        pet_level = msg.get('pet_level', 1)
        message_text = msg.get('message', '')
        
        # Форматируем время
        created_at = msg.get('created_at')
        if created_at:
            time_str = created_at.strftime('%H:%M')
            date_str = created_at.strftime('%d.%m.%Y')
            
            now = datetime.utcnow()
            if created_at.date() == now.date():
                date_display = 'Сегодня'
            elif created_at.date() == (now - timedelta(days=1)).date():
                date_display = 'Вчера'
            else:
                date_display = date_str
            
            time_display = f'{date_display}, {time_str}'
        else:
            time_display = ''
        
        return f"{emoji} {pet_name} (⭐ Ур.{pet_level}): «{message_text}»"