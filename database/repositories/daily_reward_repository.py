from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import DailyReward


class DailyRewardRepository:
    """Репозиторий для работы с ежедневными наградами"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_user_id(self, user_id: int) -> Optional[DailyReward]:
        """Получить данные о ежедневных наградах пользователя"""
        result = await self.session.execute(
            select(DailyReward).where(DailyReward.user_id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def create(self, user_id: int) -> DailyReward:
        """Создать запись о ежедневных наградах"""
        daily = DailyReward(
            user_id=user_id,
            streak_days=0,
            last_claim_date=None,
            next_claim_available=datetime.utcnow()
        )
        self.session.add(daily)
        await self.session.flush()
        return daily
    
    async def update_streak(self, user_id: int, streak: int) -> DailyReward:
        """Обновить стрик"""
        daily = await self.get_by_user_id(user_id)
        if not daily:
            daily = await self.create(user_id)
        
        daily.streak_days = streak
        daily.last_claim_date = datetime.utcnow()
        daily.next_claim_available = datetime.utcnow() + timedelta(days=1)
        await self.session.flush()
        return daily
    
    async def can_claim(self, user_id: int) -> bool:
        """Можно ли получить награду"""
        daily = await self.get_by_user_id(user_id)
        if not daily:
            return True
        
        return datetime.utcnow() >= daily.next_claim_available
    
    async def reset_all_for_new_day(self) -> None:
        """Сбросить статус всех ежедневных наград для нового дня"""
        now = datetime.utcnow()
        today = now.date()
        
        result = await self.session.execute(select(DailyReward))
        all_dailies = result.scalars().all()
        
        for daily in all_dailies:
            # Если последнее получение было не сегодня
            if daily.last_claim_date is None:
                # Никогда не получал — можно получить
                daily.next_claim_available = now
                continue
            
            last_claim_date = daily.last_claim_date.date()
            
            # Проверяем пропуск дня
            days_gap = (today - last_claim_date).days
            
            if days_gap == 0:
                # Уже получал сегодня — ничего не делаем
                continue
            elif days_gap == 1:
                # Получал вчера — можно получить сегодня, стрик продолжается
                daily.next_claim_available = now
            else:
                # Пропустил день или больше — сбрасываем стрик
                daily.streak_days = 0
                daily.next_claim_available = now
        
        await self.session.flush()