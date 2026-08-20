import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories.daily_reward_repository import DailyRewardRepository
from database.repositories.user_repository import UserRepository
from database.repositories.pet_repository import PetRepository
from database.repositories.inventory_repository import InventoryRepository
from services.data_loader import data_loader
from services.level_service import LevelService

logger = logging.getLogger(__name__)


class DailyService:
    """Сервис для работы с ежедневными наградами"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.daily_repo = DailyRewardRepository(session)
        self.user_repo = UserRepository(session)
        self.pet_repo = PetRepository(session)
        self.inventory_repo = InventoryRepository(session)
        self.level_service = LevelService(session)
        self.daily_data = data_loader.get("daily_rewards", {})
        self.days = self.daily_data.get("days", [])
    
    async def get_daily_info(self, user_id: int) -> Dict[str, Any]:
        """Получить информацию о ежедневной награде"""
        user = await self.user_repo.get_by_telegram_id(user_id)
        if not user:
            return {"success": False, "message": "Пользователь не найден"}
        
        daily = await self.daily_repo.get_by_user_id(user.id)
        if not daily:
            daily = await self.daily_repo.create(user.id)
        
        can_claim = await self.daily_repo.can_claim(user.id)
        current_day = daily.streak_days + 1 if can_claim else daily.streak_days
        
        reward = self._get_reward_for_day(current_day)
        
        return {
            "success": True,
            "streak": daily.streak_days,
            "current_day": current_day,
            "can_claim": can_claim,
            "next_claim": daily.next_claim_available,
            "reward": reward
        }
    
    def _get_reward_for_day(self, day: int) -> Optional[Dict]:
        """Получить награду для дня"""
        if day > 30:
            day = ((day - 1) % 30) + 1
        
        for d in self.days:
            if d.get("day") == day:
                return d
        return None
    
    async def claim_daily_reward(self, user_id: int) -> Dict[str, Any]:
        """Получить ежедневную награду"""
        user = await self.user_repo.get_by_telegram_id(user_id)
        if not user:
            return {"success": False, "message": "Пользователь не найден"}
        
        if not await self.daily_repo.can_claim(user.id):
            daily = await self.daily_repo.get_by_user_id(user.id)
            if daily:
                return {
                    "success": False,
                    "message": f"⏳ Награда будет доступна завтра",
                    "next_claim": daily.next_claim_available
                }
        
        daily = await self.daily_repo.get_by_user_id(user.id)
        if not daily:
            daily = await self.daily_repo.create(user.id)
        
        if daily.last_claim_date:
            days_gap = (datetime.utcnow() - daily.last_claim_date).days
            if days_gap > 1:
                daily.streak_days = 0
        
        daily.streak_days += 1
        current_day = daily.streak_days
        
        reward = self._get_reward_for_day(current_day)
        if not reward:
            return {"success": False, "message": "Награда не найдена"}
        
        pet = await self.pet_repo.get_by_user_id(user.id)
        reward_type = reward.get("reward_type")
        reward_amount = reward.get("reward_amount", 0)
        reward_item = reward.get("reward_item")
        
        # === ВСЕ ИЗМЕНЕНИЯ В ОДНОЙ ТРАНЗАКЦИИ ===
        if reward_type == "coins":
            user.coins += reward_amount
            reward_text = f"💰 +{reward_amount} монет"
        elif reward_type == "item":
            if reward_item:
                await self.inventory_repo.add_item(user.id, reward_item, reward_amount)
                foods = data_loader.get("foods", {})
                item_data = foods.get(reward_item, {})
                item_name = item_data.get("name", reward_item)
                item_emoji = item_data.get("emoji", "")
                reward_text = f"{item_emoji} {item_name} x{reward_amount}"
            else:
                reward_text = "🎁 Сундук"
        else:
            reward_text = "🎁 Награда"
        
        # Обновляем стрик
        await self.daily_repo.update_streak(user.id, daily.streak_days)
        await self.session.flush()
        
        return {
            "success": True,
            "message": f"📅 День {current_day}!\n"
                      f"Награда: {reward_text}\n"
                      f"🔥 Стрик: {daily.streak_days} дней",
            "streak": daily.streak_days,
            "reward": reward
        }