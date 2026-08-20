import logging
import random
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories.pet_repository import PetRepository
from database.repositories.user_repository import UserRepository
from database.repositories.inventory_repository import InventoryRepository
from database.repositories.food_stats_repository import FoodStatsRepository
from services.data_loader import data_loader
from services.quest_service import QuestService
from services.premium_service import PremiumService

logger = logging.getLogger(__name__)


class FoodService:
    """Сервис для работы с едой"""
    
    def __init__(self, session: AsyncSession, level_service, achievement_service):
        self.session = session
        self.pet_repo = PetRepository(session)
        self.user_repo = UserRepository(session)
        self.inventory_repo = InventoryRepository(session)
        self.food_stats_repo = FoodStatsRepository(session)
        self.level_service = level_service
        self.achievement_service = achievement_service
        self.quest_service = QuestService(session)
        self.premium_service = PremiumService(session)
        self.balance = data_loader.get_balance()
        self.foods = data_loader.get("foods", {})
    
    async def eat_food(self, user_id: int, pet_id: int, food_id: str) -> Dict[str, Any]:
        """
        Поедание еды питомцем
        """
        # Получаем данные
        user = await self.user_repo.get_by_telegram_id(user_id)
        if not user:
            return {"success": False, "message": "Пользователь не найден"}
        
        pet = await self.pet_repo.get_by_id(pet_id)
        if not pet:
            return {"success": False, "message": "Питомец не найден"}
        
        food = self.foods.get(food_id)
        if not food:
            return {"success": False, "message": "Такой еды не существует"}
        
        # Проверяем наличие в инвентаре
        if not await self.inventory_repo.has_item(user.id, food_id):
            return {"success": False, "message": "У вас нет этой еды в инвентаре"}
        
        # Проверяем, может ли питомец есть
        hunger_percent = pet.get_hunger_percent()
        if hunger_percent >= 200:
            return {"success": False, "message": "💀 Питомец в катастрофическом состоянии! Подожди."}
        
        if hunger_percent >= 150:
            return {"success": False, "message": "🤢 У питомца тяжелый желудок! Подожди немного."}
        
        # Сохраняем старую сытость для проверки переедания
        old_hunger_percent = pet.get_hunger_percent()
        
        # Рассчитываем сытость
        hunger_gain = food.get("hunger", 0)
        
        # Применяем бонус характера Обжора
        character_bonus = 1.0
        characters = data_loader.get("characters", {})
        character = characters.get(pet.character_id, {})
        bonus = character.get("bonus", {})
        if "hunger" in bonus:
            character_bonus = bonus["hunger"]
        
        hunger_gain = int(hunger_gain * character_bonus)
        
        # Проверка критического жора
        is_critical = self._check_critical_eat(pet.luck)
        if is_critical:
            hunger_gain *= 2
            logger.info(f"Критический жор! {pet.name} съел в 2 раза больше")
        
        # Обновляем сытость
        max_hunger = pet.get_max_hunger()
        new_hunger = min(pet.hunger + hunger_gain, max_hunger)
        pet.hunger = new_hunger
        
        # Проверяем переедание (сытость > 100% после еды И до еды было <= 100%)
        new_hunger_percent = pet.get_hunger_percent()
        if new_hunger_percent > 100 and old_hunger_percent <= 100:
            pet.total_overeat += 1
            logger.info(f"Переедание! {pet.name} съел больше чем нужно")
        
        # Начисляем XP
        xp_gain = food.get("experience", 0)
        if is_critical:
            xp_gain = int(xp_gain * 1.5)
        
        # Проверяем уровень
        new_level = False
        if xp_gain > 0:
            leveled_up, new_level_data = await self.level_service.add_experience(pet, xp_gain)
            new_level = leveled_up
        
        # Обновляем статистику питомца
        pet.total_eaten += 1
        
        # Обновляем время последнего приема пищи
        pet.last_eat = datetime.utcnow()
        pet.last_hunger_update = datetime.utcnow()
        
        # === ВСЕ ИЗМЕНЕНИЯ В ОДНОЙ ТРАНЗАКЦИИ ===
        # 1. Удаляем еду из инвентаря
        await self.inventory_repo.remove_item(user.id, food_id, 1)
        
        # 2. Обновляем статистику по конкретной еде
        await self.food_stats_repo.increment_count(pet.id, food_id, 1)
        
        # 3. Обновляем питомца
        await self.pet_repo.update(pet)
        
        # 4. Обновляем задания
        await self.quest_service.update_quest_progress(user_id, "eat_any", 1)
        await self.quest_service.update_quest_progress(user_id, "eat_item", 1, food_id)
        if food_id == "pizza":
            await self.quest_service.update_quest_progress(user_id, "eat_item", 1, "pizza")
        if food_id == "cookie":
            await self.quest_service.update_quest_progress(user_id, "eat_item", 1, "cookie")
        
        # 5. Проверяем достижения
        unlocked = await self.achievement_service.check_all_achievements(pet.id)
        
        # 6. Начисляем Battle Pass XP (за каждое поедание)
        if xp_gain > 0:
            await self.premium_service.add_battlepass_xp(user_id, xp_gain // 10 + 1)
        
        # ===== ОБНОВЛЯЕМ ОЧКИ В СОРЕВНОВАНИИ =====
        try:
            from services.competition_service import CompetitionService
            competition_service = CompetitionService(self.session)
            
            food_data = self.foods.get(food_id, {})
            points = food_data.get("hunger", 0) // 10 + 1
            if points <= 0:
                points = 1
            
            await competition_service.submit_food_eaten(
                pet_id=pet.id,
                food_amount=points
            )
            logger.info(f"🏆 ОЧКИ В СОРЕВНОВАНИИ: pet_id={pet.id}, food={food_id}, points={points}")
        except Exception as e:
            logger.error(f"❌ Ошибка обновления очков соревнования: {e}")
        
        # 7. Единый flush
        await self.session.flush()
        
        # Проверяем статус
        status, status_text = pet.get_hunger_status()
        
        # Формируем сообщение
        message = self._format_eat_message(
            food_name=food.get("name", food_id),
            food_emoji=food.get("emoji", ""),
            hunger_gain=hunger_gain,
            xp_gain=xp_gain,
            is_critical=is_critical,
            new_level=new_level,
            status_emoji=status,
            status_text=status_text,
            hunger_percent=pet.get_hunger_percent(),
            unlocked_achievements=unlocked
        )
        
        return {
            "success": True,
            "message": message,
            "hunger_gained": hunger_gain,
            "xp_gained": xp_gain,
            "is_critical": is_critical,
            "new_level": new_level,
            "status": status,
            "hunger_percent": pet.get_hunger_percent(),
            "unlocked_achievements": unlocked
        }
    
    def _check_critical_eat(self, luck: float) -> bool:
        """Проверка на критический жор"""
        base_chance = self.balance.get("base_critical_eat_chance", 0.05)
        chance = base_chance + (luck * 0.3)
        return random.random() < chance
    
    def _format_eat_message(
        self,
        food_name: str,
        food_emoji: str,
        hunger_gain: int,
        xp_gain: int,
        is_critical: bool,
        new_level: bool,
        status_emoji: str,
        status_text: str,
        hunger_percent: float,
        unlocked_achievements: list = None
    ) -> str:
        """Форматирование сообщения о еде"""
        lines = []
        
        # Эмодзи и название еды
        lines.append(f"{food_emoji} <b>Съедено:</b> {food_name}")
        lines.append("")
        
        # Критический жор
        if is_critical:
            lines.append("💥 <b>КРИТИЧЕСКИЙ ЖОР!</b> В 2 раза больше сытости!")
            lines.append("")
        
        # Сытость
        lines.append(f"🍽️ <b>Сытость:</b> +{hunger_gain}")
        lines.append(f"📊 <b>Текущая сытость:</b> {hunger_percent:.0f}%")
        lines.append(f"📊 <b>Статус:</b> {status_emoji} {status_text}")
        lines.append("")
        
        # XP
        lines.append(f"✨ <b>Опыт:</b> +{xp_gain}")
        
        # Новый уровень
        if new_level:
            lines.append("🎉 <b>НОВЫЙ УРОВЕНЬ!</b>")
        
        # Новые достижения
        if unlocked_achievements:
            lines.append("")
            lines.append("🏆 <b>НОВЫЕ ДОСТИЖЕНИЯ!</b>")
            for ach in unlocked_achievements:
                ach_data = ach.get("data", {})
                ach_name = ach_data.get("name", "Неизвестное достижение")
                ach_emoji = ach_data.get("emoji", "🏆")
                lines.append(f"{ach_emoji} {ach_name}")
        
        return "\n".join(lines)