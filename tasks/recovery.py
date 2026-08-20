"""
Задача для восстановления характеристик питомца
Восстанавливает энергию и сытость со временем
"""
import logging
from datetime import datetime, timedelta
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import async_session
from database.models import Pet
from database.repositories.pet_repository import PetRepository

logger = logging.getLogger(__name__)


class RecoveryTask:
    """Задача для восстановления характеристик питомца"""
    
    ENERGY_RECOVERY_PER_HOUR = 5
    HUNGER_RECOVERY_PER_HOUR = -3
    
    @staticmethod
    async def run() -> None:
        """Запустить восстановление для всех питомцев"""
        logger.info("🔄 Запуск восстановления характеристик...")
        
        try:
            async with async_session() as session:
                pet_repo = PetRepository(session)
                pets = await pet_repo.get_all()
                
                updated_count = 0
                for pet in pets:
                    if await RecoveryTask._recover_pet(session, pet):
                        updated_count += 1
                
                await session.commit()
                logger.info(f"✅ Восстановлено {updated_count} питомцев")
                
        except Exception as e:
            logger.error(f"❌ Ошибка при восстановлении: {e}")
            raise
    
    @staticmethod
    async def _recover_pet(session: AsyncSession, pet: Pet) -> bool:
        """Восстановить характеристики одного питомца"""
        now = datetime.utcnow()
        last_recovery = pet.last_recovery or now
        
        hours_passed = (now - last_recovery).total_seconds() / 3600
        hours_passed = min(hours_passed, 24.0)
        
        if hours_passed < 0.1:
            return False
        
        max_energy = 100
        energy_recovery = int(hours_passed * RecoveryTask.ENERGY_RECOVERY_PER_HOUR)
        new_energy = min(max_energy, pet.energy + energy_recovery)
        
        hunger_change = int(hours_passed * RecoveryTask.HUNGER_RECOVERY_PER_HOUR)
        new_hunger = max(0, pet.hunger + hunger_change)
        
        if new_energy == pet.energy and new_hunger == pet.hunger:
            return False
        
        pet.energy = new_energy
        pet.hunger = new_hunger
        pet.last_recovery = now
        
        logger.debug(
            f"🔄 Восстановление {pet.name}: "
            f"энергия {pet.energy}→{new_energy}, "
            f"голод {pet.hunger}→{new_hunger}"
        )
        
        return True
    
    @staticmethod
    async def recover_single_pet(pet_id: int) -> None:
        """Восстановить характеристики конкретного питомца"""
        try:
            async with async_session() as session:
                pet_repo = PetRepository(session)
                pet = await pet_repo.get_by_id(pet_id)
                
                if pet:
                    await RecoveryTask._recover_pet(session, pet)
                    await session.commit()
                    
        except Exception as e:
            logger.error(f"❌ Ошибка при восстановлении питомца {pet_id}: {e}")
    
    @staticmethod
    async def run_for_active_users() -> None:
        """Восстановить характеристики только для активных пользователей"""
        logger.info("🔄 Запуск восстановления для активных пользователей...")
        
        try:
            async with async_session() as session:
                pet_repo = PetRepository(session)
                
                seven_days_ago = datetime.utcnow() - timedelta(days=7)
                pets = await pet_repo.get_active_users_pets(seven_days_ago)
                
                if not pets:
                    logger.info("✅ Нет активных питомцев для восстановления")
                    return
                
                updated_count = 0
                for pet in pets:
                    if await RecoveryTask._recover_pet(session, pet):
                        updated_count += 1
                
                await session.commit()
                logger.info(f"✅ Восстановлено {updated_count} активных питомцев")
                
        except Exception as e:
            logger.error(f"❌ Ошибка при восстановлении активных пользователей: {e}")