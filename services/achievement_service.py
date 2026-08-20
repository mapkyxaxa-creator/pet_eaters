import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories.achievement_repository import AchievementRepository
from database.repositories.pet_repository import PetRepository
from database.repositories.user_repository import UserRepository
from database.repositories.inventory_repository import InventoryRepository
from database.repositories.food_stats_repository import FoodStatsRepository
from services.data_loader import data_loader
from services.chat_service import ChatService, RARE_ACHIEVEMENTS

logger = logging.getLogger(__name__)


class AchievementService:
    """Сервис для работы с достижениями"""
    
    def __init__(self, session: AsyncSession, level_service=None):
        self.session = session
        self.achievement_repo = AchievementRepository(session)
        self.pet_repo = PetRepository(session)
        self.user_repo = UserRepository(session)
        self.inventory_repo = InventoryRepository(session)
        self.food_stats_repo = FoodStatsRepository(session)
        self.level_service = level_service
        self.achievements_data = data_loader.get("achievements", {})
        self.titles_data = data_loader.get("titles", {})
    
    def set_level_service(self, level_service):
        self.level_service = level_service
    
    async def check_all_achievements(self, pet_id: int) -> List[Dict[str, Any]]:
        """Проверить все достижения для питомца"""
        pet = await self.pet_repo.get_by_id(pet_id)
        if not pet:
            return []
        
        unlocked = []
        for ach_id, ach_data in self.achievements_data.items():
            if await self.achievement_repo.is_unlocked(pet_id, ach_id):
                continue
            
            if await self._check_condition(pet, ach_data):
                achievement = await self.achievement_repo.unlock(pet_id, ach_id)
                unlocked.append({
                    "id": ach_id,
                    "data": ach_data,
                    "achievement": achievement
                })
                await self._give_reward(pet, ach_data)
        
        if unlocked:
            await self.session.flush()
        
        return unlocked
    
    async def _check_condition(self, pet, ach_data: Dict) -> bool:
        """Проверить условие достижения"""
        condition_type = ach_data.get("condition_type")
        condition_value = ach_data.get("condition_value", 0)
        condition_item = ach_data.get("condition_item")
        
        if condition_type == "eat_count":
            return await self._check_eat_count(pet.id, condition_item, condition_value)
        elif condition_type == "total_eat":
            return pet.total_eaten >= condition_value
        elif condition_type == "overeat_count":
            return pet.total_overeat >= condition_value
        elif condition_type == "adventure_count":
            return pet.total_adventures >= condition_value
        elif condition_type == "level":
            return pet.level >= condition_value
        elif condition_type == "collect_count":
            return pet.collected_items >= condition_value
        elif condition_type == "competition_wins":
            return pet.competition_wins >= condition_value
        elif condition_type == "find_legendary":
            return pet.found_legendary >= condition_value
        elif condition_type == "inactive_days":
            if pet.last_active_date:
                days = (datetime.utcnow() - pet.last_active_date).days
                return days >= condition_value
        return False
    
    async def _check_eat_count(self, pet_id: int, item_id: str, count: int) -> bool:
        """Проверить количество съеденной конкретной еды через food_stats"""
        stat = await self.food_stats_repo.get_by_pet_and_food(pet_id, item_id)
        if not stat:
            return False
        return stat.count >= count
    
    async def _give_reward(self, pet, ach_data: Dict) -> None:
        """Выдать награду за достижение"""
        reward_coins = ach_data.get("reward_coins", 0)
        reward_xp = ach_data.get("reward_xp", 0)
        reward_title = ach_data.get("reward_title")
        
        user = await self.user_repo.get_by_id(pet.user_id)
        
        if reward_coins > 0 and user:
            user.coins += reward_coins
        
        if reward_xp > 0 and self.level_service:
            await self.level_service.add_experience(pet, reward_xp)
        
        if reward_title and not pet.title_id:
            pet.title_id = reward_title
        
        logger.info(f"Достижение {ach_data.get('id')} разблокировано")
    
    async def get_unlocked_achievements(self, pet_id: int) -> List[Dict]:
        """Получить список разблокированных достижений"""
        achievements = await self.achievement_repo.get_by_pet_id(pet_id)
        result = []
        for ach in achievements:
            ach_data = self.achievements_data.get(ach.achievement_id, {})
            if ach_data:
                result.append({
                    "id": ach.achievement_id,
                    "name": ach_data.get("name", ach.achievement_id),
                    "emoji": ach_data.get("emoji", ""),
                    "description": ach_data.get("description", ""),
                    "unlocked_at": ach.unlocked_at
                })
        return result
    
    async def get_available_titles(self, pet) -> List[Dict]:
        """Получить список доступных титулов для питомца"""
        # Получаем все достижения питомца
        achievements = await self.achievement_repo.get_by_pet_id(pet.id)
        available = []
        seen_titles = set()
        
        # Титулы из достижений
        for ach in achievements:
            ach_data = self.achievements_data.get(ach.achievement_id, {})
            title_id = ach_data.get("reward_title")
            if title_id and title_id in self.titles_data:
                if title_id not in seen_titles:
                    title_data = self.titles_data[title_id]
                    available.append({
                        "id": title_id,
                        "name": title_data.get("name", title_id),
                        "emoji": title_data.get("emoji", ""),
                        "description": title_data.get("description", ""),
                        "is_active": pet.title_id == title_id
                    })
                    seen_titles.add(title_id)
        
        # ===== СОЦИАЛЬНЫЕ ТИТУЛЫ (из достижений social_likes_*) =====
        social_title_ids = ["social_likes_100", "social_likes_500", "social_likes_1000", "social_likes_5000", "social_likes_10000"]
        
        # Проверяем, есть ли достижения для социальных титулов
        for ach in achievements:
            if ach.achievement_id in social_title_ids:
                title_id = ach.achievement_id
                if title_id in self.titles_data and title_id not in seen_titles:
                    title_data = self.titles_data[title_id]
                    available.append({
                        "id": title_id,
                        "name": title_data.get("name", title_id),
                        "emoji": title_data.get("emoji", ""),
                        "description": title_data.get("description", ""),
                        "is_active": pet.title_id == title_id
                    })
                    seen_titles.add(title_id)
        
        # Титулы за сюжетные главы
        story_chapters = data_loader.get("story", {}).get("chapters", [])
        for chapter in story_chapters:
            chapter_order = chapter.get("order", 0)
            if pet.story_progress >= chapter_order:
                title_name = chapter.get("rewards", {}).get("title")
                if title_name:
                    # Ищем ID титула по имени
                    for tid, tdata in self.titles_data.items():
                        if tdata.get("name") == title_name and tid not in seen_titles:
                            available.append({
                                "id": tid,
                                "name": tdata.get("name", tid),
                                "emoji": tdata.get("emoji", ""),
                                "description": tdata.get("description", ""),
                                "is_active": pet.title_id == tid
                            })
                            seen_titles.add(tid)
                            break
        
        # Добавляем "Новичок" всегда
        available.insert(0, {
            "id": "newcomer",
            "name": "Новичок",
            "emoji": "🐣",
            "description": "Создать питомца",
            "is_active": pet.title_id == "newcomer" or not pet.title_id
        })
        
        return available
    
    async def set_title(self, pet_id: int, title_id: str) -> bool:
        """Установить титул"""
        pet = await self.pet_repo.get_by_id(pet_id)
        if not pet:
            return False
        
        titles = await self.get_available_titles(pet)
        for title in titles:
            if title["id"] == title_id:
                pet.title_id = title_id
                await self.session.flush()
                return True
        return False