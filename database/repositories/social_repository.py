from typing import Optional, List, Tuple
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc
from database.models import Like, Gift, Pet, User


class SocialRepository:
    """Репозиторий для работы с социальными взаимодействиями"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    # === ЛАЙКИ ===
    
    async def get_like(self, from_user_id: int, pet_id: int) -> Optional[Like]:
        """Получить лайк от пользователя к питомцу"""
        result = await self.session.execute(
            select(Like).where(
                and_(
                    Like.from_user_id == from_user_id,
                    Like.pet_id == pet_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def add_like(self, from_user_id: int, pet_id: int) -> Like:
        """Поставить лайк"""
        like = Like(
            from_user_id=from_user_id,
            pet_id=pet_id,
            created_at=datetime.utcnow()
        )
        self.session.add(like)
        await self.session.flush()
        return like
    
    async def remove_like(self, from_user_id: int, pet_id: int) -> bool:
        """Убрать лайк"""
        like = await self.get_like(from_user_id, pet_id)
        if like:
            await self.session.delete(like)
            await self.session.flush()
            return True
        return False
    
    async def get_pet_likes_count(self, pet_id: int) -> int:
        """Получить количество лайков у питомца"""
        result = await self.session.execute(
            select(func.count(Like.id)).where(Like.pet_id == pet_id)
        )
        return result.scalar() or 0
    
    async def get_user_liked_pets(self, user_id: int) -> List[int]:
        """Получить ID питомцев, которым поставил лайк пользователь"""
        result = await self.session.execute(
            select(Like.pet_id).where(Like.from_user_id == user_id)
        )
        return result.scalars().all()
    
    # === ПОДАРКИ ===
    
    async def send_gift(
        self,
        from_user_id: int,
        to_user_id: int,
        item_id: str,
        quantity: int = 1,
        message: str = None,
        item_type: str = "food"  # <-- ДОБАВЛЕН ПАРАМЕТР
    ) -> Gift:
        """Отправить подарок"""
        gift = Gift(
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            item_id=item_id,
            item_type=item_type,  # <-- ДОБАВЛЕНО
            quantity=quantity,
            message=message,
            created_at=datetime.utcnow(),
            is_read=False
        )
        self.session.add(gift)
        await self.session.flush()
        return gift
    
    async def get_gift_by_id(self, gift_id: int) -> Optional[Gift]:
        """Получить подарок по ID"""
        return await self.session.get(Gift, gift_id)
    
    async def get_received_gifts(self, user_id: int, limit: int = 10) -> List[Gift]:
        """Получить полученные подарки"""
        result = await self.session.execute(
            select(Gift)
            .where(Gift.to_user_id == user_id)
            .order_by(desc(Gift.created_at))
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_sent_gifts(self, user_id: int, limit: int = 10) -> List[Gift]:
        """Получить отправленные подарки"""
        result = await self.session.execute(
            select(Gift)
            .where(Gift.from_user_id == user_id)
            .order_by(desc(Gift.created_at))
            .limit(limit)
        )
        return result.scalars().all()
    
    async def mark_gift_as_read(self, gift_id: int) -> bool:
        """Отметить подарок как прочитанный"""
        gift = await self.session.get(Gift, gift_id)
        if gift:
            gift.is_read = True
            await self.session.flush()
            return True
        return False
    
    async def get_unread_gifts_count(self, user_id: int) -> int:
        """Получить количество непрочитанных подарков"""
        result = await self.session.execute(
            select(func.count(Gift.id))
            .where(
                and_(
                    Gift.to_user_id == user_id,
                    Gift.is_read == False
                )
            )
        )
        return result.scalar() or 0
    
    # === РЕЙТИНГ ===
    
    async def get_rating_by_level(self, limit: int = 10) -> List[Tuple[Pet, User]]:
        """Получить рейтинг по уровню"""
        result = await self.session.execute(
            select(Pet, User)
            .join(User, Pet.user_id == User.id)
            .order_by(desc(Pet.level), desc(Pet.experience))
            .limit(limit)
        )
        return result.all()
    
    async def get_rating_by_likes(self, limit: int = 10) -> List[Tuple[Pet, User]]:
        """Получить рейтинг по лайкам"""
        result = await self.session.execute(
            select(Pet, User)
            .join(User, Pet.user_id == User.id)
            .order_by(desc(Pet.total_likes))
            .limit(limit)
        )
        return result.all()
    
    async def get_user_rank_by_level(self, pet_id: int) -> int:
        """Получить место пользователя в рейтинге по уровню"""
        subquery = select(Pet.level).where(Pet.id == pet_id).scalar_subquery()
        result = await self.session.execute(
            select(func.count(Pet.id) + 1)
            .where(Pet.level > subquery)
        )
        return result.scalar() or 1
    
    async def get_user_rank_by_likes(self, pet_id: int) -> int:
        """Получить место пользователя в рейтинге по лайкам"""
        subquery = select(Pet.total_likes).where(Pet.id == pet_id).scalar_subquery()
        result = await self.session.execute(
            select(func.count(Pet.id) + 1)
            .where(Pet.total_likes > subquery)
        )
        return result.scalar() or 1