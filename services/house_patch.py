"""
House System Patch Module

This module provides monkey-patching functions to integrate the house system
with existing services without modifying their source code directly.

The patch adds house bonus calculations to:
- FoodService: hunger reduction
- AdventureService: luck boost, energy recovery
- PetService: stat calculations
- DailyService: daily bonuses from house
"""

import logging
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from services.house_integration import HouseIntegrationService

logger = logging.getLogger(__name__)


class HousePatch:
    """Класс для применения патчей к существующим сервисам"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.house_integration = HouseIntegrationService(session)
    
    async def patch_food_service(self, food_service) -> None:
        """
        Патчит FoodService для применения бонусов дома
        
        Сохраняет оригинальные методы и добавляет интеграцию
        """
        # Сохраняем оригинальный метод
        original_eat = food_service.eat_food
        
        async def patched_eat(user_id: int, pet_id: int, food_id: str) -> Dict[str, Any]:
            """Патченный метод eat_food с поддержкой дома"""
            # Вызываем оригинальный метод
            result = await original_eat(user_id, pet_id, food_id)
            
            # Если успешно, применяем бонусы дома
            if result.get("success"):
                try:
                    # Получаем эффекты дома
                    effects = await self.house_integration.apply_all_house_effects(
                        pet_id,
                        {"hunger": result.get("hunger_gained", 0)}
                    )
                    
                    # Если есть эффект голода, обновляем результат
                    if "hunger" in effects and effects["hunger"]["details"].get("modifier_applied"):
                        result["house_effect"] = effects["hunger"]["details"]
                        result["hunger_gained"] = effects["hunger"]["adjusted"]
                        
                        # Обновляем сообщение
                        if "message" in result:
                            result["message"] = result["message"] + "\n\n🏠 <b>Бонус дома применён!</b>"
                except Exception as e:
                    logger.error(f"Ошибка при применении бонуса дома в FoodService: {e}")
            
            return result
        
        # Применяем патч
        food_service.eat_food = patched_eat
        logger.info("FoodService патч применён")
    
    async def patch_adventure_service(self, adventure_service) -> None:
        """
        Патчит AdventureService для применения бонусов дома
        """
        original_start = adventure_service.start_adventure
        
        async def patched_start(user_id: int, pet_id: int, location_id: str) -> Dict[str, Any]:
            """Патченный метод start_adventure с поддержкой дома"""
            # Вызываем оригинальный метод
            result = await original_start(user_id, pet_id, location_id)
            
            # Если успешно, применяем бонусы дома
            if result.get("success"):
                try:
                    # Получаем питомца
                    pet = await adventure_service.pet_repo.get_by_id(pet_id)
                    if pet:
                        # Применяем бонус удачи к приключению
                        luck_effect = await self.house_integration.apply_adventure_luck_boost(
                            pet_id, pet.luck
                        )
                        
                        if luck_effect[1].get("modifier_applied"):
                            # Сохраняем бонус удачи в результат
                            result["house_luck_boost"] = luck_effect[1]
                            result["effective_luck"] = luck_effect[0]
                            
                            logger.info(f"Применён бонус удачи от дома: {luck_effect[1]}")
                except Exception as e:
                    logger.error(f"Ошибка при применении бонуса дома в AdventureService: {e}")
            
            return result
        
        adventure_service.start_adventure = patched_start
        logger.info("AdventureService патч применён")
    
    async def patch_pet_service(self, pet_service) -> None:
        """
        Патчит PetService для включения бонусов дома в характеристики
        """
        # Добавляем метод для получения эффективных характеристик
        async def get_effective_stats(self, pet_id: int) -> Dict[str, Any]:
            """Получить характеристики питомца с учётом бонусов дома"""
            return await self.house_integration.get_effective_pet_stats(pet_id)
        
        # Добавляем метод в pet_service
        pet_service.get_effective_stats = get_effective_stats.__get__(pet_service)
        
        # Патчим метод get_pet_stats, если он существует
        if hasattr(pet_service, 'get_pet_stats'):
            original_stats = pet_service.get_pet_stats
            
            async def patched_stats(self, pet_id: int) -> Dict[str, Any]:
                """Патченный метод get_pet_stats с бонусами дома"""
                result = await original_stats(pet_id)
                
                if result.get("success"):
                    try:
                        pet = await self.pet_repo.get_by_id(pet_id)
                        if pet:
                            # Получаем эффективные характеристики
                            stats = await self.house_integration.get_effective_pet_stats(pet_id)
                            if "effective_stats" in stats:
                                result["house_bonuses"] = stats["house_bonuses"]
                                result["effective_stats"] = stats["effective_stats"]
                    except Exception as e:
                        logger.error(f"Ошибка при получении бонусов дома: {e}")
                
                return result
            
            pet_service.get_pet_stats = patched_stats.__get__(pet_service)
        
        logger.info("PetService патч применён")
    
    async def patch_daily_service(self, daily_service) -> None:
        """
        Патчит DailyService для включения ежедневных бонусов дома
        """
        # Добавляем метод для получения ежедневных бонусов
        async def get_daily_house_bonus(self, pet_id: int) -> Dict[str, Any]:
            """Получить ежедневный бонус от дома"""
            return await self.house_integration.get_daily_house_bonus(pet_id)
        
        async def collect_daily_house_bonus(self, pet_id: int, user_id: int) -> Dict[str, Any]:
            """Собрать ежедневный бонус от дома"""
            return await self.house_integration.collect_daily_house_bonus(pet_id, user_id)
        
        # Добавляем методы
        daily_service.get_daily_house_bonus = get_daily_house_bonus.__get__(daily_service)
        daily_service.collect_daily_house_bonus = collect_daily_house_bonus.__get__(daily_service)
        
        logger.info("DailyService патч применён")
    
    async def patch_all(self, services: Dict[str, Any]) -> None:
        """
        Применить все патчи к переданным сервисам
        
        Args:
            services: словарь с сервисами {'food': FoodService, 'adventure': AdventureService, ...}
        """
        if "food" in services:
            await self.patch_food_service(services["food"])
        
        if "adventure" in services:
            await self.patch_adventure_service(services["adventure"])
        
        if "pet" in services:
            await self.patch_pet_service(services["pet"])
        
        if "daily" in services:
            await self.patch_daily_service(services["daily"])
        
        logger.info("Все патчи применены")


# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====

async def apply_house_patches(session: AsyncSession, services: Dict[str, Any]) -> None:
    """
    Удобная функция для применения всех патчей
    
    Использование:
        services = {
            'food': food_service,
            'adventure': adventure_service,
            'pet': pet_service,
            'daily': daily_service
        }
        await apply_house_patches(session, services)
    """
    patcher = HousePatch(session)
    await patcher.patch_all(services)


async def get_house_integration(session: AsyncSession) -> HouseIntegrationService:
    """Получить экземпляр HouseIntegrationService"""
    return HouseIntegrationService(session)


# ===== ДЛЯ ОБРАТНОЙ СОВМЕСТИМОСТИ =====

class HouseIntegrationHelper:
    """Хелпер для интеграции дома с существующими сервисами"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.integration = HouseIntegrationService(session)
    
    async def get_pet_effective_stats(self, pet_id: int) -> Dict[str, Any]:
        """Получить эффективные характеристики питомца"""
        return await self.integration.get_effective_pet_stats(pet_id)
    
    async def apply_food_hunger_modifier(self, pet_id: int, hunger_gain: int) -> tuple:
        """Применить модификатор голода от дома"""
        return await self.integration.apply_food_hunger_modifier(pet_id, hunger_gain)
    
    async def apply_energy_recovery_boost(self, pet_id: int, recovery: int) -> tuple:
        """Применить бонус восстановления энергии от дома"""
        return await self.integration.apply_energy_recovery_boost(pet_id, recovery)
    
    async def apply_adventure_luck_boost(self, pet_id: int, luck: float) -> tuple:
        """Применить бонус удачи от дома"""
        return await self.integration.apply_adventure_luck_boost(pet_id, luck)
    
    async def get_daily_house_bonus(self, pet_id: int) -> Dict[str, Any]:
        """Получить ежедневный бонус от дома"""
        return await self.integration.get_daily_house_bonus(pet_id)
    
    async def collect_daily_house_bonus(self, pet_id: int, user_id: int) -> Dict[str, Any]:
        """Собрать ежедневный бонус от дома"""
        return await self.integration.collect_daily_house_bonus(pet_id, user_id)
