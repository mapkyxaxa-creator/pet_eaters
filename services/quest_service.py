import logging
import random
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories.quest_repository import QuestRepository
from database.repositories.user_repository import UserRepository
from database.repositories.pet_repository import PetRepository
from database.repositories.inventory_repository import InventoryRepository
from services.data_loader import data_loader
# Убираем EconomyService — он не используется
from services.level_service import LevelService

logger = logging.getLogger(__name__)


class QuestService:
    """Сервис для работы с заданиями"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.quest_repo = QuestRepository(session)
        self.user_repo = UserRepository(session)
        self.pet_repo = PetRepository(session)
        self.inventory_repo = InventoryRepository(session)
        # Убираем economy_service — он не используется
        self.level_service = LevelService(session)
        self.quests_data = data_loader.get("quests", {})
        self.foods_data = data_loader.get("foods", {})
    
    async def get_daily_quests(self, user_id: int) -> List[Dict[str, Any]]:
        """Получить ежедневные задания"""
        user = await self.user_repo.get_by_telegram_id(user_id)
        if not user:
            return []
        
        quests = await self.quest_repo.get_by_user_id(user.id)
        
        if not quests:
            await self._reset_quests(user.id)
            quests = await self.quest_repo.get_by_user_id(user.id)
        else:
            need_reset = await self._need_reset(quests)
            if need_reset:
                await self._reset_quests(user.id)
                quests = await self.quest_repo.get_by_user_id(user.id)
        
        result = []
        for quest in quests:
            quest_data = self.quests_data.get(quest.quest_id, {})
            if quest_data:
                result.append({
                    "id": quest.quest_id,
                    "data": quest_data,
                    "progress": quest.progress,
                    "completed": quest.completed,
                    "claimed": quest.claimed
                })
        
        return result
    
    async def _need_reset(self, quests: List) -> bool:
        """Проверить, нужно ли сбросить задания"""
        if not quests:
            return True
        
        today = datetime.utcnow().date()
        
        for quest in quests:
            if quest.started_at.date() == today:
                return False
        
        return True
    
    async def _reset_quests(self, user_id: int) -> None:
        """Сбросить задания и создать новые"""
        old_quests = await self.quest_repo.get_by_user_id(user_id)
        for quest in old_quests:
            await self.session.delete(quest)
        
        quest_ids = list(self.quests_data.keys())
        selected = random.sample(quest_ids, min(3, len(quest_ids)))
        
        for quest_id in selected:
            await self.quest_repo.create_or_update(user_id, quest_id, 0, False)
        
        await self.session.flush()
        logger.info(f"Ежедневные задания обновлены для пользователя {user_id}")
    
    async def update_quest_progress(
        self,
        user_id: int,
        condition_type: str,
        value: int = 1,
        item_id: str = None
    ) -> List[Dict[str, Any]]:
        """Обновить прогресс заданий"""
        user = await self.user_repo.get_by_telegram_id(user_id)
        if not user:
            return []
        
        quests = await self.quest_repo.get_by_user_id(user.id)
        completed_quests = []
        
        for quest in quests:
            if quest.completed or quest.claimed:
                continue
            
            quest_data = self.quests_data.get(quest.quest_id, {})
            if not quest_data:
                continue
            
            if not self._match_condition(quest_data, condition_type, item_id):
                continue
            
            quest.progress += value
            
            condition_value = quest_data.get("condition_value", 1)
            
            if quest.progress >= condition_value:
                quest.completed = True
                quest.completed_at = datetime.utcnow()
                completed_quests.append({
                    "id": quest.quest_id,
                    "data": quest_data
                })
            
            await self.session.flush()
        
        await self.session.flush()
        return completed_quests
    
    def _match_condition(self, quest_data: Dict, condition_type: str, item_id: str = None) -> bool:
        """Проверить, подходит ли условие"""
        quest_condition = quest_data.get("condition_type")
        quest_item = quest_data.get("condition_item")
        
        if quest_condition != condition_type:
            return False
        
        if quest_item and quest_item != item_id:
            return False
        
        return True
    
    async def claim_quest_reward(self, user_id: int, quest_id: str) -> Dict[str, Any]:
        """Забрать награду за задание"""
        user = await self.user_repo.get_by_telegram_id(user_id)
        if not user:
            return {"success": False, "message": "Пользователь не найден"}
        
        quest = await self.quest_repo.get_by_id(user.id, quest_id)
        
        if not quest:
            return {"success": False, "message": "Задание не найдено"}
        
        if not quest.completed:
            return {"success": False, "message": "Задание еще не выполнено"}
        
        if quest.claimed:
            return {"success": False, "message": "Награда уже получена"}
        
        quest_data = self.quests_data.get(quest_id, {})
        if not quest_data:
            return {"success": False, "message": "Данные задания не найдены"}
        
        pet = await self.pet_repo.get_by_user_id(user.id)
        reward_coins = quest_data.get("reward_coins", 0)
        reward_xp = quest_data.get("reward_xp", 0)
        reward_item = quest_data.get("reward_item")
        
        if reward_coins > 0:
            user.coins += reward_coins
        
        if reward_xp > 0 and pet:
            await self.level_service.add_experience(pet, reward_xp)
        
        if reward_item and pet:
            await self.inventory_repo.add_item(user.id, reward_item, 1)
        
        quest.claimed = True
        quest.claimed_at = datetime.utcnow()
        await self.session.flush()
        
        return {
            "success": True,
            "message": f"✅ Награда за задание получена!",
            "coins": reward_coins,
            "xp": reward_xp,
            "item": reward_item
        }