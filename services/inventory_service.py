import logging
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories.inventory_repository import InventoryRepository
from database.repositories.pet_repository import PetRepository
from database.repositories.food_stats_repository import FoodStatsRepository
from services.data_loader import data_loader

logger = logging.getLogger(__name__)


class InventoryService:
    """Сервис для работы с инвентарем"""
    
    def __init__(self, session: AsyncSession, achievement_service=None):
        self.session = session
        self.inventory_repo = InventoryRepository(session)
        self.pet_repo = PetRepository(session)
        self.food_stats_repo = FoodStatsRepository(session)
        self.achievement_service = achievement_service
        self.foods = data_loader.get("foods", {})
    
    async def get_inventory(self, user_id: int) -> List[Dict[str, Any]]:
        """Получение инвентаря с данными о предметах"""
        items = await self.inventory_repo.get_all_items(user_id)
        result = []
        
        for item in items:
            food_data = self.foods.get(item.item_id, {})
            if food_data:
                result.append({
                    "id": item.item_id,
                    "name": food_data.get("name", item.item_id),
                    "emoji": food_data.get("emoji", ""),
                    "rarity": food_data.get("rarity", "common"),
                    "quantity": item.quantity,
                    "hunger": food_data.get("hunger", 0),
                    "experience": food_data.get("experience", 0),
                    "coin_value": food_data.get("coin_value", 0),
                    "sell_price": food_data.get("sell_price", 0),
                    "description": food_data.get("description", "")
                })
        
        return result
    
    async def get_item_count(self, user_id: int, item_id: str) -> int:
        """Получение количества предмета"""
        item = await self.inventory_repo.get_item(user_id, item_id)
        return item.quantity if item else 0
    
    async def get_total_items(self, user_id: int) -> int:
        """Получение общего количества предметов"""
        items = await self.inventory_repo.get_all_items(user_id)
        return sum(item.quantity for item in items)
    
    async def get_unique_food_count(self, user_id: int) -> int:
        """Получить количество уникальных блюд, которые когда-либо были найдены (через food_stats)"""
        # Получаем питомца пользователя
        pet = await self.pet_repo.get_by_user_id(user_id)
        if not pet:
            return 0
        
        # Получаем всю статистику поедания из food_stats
        stats = await self.food_stats_repo.get_all_by_pet(pet.id)
        
        # Считаем уникальные блюда
        unique_foods = set()
        for stat in stats:
            if stat.count > 0 and stat.food_id in self.foods:
                unique_foods.add(stat.food_id)
        
        return len(unique_foods)
    
    async def check_collection_achievements(self, user_id: int, pet_id: int) -> List[Dict]:
        """Проверить достижения коллекционера"""
        if not self.achievement_service:
            return []
        
        # Получаем реальное количество уникальных блюд из food_stats
        unique_count = await self.get_unique_food_count(user_id)
        
        # Обновляем collected_items у питомца
        pet = await self.pet_repo.get_by_id(pet_id)
        if pet:
            pet.collected_items = unique_count
            await self.pet_repo.update(pet)
        
        # Проверяем достижения
        return await self.achievement_service.check_all_achievements(pet_id)