from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from database.models import FoodStats


class FoodStatsRepository:
    """Репозиторий для работы со статистикой еды"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_pet_and_food(self, pet_id: int, food_id: str) -> Optional[FoodStats]:
        """Получить статистику по конкретной еде для питомца"""
        result = await self.session.execute(
            select(FoodStats).where(
                and_(
                    FoodStats.pet_id == pet_id,
                    FoodStats.food_id == food_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def increment_count(self, pet_id: int, food_id: str, increment: int = 1) -> FoodStats:
        """Увеличить счётчик поедания"""
        stat = await self.get_by_pet_and_food(pet_id, food_id)
        if stat:
            stat.count += increment
        else:
            stat = FoodStats(
                pet_id=pet_id,
                food_id=food_id,
                count=increment
            )
            self.session.add(stat)
        await self.session.flush()
        return stat
    
    async def get_all_by_pet(self, pet_id: int) -> List[FoodStats]:
        """Получить всю статистику по питомцу"""
        result = await self.session.execute(
            select(FoodStats).where(FoodStats.pet_id == pet_id)
        )
        return result.scalars().all()
    
    async def get_count(self, pet_id: int, food_id: str) -> int:
        """Получить количество съеденной конкретной еды"""
        stat = await self.get_by_pet_and_food(pet_id, food_id)
        return stat.count if stat else 0