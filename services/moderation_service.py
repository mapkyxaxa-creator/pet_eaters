import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories.photo_repository import PhotoRepository
from database.repositories.pet_repository import PetRepository
from database.repositories.user_repository import UserRepository
from database.models import Photo, Pet, User

logger = logging.getLogger(__name__)


class ModerationService:
    """Сервис для модерации контента"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.photo_repo = PhotoRepository(session)
        self.pet_repo = PetRepository(session)
        self.user_repo = UserRepository(session)
    
    async def get_pending_photos(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Получить фото на модерации с деталями"""
        return await self.photo_repo.get_pending_photos_with_details(limit)
    
    async def get_pending_count(self) -> int:
        """Получить количество фото на модерации"""
        return await self.photo_repo.get_pending_count()
    
    async def approve_photo(self, photo_id: int, admin_id: int) -> Dict[str, Any]:
        """Одобрить фото"""
        photo = await self.photo_repo.approve_photo(photo_id, admin_id)
        await self.session.flush()
        
        if photo:
            return {
                "success": True,
                "message": "✅ Фото одобрено",
                "photo": photo
            }
        return {
            "success": False,
            "message": "❌ Фото не найдено",
            "photo": None
        }
    
    async def reject_photo(self, photo_id: int, admin_id: int, reason: str = None) -> Dict[str, Any]:
        """Отклонить фото"""
        photo = await self.photo_repo.reject_photo(photo_id, admin_id, reason)
        await self.session.flush()
        
        if photo:
            return {
                "success": True,
                "message": "❌ Фото отклонено",
                "photo": photo
            }
        return {
            "success": False,
            "message": "❌ Фото не найдено",
            "photo": None
        }
    
    async def get_photo_details(self, photo_id: int) -> Optional[Dict[str, Any]]:
        """Получить детали фото для модерации"""
        photo = await self.photo_repo.get_pending_photo_by_id(photo_id)
        if not photo:
            return None
        
        pet = await self.pet_repo.get_by_id(photo.pet_id)
        if not pet:
            return None
        
        user = await self.user_repo.get_by_id(pet.user_id)
        if not user:
            return None
        
        return {
            "photo": photo,
            "pet": pet,
            "user": user
        }
    
    async def get_photo_for_moderation(self, photo_id: int) -> Optional[Photo]:
        """Получить фото для модерации по ID"""
        return await self.photo_repo.get_pending_photo_by_id(photo_id)
    
    async def is_photo_pending(self, photo_id: int) -> bool:
        """Проверить, находится ли фото на модерации"""
        photo = await self.photo_repo.get_pending_photo_by_id(photo_id)
        return photo is not None
    
    async def get_pending_photo_info(self, photo: Photo) -> Dict[str, Any]:
        """Получить информацию о фото для отображения"""
        pet = await self.pet_repo.get_by_id(photo.pet_id)
        if not pet:
            return {}
        
        user = await self.user_repo.get_by_id(pet.user_id)
        if not user:
            return {}
        
        return {
            "photo_id": photo.id,
            "pet_name": pet.name,
            "pet_id": pet.id,
            "owner_name": user.first_name or user.username or "Пользователь",
            "owner_id": user.telegram_id,
            "caption": photo.caption,
            "created_at": photo.created_at,
            "file_id": photo.telegram_file_id
        }
