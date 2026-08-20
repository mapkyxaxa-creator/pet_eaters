import logging
from typing import Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from database.models import AdventureHistory, AdventureCooldown, Pet

logger = logging.getLogger(__name__)


class AdventureRepository:
    """Репозиторий для работы с приключениями"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_last_adventure(self, pet_id: int) -> Optional[AdventureHistory]:
        """Получение последнего приключения питомца"""
        result = await self.session.execute(
            select(AdventureHistory)
            .where(AdventureHistory.pet_id == pet_id)
            .order_by(desc(AdventureHistory.started_at))
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    async def create_adventure(
        self,
        pet_id: int,
        location_id: str,
        duration: int
    ) -> AdventureHistory:
        """Создание записи о начале приключения"""
        logger.info(f"📝 СОЗДАНИЕ ПРИКЛЮЧЕНИЯ: pet_id={pet_id}, location_id={location_id}, duration={duration}")
        adventure = AdventureHistory(
            pet_id=pet_id,
            location_id=location_id,
            duration=duration,
            started_at=datetime.utcnow()
        )
        self.session.add(adventure)
        await self.session.flush()
        logger.info(f"✅ ПРИКЛЮЧЕНИЕ СОЗДАНО: id={adventure.id}, pet_id={pet_id}, location_id={location_id}")
        logger.info(f"💾 ДАННЫЕ СОХРАНЕНЫ В БАЗУ: adventure_id={adventure.id}")
        return adventure
    
    async def complete_adventure(
        self,
        adventure_id: int,
        reward_type: str = None,
        reward_amount: int = None,
        reward_item_id: str = None,
        event_id: str = None,
        event_text: str = None,
        xp_gained: int = 0,
        coins_gained: int = 0
    ) -> AdventureHistory:
        """Завершение приключения"""
        logger.info(f"🔚 ЗАВЕРШЕНИЕ ПРИКЛЮЧЕНИЯ: adventure_id={adventure_id}, reward_type={reward_type}, xp_gained={xp_gained}, coins_gained={coins_gained}")
        result = await self.session.execute(
            select(AdventureHistory).where(AdventureHistory.id == adventure_id)
        )
        adventure = result.scalar_one()
        
        adventure.completed_at = datetime.utcnow()
        adventure.reward_type = reward_type
        adventure.reward_amount = reward_amount
        adventure.reward_item_id = reward_item_id
        adventure.event_id = event_id
        adventure.event_text = event_text
        adventure.xp_gained = xp_gained
        adventure.coins_gained = coins_gained
        
        await self.session.flush()
        logger.info(f"✅ ПРИКЛЮЧЕНИЕ ЗАВЕРШЕНО: adventure_id={adventure_id}, completed_at={adventure.completed_at}")
        logger.info(f"💾 ОБНОВЛЕННЫЕ ДАННЫЕ СОХРАНЕНЫ: adventure_id={adventure_id}, xp={xp_gained}, coins={coins_gained}")
        return adventure
    
    async def get_cooldown(self, pet_id: int, location_id: str) -> Optional[AdventureCooldown]:
        """Получение кулдауна для локации"""
        result = await self.session.execute(
            select(AdventureCooldown)
            .where(
                and_(
                    AdventureCooldown.pet_id == pet_id,
                    AdventureCooldown.location_id == location_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def set_cooldown(
        self,
        pet_id: int,
        location_id: str,
        cooldown_until: datetime
    ) -> AdventureCooldown:
        """Установка кулдауна для локации"""
        logger.info(f"⏳ УСТАНОВКА КУЛДАУНА: pet_id={pet_id}, location_id={location_id}, cooldown_until={cooldown_until}")
        cooldown = await self.get_cooldown(pet_id, location_id)
        
        if cooldown:
            cooldown.cooldown_until = cooldown_until
            cooldown.updated_at = datetime.utcnow()
            logger.info(f"🔄 ОБНОВЛЕНИЕ КУЛДАУНА: pet_id={pet_id}, location_id={location_id}, new_cooldown={cooldown_until}")
        else:
            cooldown = AdventureCooldown(
                pet_id=pet_id,
                location_id=location_id,
                cooldown_until=cooldown_until
            )
            self.session.add(cooldown)
            logger.info(f"✨ СОЗДАНИЕ НОВОГО КУЛДАУНА: pet_id={pet_id}, location_id={location_id}, cooldown_until={cooldown_until}")
        
        await self.session.flush()
        logger.info(f"💾 КУЛДАУН СОХРАНЕН: pet_id={pet_id}, location_id={location_id}")
        return cooldown
    
    async def get_adventure_history(
        self,
        pet_id: int,
        limit: int = 10
    ) -> List[AdventureHistory]:
        """Получение истории приключений"""
        result = await self.session.execute(
            select(AdventureHistory)
            .where(AdventureHistory.pet_id == pet_id)
            .order_by(desc(AdventureHistory.started_at))
            .limit(limit)
        )
        return result.scalars().all()    
    async def get_adventure_by_id(self, adventure_id: int) -> Optional[AdventureHistory]:
        """Получение приключения по ID"""
        result = await self.session.execute(
            select(AdventureHistory).where(AdventureHistory.id == adventure_id)
        )
        return result.scalar_one_or_none()
    
    async def get_active_adventure(self, pet_id: int) -> Optional[AdventureHistory]:
        """Получение активного приключения питомца (незавершенного)"""
        result = await self.session.execute(
            select(AdventureHistory)
            .where(
                and_(
                    AdventureHistory.pet_id == pet_id,
                    AdventureHistory.completed_at.is_(None)
                )
            )
            .order_by(desc(AdventureHistory.started_at))
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    async def get_pending_adventure(self, pet_id: int) -> Optional[AdventureHistory]:
        """Получение ожидающего завершения приключения питомца"""
        result = await self.session.execute(
            select(AdventureHistory)
            .where(
                and_(
                    AdventureHistory.pet_id == pet_id,
                    AdventureHistory.completed_at.is_(None)
                )
            )
            .order_by(desc(AdventureHistory.started_at))
            .limit(1)
        )
        return result.scalar_one_or_none()
