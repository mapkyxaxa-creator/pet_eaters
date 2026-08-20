import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories.photo_repository import PhotoRepository
from database.models import Photo

logger = logging.getLogger(__name__)


class PhotoService:
    """Сервис для работы с альбомом фотографий"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.photo_repo = PhotoRepository(session)
    
    async def add_photo(
        self,
        pet_id: int,
        telegram_file_id: str,
        caption: str = None,
        is_main: bool = False,
        is_approved: bool = False
    ) -> Optional[Photo]:
        """Добавить фото в альбом"""
        try:
            photo = await self.photo_repo.add_photo(
                pet_id=pet_id,
                telegram_file_id=telegram_file_id,
                caption=caption,
                is_main=is_main,
                is_approved=is_approved
            )
            await self.session.flush()
            logger.info(f"Добавлено фото для питомца {pet_id}, одобрено: {is_approved}")
            return photo
        except Exception as e:
            logger.error(f"Ошибка добавления фото: {e}")
            return None
    
    async def add_photo_with_moderation(
        self,
        pet_id: int,
        telegram_file_id: str,
        caption: str = None,
        is_main: bool = False,
        auto_approve: bool = False
    ) -> Optional[Photo]:
        """Добавить фото с модерацией"""
        try:
            is_approved = auto_approve  # Если auto_approve=True, фото сразу одобрено
            photo = await self.photo_repo.add_photo(
                pet_id=pet_id,
                telegram_file_id=telegram_file_id,
                caption=caption,
                is_main=is_main,
                is_approved=is_approved
            )
            await self.session.flush()
            await self.session.refresh(photo)
            logger.info(f"Добавлено фото для питомца {pet_id}, одобрено: {is_approved}")
            return photo
        except Exception as e:
            logger.error(f"Ошибка добавления фото: {e}")
            return None
    
    async def get_photos(self, pet_id: int, limit: int = 20) -> List[Photo]:
        """Получить все одобренные фото питомца"""
        return await self.photo_repo.get_photos(pet_id, limit)
    
    async def get_all_photos_including_pending(self, pet_id: int, limit: int = 20) -> List[Photo]:
        """Получить все фото питомца (включая на модерации)"""
        return await self.photo_repo.get_all_photos_including_pending(pet_id, limit)
    
    async def get_photo(self, photo_id: int) -> Optional[Photo]:
        """Получить фото по ID"""
        return await self.photo_repo.get_photo(photo_id)
    
    async def get_by_id(self, photo_id: int) -> Optional[Photo]:
        """Получить фото по ID"""
        return await self.photo_repo.get_by_id(photo_id)
    
    async def get_main_photo(self, pet_id: int) -> Optional[Photo]:
        """Получить главное одобренное фото"""
        return await self.photo_repo.get_main_photo(pet_id)
    
    async def get_pending_photos(self, limit: int = 20) -> List[Photo]:
        """Получить фото на модерации"""
        return await self.photo_repo.get_pending_photos(limit)
    
    async def get_pending_photos_with_details(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Получить фото на модерации с данными питомца и владельца"""
        return await self.photo_repo.get_pending_photos_with_details(limit)
    
    async def get_pending_count(self) -> int:
        """Количество фото на модерации"""
        return await self.photo_repo.get_pending_count()
    
    async def approve_photo(self, photo_id: int, admin_id: int) -> Optional[Photo]:
        """Одобрить фото"""
        photo = await self.photo_repo.approve_photo(photo_id, admin_id)
        await self.session.flush()
        if photo:
            logger.info(f"Фото {photo_id} одобрено админом {admin_id}")
        return photo
    
    async def reject_photo(self, photo_id: int, admin_id: int, reason: str = None) -> Optional[Photo]:
        """Отклонить фото"""
        photo = await self.photo_repo.reject_photo(photo_id, admin_id, reason)
        await self.session.flush()
        if photo:
            logger.info(f"Фото {photo_id} отклонено админом {admin_id}, причина: {reason}")
        return photo
    
    async def delete_photo(self, photo_id: int) -> bool:
        """Удалить фото"""
        result = await self.photo_repo.delete_photo(photo_id)
        await self.session.flush()
        if result:
            logger.info(f"Удалено фото {photo_id}")
        return result
    
    async def set_main_photo(self, pet_id: int, photo_id: int) -> bool:
        """Установить главное фото"""
        result = await self.photo_repo.set_main_photo(pet_id, photo_id)
        await self.session.flush()
        if result:
            logger.info(f"Фото {photo_id} установлено как главное для питомца {pet_id}")
        return result
    
    async def get_photos_count(self, pet_id: int) -> int:
        """Получить количество одобренных фото"""
        return await self.photo_repo.get_photos_count(pet_id)
    
    async def get_pending_photo_by_id(self, photo_id: int) -> Optional[Photo]:
        """Получить фото на модерации по ID"""
        return await self.photo_repo.get_pending_photo_by_id(photo_id)
