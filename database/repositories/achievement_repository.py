from typing import Optional, List
from datetime import datetime  # <-- ДОБАВЛЕН ИМПОРТ
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from database.models import Achievement, Pet


class AchievementRepository:
    """Репозиторий для работы с достижениями"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_pet_id(self, pet_id: int) -> List[Achievement]:
        """Получить все достижения питомца"""
        result = await self.session.execute(
            select(Achievement).where(Achievement.pet_id == pet_id)
        )
        return result.scalars().all()
    
    async def get_by_id(self, pet_id: int, achievement_id: str) -> Optional[Achievement]:
        """Получить конкретное достижение"""
        result = await self.session.execute(
            select(Achievement).where(
                and_(
                    Achievement.pet_id == pet_id,
                    Achievement.achievement_id == achievement_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def unlock(self, pet_id: int, achievement_id: str) -> Achievement:
        """Разблокировать достижение"""
        achievement = Achievement(
            pet_id=pet_id,
            achievement_id=achievement_id,
            unlocked_at=datetime.utcnow()
        )
        self.session.add(achievement)
        await self.session.flush()
        return achievement
    
    async def is_unlocked(self, pet_id: int, achievement_id: str) -> bool:
        """Проверить, разблокировано ли достижение"""
        achievement = await self.get_by_id(pet_id, achievement_id)
        return achievement is not None
    
    async def count_unlocked(self, pet_id: int) -> int:
        """Количество разблокированных достижений"""
        result = await self.session.execute(
            select(Achievement).where(Achievement.pet_id == pet_id)
        )
        return len(result.scalars().all())