from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_, func, or_
from database.models import Photo, Pet, User


class PhotoRepository:
    """Репозиторий для работы с фотографиями"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def add_photo(
        self,
        pet_id: int,
        telegram_file_id: str,
        caption: str = None,
        is_main: bool = False,
        is_approved: bool = False
    ) -> Photo:
        """Добавить фото в альбом"""
        # Если это главное фото, снимаем флаг с других
        if is_main:
            await self._remove_main_flag(pet_id)
        
        photo = Photo(
            pet_id=pet_id,
            telegram_file_id=telegram_file_id,
            caption=caption,
            is_main=is_main,
            is_approved=is_approved,
            is_rejected=False,
            created_at=datetime.utcnow()
        )
        self.session.add(photo)
        await self.session.flush()
        await self.session.refresh(photo)
        return photo
    
    async def _remove_main_flag(self, pet_id: int) -> None:
        """Снять флаг is_main со всех фото питомца"""
        result = await self.session.execute(
            select(Photo).where(
                and_(
                    Photo.pet_id == pet_id,
                    Photo.is_main == True
                )
            )
        )
        for photo in result.scalars().all():
            photo.is_main = False
        await self.session.flush()
    
    async def get_photos(self, pet_id: int, limit: int = 20) -> List[Photo]:
        """Получить все одобренные фото питомца"""
        result = await self.session.execute(
            select(Photo)
            .where(
                and_(
                    Photo.pet_id == pet_id,
                    Photo.is_approved == True,
                    Photo.is_rejected == False
                )
            )
            .order_by(desc(Photo.is_main), desc(Photo.created_at))
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_all_photos_including_pending(self, pet_id: int, limit: int = 20) -> List[Photo]:
        """Получить все фото питомца (включая на модерации)"""
        result = await self.session.execute(
            select(Photo)
            .where(Photo.pet_id == pet_id)
            .order_by(desc(Photo.is_main), desc(Photo.created_at))
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_main_photo(self, pet_id: int) -> Optional[Photo]:
        """Получить главное одобренное фото питомца"""
        result = await self.session.execute(
            select(Photo)
            .where(
                and_(
                    Photo.pet_id == pet_id,
                    Photo.is_main == True,
                    Photo.is_approved == True,
                    Photo.is_rejected == False
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_photo(self, photo_id: int) -> Optional[Photo]:
        """Получить фото по ID"""
        return await self.session.get(Photo, photo_id)
    
    async def get_by_id(self, photo_id: int) -> Optional[Photo]:
        """Получить фото по ID (алиас для get_photo)"""
        return await self.session.get(Photo, photo_id)
    
    async def get_pending_photos(self, limit: int = 20) -> List[Photo]:
        """Получить фото на модерации"""
        result = await self.session.execute(
            select(Photo)
            .where(
                and_(
                    Photo.is_approved == False,
                    Photo.is_rejected == False
                )
            )
            .order_by(Photo.created_at)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_pending_photos_with_details(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Получить фото на модерации с данными питомца и владельца"""
        result = await self.session.execute(
            select(Photo, Pet, User)
            .join(Pet, Photo.pet_id == Pet.id)
            .join(User, Pet.user_id == User.id)
            .where(
                and_(
                    Photo.is_approved == False,
                    Photo.is_rejected == False
                )
            )
            .order_by(Photo.created_at)
            .limit(limit)
        )
        
        items = []
        for photo, pet, user in result.all():
            items.append({
                "photo": photo,
                "pet": pet,
                "user": user
            })
        return items
    
    async def get_pending_count(self) -> int:
        """Количество фото на модерации"""
        result = await self.session.execute(
            select(func.count(Photo.id))
            .where(
                and_(
                    Photo.is_approved == False,
                    Photo.is_rejected == False
                )
            )
        )
        return result.scalar() or 0
    
    async def approve_photo(self, photo_id: int, admin_id: int) -> Optional[Photo]:
        """Одобрить фото"""
        photo = await self.get_photo(photo_id)
        if photo:
            photo.is_approved = True
            photo.is_rejected = False
            photo.reviewed_at = datetime.utcnow()
            photo.reviewed_by = admin_id
            await self.session.flush()
            await self.session.refresh(photo)
            return photo
        return None
    
    async def reject_photo(self, photo_id: int, admin_id: int, reason: str = None) -> Optional[Photo]:
        """Отклонить фото"""
        photo = await self.get_photo(photo_id)
        if photo:
            photo.is_approved = False
            photo.is_rejected = True
            photo.reviewed_at = datetime.utcnow()
            photo.reviewed_by = admin_id
            photo.reject_reason = reason
            await self.session.flush()
            await self.session.refresh(photo)
            return photo
        return None
    
    async def delete_photo(self, photo_id: int) -> bool:
        """Удалить фото"""
        photo = await self.get_photo(photo_id)
        if photo:
            await self.session.delete(photo)
            await self.session.flush()
            return True
        return False
    
    async def set_main_photo(self, pet_id: int, photo_id: int) -> bool:
        """Установить главное фото"""
        photo = await self.get_photo(photo_id)
        if not photo or photo.pet_id != pet_id:
            return False
        
        # Снимаем флаг с других фото
        await self._remove_main_flag(pet_id)
        
        photo.is_main = True
        await self.session.flush()
        return True
    
    async def get_photos_count(self, pet_id: int) -> int:
        """Получить количество одобренных фото в альбоме"""
        result = await self.session.execute(
            select(func.count(Photo.id))
            .where(
                and_(
                    Photo.pet_id == pet_id,
                    Photo.is_approved == True,
                    Photo.is_rejected == False
                )
            )
        )
        return result.scalar() or 0
    
    async def get_pending_photo_by_id(self, photo_id: int) -> Optional[Photo]:
        """Получить фото на модерации по ID"""
        result = await self.session.execute(
            select(Photo)
            .where(
                and_(
                    Photo.id == photo_id,
                    Photo.is_approved == False,
                    Photo.is_rejected == False
                )
            )
        )
        return result.scalar_one_or_none()
