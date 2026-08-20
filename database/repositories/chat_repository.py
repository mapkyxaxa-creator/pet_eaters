"""Репозиторий для работы с сообщениями чата питомцев"""
from typing import Optional, List, Dict, Any
from datetime import datetime
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_
from database.models import ChatMessage, Pet


class ChatRepository:
    """Репозиторий для управления сообщениями в общем чате питомцев"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def add_message(
        self,
        pet_id: int,
        event_type: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> ChatMessage:
        """
        Добавить новое сообщение в чат
        
        Args:
            pet_id: ID питомца
            event_type: Тип события (legendary_found, level_up, etc.)
            message: Текст сообщения
            data: Дополнительные данные в виде словаря
        
        Returns:
            ChatMessage: Созданное сообщение
        """
        data_json = json.dumps(data, ensure_ascii=False) if data else None
        
        chat_message = ChatMessage(
            pet_id=pet_id,
            event_type=event_type,
            message=message,
            data=data_json,
            created_at=datetime.utcnow()
        )
        
        self.session.add(chat_message)
        await self.session.commit()
        await self.session.refresh(chat_message)
        
        return chat_message
    
    async def get_recent(self, limit: int = 30) -> List[Dict[str, Any]]:
        """
        Получить последние сообщения чата
        
        Args:
            limit: Максимальное количество сообщений
        
        Returns:
            List[Dict]: Список сообщений с данными о питомце
        """
        query = (
            select(ChatMessage, Pet)
            .join(Pet, ChatMessage.pet_id == Pet.id)
            .order_by(desc(ChatMessage.created_at))
            .limit(limit)
        )
        
        result = await self.session.execute(query)
        rows = result.all()
        
        messages = []
        for chat_msg, pet in rows:
            # Декодируем JSON данные
            data = None
            if chat_msg.data:
                try:
                    data = json.loads(chat_msg.data)
                except json.JSONDecodeError:
                    data = {}
            
            messages.append({
                'id': chat_msg.id,
                'pet_id': chat_msg.pet_id,
                'pet_name': pet.name,
                'pet_photo': pet.photo_file_id,
                'pet_character_id': pet.character_id,
                'pet_level': pet.level,
                'event_type': chat_msg.event_type,
                'message': chat_msg.message,
                'data': data,
                'created_at': chat_msg.created_at
            })
        
        return messages
    
    async def get_by_pet(self, pet_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Получить сообщения конкретного питомца
        
        Args:
            pet_id: ID питомца
            limit: Максимальное количество сообщений
        
        Returns:
            List[Dict]: Список сообщений
        """
        query = (
            select(ChatMessage, Pet)
            .join(Pet, ChatMessage.pet_id == Pet.id)
            .where(ChatMessage.pet_id == pet_id)
            .order_by(desc(ChatMessage.created_at))
            .limit(limit)
        )
        
        result = await self.session.execute(query)
        rows = result.all()
        
        messages = []
        for chat_msg, pet in rows:
            data = None
            if chat_msg.data:
                try:
                    data = json.loads(chat_msg.data)
                except json.JSONDecodeError:
                    data = {}
            
            messages.append({
                'id': chat_msg.id,
                'pet_id': chat_msg.pet_id,
                'pet_name': pet.name,
                'pet_photo': pet.photo_file_id,
                'pet_character_id': pet.character_id,
                'pet_level': pet.level,
                'event_type': chat_msg.event_type,
                'message': chat_msg.message,
                'data': data,
                'created_at': chat_msg.created_at
            })
        
        return messages
    
    async def delete_old_messages(self, days: int = 30) -> int:
        """
        Удалить старые сообщения
        
        Args:
            days: Сколько дней хранить сообщения
        
        Returns:
            int: Количество удалённых сообщений
        """
        from sqlalchemy import delete
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = delete(ChatMessage).where(ChatMessage.created_at < cutoff_date)
        result = await self.session.execute(query)
        await self.session.commit()
        
        return result.rowcount
