import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories.user_repository import UserRepository
from database.repositories.pet_repository import PetRepository
from database.repositories.premium_repository import PremiumRepository
from database.repositories.cosmetic_repository import CosmeticRepository
from services.data_loader import data_loader
from services.payment_service import PaymentService

logger = logging.getLogger(__name__)


class PremiumService:
    """Сервис для работы с Premium и Battle Pass"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.pet_repo = PetRepository(session)
        self.premium_repo = PremiumRepository(session)
        self.cosmetic_repo = CosmeticRepository(session)
        self.payment_service = PaymentService(session)
        self.premium_data = data_loader.get("premium", {})
        self.battlepass_data = data_loader.get("battlepass", {})
    
    # === PREMIUM ===
    
    async def get_premium_info(self) -> Dict[str, Any]:
        """Получить информацию о Premium"""
        return self.premium_data.get("premium", {})
    
    async def buy_premium(self, user_id: int, pet_id: int) -> Dict[str, Any]:
        """
        Купить Premium подписку
        
        Args:
            user_id: Telegram ID пользователя
            pet_id: ID питомца
        
        Returns:
            {
                "success": bool,
                "message": str
            }
        """
        premium_info = await self.get_premium_info()
        price = premium_info.get("price", 500)
        duration = premium_info.get("duration_days", 30)
        
        user = await self.user_repo.get_by_telegram_id(user_id)
        if not user:
            return {"success": False, "message": "Пользователь не найден"}
        
        pet = await self.pet_repo.get_by_id(pet_id)
        if not pet or pet.user_id != user.id:
            return {"success": False, "message": "Питомец не найден"}
        
        if user.premium_currency < price:
            return {
                "success": False,
                "message": f"Недостаточно 💎! Нужно: {price}, у тебя: {user.premium_currency}",
                "need": price,
                "have": user.premium_currency
            }
        
        # Списываем лапки
        user.premium_currency -= price
        
        # Активируем Premium
        await self.premium_repo.activate_premium(user.id, duration)
        
        # Выдаём бонусы Premium
        await self._give_premium_bonuses(pet, user)
        
        await self.session.flush()
        
        logger.info(f"Пользователь {user_id} купил Premium на {duration} дней за {price} 💎")
        
        return {
            "success": True,
            "message": f"👑 <b>Premium активирован!</b>\n\n"
                      f"📅 Длительность: {duration} дней\n"
                      f"✨ Бонусы активированы!\n"
                      f"💰 Осталось: {user.premium_currency} 💎",
            "premium_until": user.premium_until.strftime("%d.%m.%Y"),
            "balance": user.premium_currency
        }
    
    async def _give_premium_bonuses(self, pet, user) -> None:
        """Выдать бонусы Premium"""
        # Уникальная рамка
        await self.cosmetic_repo.unlock_frame(pet.id, "premium_frame")
        pet.frame_id = "premium_frame"
        
        # Значок Premium
        # Сохраняется в отдельном поле или как титул
        
        logger.info(f"Питомцу {pet.id} выданы бонусы Premium")
    
    async def check_premium_status(self, user_id: int) -> Dict[str, Any]:
        """Проверить статус Premium"""
        user = await self.user_repo.get_by_telegram_id(user_id)
        if not user:
            return {"success": False, "message": "Пользователь не найден"}
        
        is_active = user.is_premium()
        remaining_days = await self.premium_repo.get_premium_remaining_days(user.id)
        
        return {
            "success": True,
            "is_active": is_active,
            "remaining_days": remaining_days,
            "premium_until": user.premium_until.strftime("%d.%m.%Y") if user.premium_until else None
        }
    
    async def get_premium_features(self) -> List[Dict[str, Any]]:
        """Получить список функций Premium"""
        premium_info = await self.get_premium_info()
        return premium_info.get("features", [])
    
    # === BATTLE PASS ===
    
    async def get_battlepass_info(self) -> Dict[str, Any]:
        """Получить информацию о Battle Pass"""
        return self.battlepass_data
    
    async def get_battlepass_progress(self, user_id: int) -> Dict[str, Any]:
        """Получить прогресс Battle Pass пользователя"""
        season_id = self.battlepass_data.get("season", 1)
        progress = await self.premium_repo.get_battlepass_progress(user_id, season_id)
        
        total_levels = self.battlepass_data.get("levels", 30)
        
        # Получаем награды
        rewards = self.battlepass_data.get("rewards", {})
        free_rewards = rewards.get("free", [])
        premium_rewards = rewards.get("premium", [])
        
        # Формируем список наград для текущего уровня
        current_level = progress.get("level", 0)
        available_free = []
        available_premium = []
        
        for reward in free_rewards:
            if reward.get("level") <= current_level:
                available_free.append(reward)
        
        if progress.get("premium_unlocked"):
            for reward in premium_rewards:
                if reward.get("level") <= current_level:
                    available_premium.append(reward)
        
        return {
            "success": True,
            "season": season_id,
            "level": progress.get("level", 0),
            "xp": progress.get("xp", 0),
            "xp_to_next": progress.get("xp_to_next", 100),
            "total_levels": total_levels,
            "premium_unlocked": progress.get("premium_unlocked", False),
            "claimed_rewards": progress.get("claimed_rewards", {}),
            "available_free_rewards": available_free,
            "available_premium_rewards": available_premium
        }
    
    async def add_battlepass_xp(self, user_id: int, xp: int) -> Dict[str, Any]:
        """Добавить XP в Battle Pass"""
        season_id = self.battlepass_data.get("season", 1)
        battlepass = await self.premium_repo.add_battlepass_xp(user_id, xp, season_id)
        
        # Проверяем новые награды
        new_levels = []
        progress = await self.get_battlepass_progress(user_id)
        
        return {
            "success": True,
            "level": battlepass.level,
            "xp": battlepass.xp,
            "new_levels": new_levels
        }
    
    async def unlock_premium_battlepass(self, user_id: int) -> Dict[str, Any]:
        """Разблокировать Premium Battle Pass"""
        season_id = self.battlepass_data.get("season", 1)
        price = 300  # Цена в лапках
        
        user = await self.user_repo.get_by_telegram_id(user_id)
        if not user:
            return {"success": False, "message": "Пользователь не найден"}
        
        if user.premium_currency < price:
            return {
                "success": False,
                "message": f"Недостаточно 💎! Нужно: {price}, у тебя: {user.premium_currency}",
                "need": price,
                "have": user.premium_currency
            }
        
        user.premium_currency -= price
        battlepass = await self.premium_repo.unlock_premium_battlepass(user.id, season_id)
        
        await self.session.flush()
        
        logger.info(f"Пользователь {user_id} разблокировал Premium Battle Pass")
        
        return {
            "success": True,
            "message": "🎖️ Premium Battle Pass разблокирован!",
            "balance": user.premium_currency
        }
    
    async def claim_battlepass_reward(self, user_id: int, level: int) -> Dict[str, Any]:
        """Забрать награду Battle Pass"""
        season_id = self.battlepass_data.get("season", 1)
        
        # Проверяем, можно ли забрать награду
        can_claim = await self.premium_repo.claim_battlepass_reward(user_id, level, season_id)
        if not can_claim:
            return {"success": False, "message": "Награда уже получена или уровень не достигнут"}
        
        # Находим награду
        rewards = self.battlepass_data.get("rewards", {})
        free_rewards = rewards.get("free", [])
        premium_rewards = rewards.get("premium", [])
        
        reward = None
        for r in free_rewards:
            if r.get("level") == level:
                reward = r
                break
        
        if not reward:
            for r in premium_rewards:
                if r.get("level") == level:
                    reward = r
                    break
        
        if not reward:
            return {"success": False, "message": "Награда не найдена"}
        
        # Выдаём награду
        user = await self.user_repo.get_by_telegram_id(user_id)
        if not user:
            return {"success": False, "message": "Пользователь не найден"}
        
        pet = await self.pet_repo.get_by_user_id(user.id)
        
        await self._give_battlepass_reward(user, pet, reward)
        await self.session.flush()
        
        return {
            "success": True,
            "message": f"✅ Награда получена!",
            "reward": reward
        }
    
    async def _give_battlepass_reward(self, user, pet, reward: Dict[str, Any]) -> None:
        """Выдать награду Battle Pass"""
        reward_type = reward.get("type")
        amount = reward.get("amount", 1)
        item_id = reward.get("item_id")
        cosmetic_id = reward.get("cosmetic_id")
        frame_id = reward.get("frame_id")
        
        if reward_type == "coins":
            user.coins += amount
        
        elif reward_type == "xp" and pet:
            from services.level_service import LevelService
            level_service = LevelService(self.session)
            await level_service.add_experience(pet, amount)
        
        elif reward_type == "item" and item_id:
            from services.inventory_service import InventoryService
            inventory_service = InventoryService(self.session)
            await inventory_service.inventory_repo.add_item(user.id, item_id, amount)
        
        elif reward_type == "cosmetic" and cosmetic_id and pet:
            await self.cosmetic_repo.unlock_cosmetic(pet.id, cosmetic_id)
        
        elif reward_type == "frame" and frame_id and pet:
            await self.cosmetic_repo.unlock_frame(pet.id, frame_id)
        
        logger.info(f"Выдана награда Battle Pass: {reward_type} пользователю {user.id}")