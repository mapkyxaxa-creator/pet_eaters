from typing import Optional, List
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from database.models import GiftLog, Gift


class GiftLogRepository:
    """Репозиторий для работы с логами подарков"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_user_id_and_date(
        self, 
        user_id: int, 
        date: date
    ) -> List[GiftLog]:
        """Получить все логи подарков пользователя за день"""
        start_of_day = datetime(date.year, date.month, date.day)
        end_of_day = datetime(date.year, date.month, date.day, 23, 59, 59)
        
        result = await self.session.execute(
            select(GiftLog)
            .where(
                and_(
                    GiftLog.user_id == user_id,
                    GiftLog.date >= start_of_day,
                    GiftLog.date <= end_of_day
                )
            )
        )
        return result.scalars().all()
    
    async def get_by_user_date_rarity(
        self, 
        user_id: int, 
        date: date,
        rarity: str
    ) -> Optional[GiftLog]:
        """Получить лог по пользователю, дате и редкости"""
        start_of_day = datetime(date.year, date.month, date.day)
        end_of_day = datetime(date.year, date.month, date.day, 23, 59, 59)
        
        result = await self.session.execute(
            select(GiftLog)
            .where(
                and_(
                    GiftLog.user_id == user_id,
                    GiftLog.date >= start_of_day,
                    GiftLog.date <= end_of_day,
                    GiftLog.item_rarity == rarity
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def add_gift_log(
        self,
        user_id: int,
        item_id: str,
        item_rarity: str,
        quantity: int = 1
    ) -> GiftLog:
        """Добавить запись о подарке"""
        log = GiftLog(
            user_id=user_id,
            item_id=item_id,
            item_rarity=item_rarity,
            quantity=quantity,
            date=datetime.utcnow()
        )
        self.session.add(log)
        await self.session.flush()
        return log
    
    async def increment_gift_count(
        self,
        user_id: int,
        item_id: str,
        item_rarity: str,
        quantity: int = 1
    ) -> GiftLog:
        """Увеличить счётчик подарков за день"""
        today = datetime.utcnow().date()
        log = await self.get_by_user_date_rarity(user_id, today, item_rarity)
        
        if log:
            log.quantity += quantity
            log.updated_at = datetime.utcnow()
        else:
            log = GiftLog(
                user_id=user_id,
                item_id=item_id,
                item_rarity=item_rarity,
                quantity=quantity,
                date=datetime.utcnow()
            )
            self.session.add(log)
        
        await self.session.flush()
        return log
    
    async def get_today_gift_count(
        self,
        user_id: int,
        rarity: str
    ) -> int:
        """Получить количество подарков за сегодня по редкости"""
        today = datetime.utcnow().date()
        log = await self.get_by_user_date_rarity(user_id, today, rarity)
        return log.quantity if log else 0