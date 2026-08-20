"""
Интеграционный сервис для связи системы дома с другими системами

Этот сервис обеспечивает:
- Применение бонусов дома к характеристикам питомца
- Интеграцию с системой еды (уменьшение голода, восстановление энергии)
- Интеграцию с системой приключений (бонус к удаче)
- Интеграцию с ежедневной системой (ежедневные бонусы от дома)
- Интеграцию с системой достижений
"""

import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from services.house_service import HouseService
from database.repositories.pet_repository import PetRepository
from database.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


class HouseIntegrationService:
    """Сервис интеграции дома с другими системами"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.house_service = HouseService(session)
        self.pet_repo = PetRepository(session)
        self.user_repo = UserRepository(session)
    
    # === ПРИМЕНЕНИЕ БОНУСОВ ===
    
    async def apply_house_bonuses_to_pet(self, pet_id: int) -> Dict[str, Any]:
        """
        Применить все бонусы дома к питомцу
        
        Возвращает словарь с применёнными бонусами:
        {
            "energy_recovery_boost": int,  # % ускорения восстановления энергии
            "happiness_boost": int,        # + к счастью
            "hunger_reduction": int,       # % уменьшения голода
            "luck_boost": int              # % бонус к удаче
        }
        """
        house = await self.house_service.house_repo.get_by_pet_id(pet_id)
        if not house:
            return {
                "energy_recovery_boost": 0,
                "happiness_boost": 0,
                "hunger_reduction": 0,
                "luck_boost": 0
            }
        
        # Получаем бонусы из дома
        bonuses = await self.house_service._calculate_house_bonuses(
            house, 
            await self.house_service.house_repo.get_rooms(house.id)
        )
        
        return bonuses
    
    async def get_effective_pet_stats(self, pet_id: int) -> Dict[str, Any]:
        """
        Получить эффективные характеристики питомца с учётом бонусов дома
        
        Возвращает словарь с характеристиками:
        {
            "base_stats": {...},           # базовые характеристики
            "house_bonuses": {...},        # бонусы от дома
            "effective_stats": {...}       # итоговые характеристики
        }
        """
        pet = await self.pet_repo.get_by_id(pet_id)
        if not pet:
            return {"error": "Питомец не найден"}
        
        # Базовые характеристики
        base_stats = {
            "hunger": pet.hunger,
            "energy": pet.energy,
            "happiness": pet.happiness,
            "luck": pet.luck,
            "level": pet.level,
            "stomach_capacity": pet.stomach_capacity
        }
        
        # Бонусы дома
        house_bonuses = await self.apply_house_bonuses_to_pet(pet_id)
        
        # Применяем бонусы к характеристикам
        effective_stats = {
            "hunger": pet.hunger,
            "energy": pet.energy,
            "happiness": min(100, pet.happiness + house_bonuses.get("happiness_boost", 0)),
            "luck": pet.luck + (pet.luck * house_bonuses.get("luck_boost", 0) / 100),
            "level": pet.level,
            "stomach_capacity": pet.stomach_capacity,
            # Дополнительные эффективные показатели
            "energy_recovery_rate": 1 + (house_bonuses.get("energy_recovery_boost", 0) / 100),
            "hunger_reduction_rate": 1 - (house_bonuses.get("hunger_reduction", 0) / 100)
        }
        
        return {
            "base_stats": base_stats,
            "house_bonuses": house_bonuses,
            "effective_stats": effective_stats
        }
    
    # === ИНТЕГРАЦИЯ С СИСТЕМОЙ ЕДЫ ===
    
    async def apply_food_hunger_modifier(self, pet_id: int, base_hunger_gain: int) -> Tuple[int, Dict[str, Any]]:
        """
        Применить модификатор голода от дома
        
        Args:
            pet_id: ID питомца
            base_hunger_gain: базовое значение голода (плюс)
            
        Returns:
            (скорректированное значение, словарь с деталями модификации)
        """
        house = await self.house_service.house_repo.get_by_pet_id(pet_id)
        if not house:
            return base_hunger_gain, {"modifier_applied": False, "reason": "Нет дома"}
        
        # Получаем бонус уменьшения голода
        bonuses = await self.apply_house_bonuses_to_pet(pet_id)
        reduction_percent = bonuses.get("hunger_reduction", 0)
        
        if reduction_percent <= 0:
            return base_hunger_gain, {
                "modifier_applied": False,
                "reason": "Нет бонуса уменьшения голода",
                "reduction_percent": 0
            }
        
        # Применяем уменьшение
        reduction = int(base_hunger_gain * (reduction_percent / 100))
        adjusted_gain = max(1, base_hunger_gain - reduction)  # Минимум 1
        
        return adjusted_gain, {
            "modifier_applied": True,
            "base_gain": base_hunger_gain,
            "reduction_percent": reduction_percent,
            "reduction_amount": reduction,
            "adjusted_gain": adjusted_gain,
            "source": "house"
        }
    
    async def apply_energy_recovery_boost(self, pet_id: int, base_recovery: int) -> Tuple[int, Dict[str, Any]]:
        """
        Применить бонус восстановления энергии от дома
        
        Args:
            pet_id: ID питомца
            base_recovery: базовое восстановление энергии
            
        Returns:
            (скорректированное значение, словарь с деталями модификации)
        """
        house = await self.house_service.house_repo.get_by_pet_id(pet_id)
        if not house:
            return base_recovery, {"modifier_applied": False, "reason": "Нет дома"}
        
        bonuses = await self.apply_house_bonuses_to_pet(pet_id)
        boost_percent = bonuses.get("energy_recovery_boost", 0)
        
        if boost_percent <= 0:
            return base_recovery, {
                "modifier_applied": False,
                "reason": "Нет бонуса восстановления энергии",
                "boost_percent": 0
            }
        
        boost = int(base_recovery * (boost_percent / 100))
        adjusted_recovery = base_recovery + boost
        
        return adjusted_recovery, {
            "modifier_applied": True,
            "base_recovery": base_recovery,
            "boost_percent": boost_percent,
            "boost_amount": boost,
            "adjusted_recovery": adjusted_recovery,
            "source": "house"
        }
    
    # === ИНТЕГРАЦИЯ С СИСТЕМОЙ ПРИКЛЮЧЕНИЙ ===
    
    async def apply_adventure_luck_boost(self, pet_id: int, base_luck: float) -> Tuple[float, Dict[str, Any]]:
        """
        Применить бонус удачи от дома для приключений
        
        Args:
            pet_id: ID питомца
            base_luck: базовая удача (0.0 - 1.0)
            
        Returns:
            (скорректированное значение, словарь с деталями модификации)
        """
        house = await self.house_service.house_repo.get_by_pet_id(pet_id)
        if not house:
            return base_luck, {"modifier_applied": False, "reason": "Нет дома"}
        
        bonuses = await self.apply_house_bonuses_to_pet(pet_id)
        luck_boost = bonuses.get("luck_boost", 0)
        
        if luck_boost <= 0:
            return base_luck, {
                "modifier_applied": False,
                "reason": "Нет бонуса удачи",
                "luck_boost": 0
            }
        
        # Бонус удачи увеличивает шанс успеха на указанный процент
        # Например, базовый шанс 50% + бонус 10% = 60%
        adjusted_luck = base_luck * (1 + luck_boost / 100)
        adjusted_luck = min(1.0, adjusted_luck)  # Максимум 100%
        
        return adjusted_luck, {
            "modifier_applied": True,
            "base_luck": base_luck,
            "luck_boost": luck_boost,
            "adjusted_luck": adjusted_luck,
            "source": "house"
        }
    
    # === ЕЖЕДНЕВНЫЕ БОНУСЫ ===
    
    async def get_daily_house_bonus(self, pet_id: int) -> Dict[str, Any]:
        """
        Получить ежедневные бонусы от дома
        
        Возвращает:
        {
            "bonus_coins": int,
            "bonus_happiness": int,
            "bonus_energy": int,
            "house_level": int,
            "message": str
        }
        """
        house = await self.house_service.house_repo.get_by_pet_id(pet_id)
        if not house:
            return {
                "bonus_coins": 0,
                "bonus_happiness": 0,
                "bonus_energy": 0,
                "house_level": 0,
                "message": "У питомца нет дома"
            }
        
        # Бонусы зависят от уровня дома
        level = house.level
        
        # Базовая формула: 5 монет за уровень, 1 счастье за уровень, 2 энергии за уровень
        bonus_coins = 5 * level
        bonus_happiness = 1 * level
        bonus_energy = 2 * level
        
        # Дополнительные бонусы за шаблон
        template_bonus = 0
        if house.template_id == "cozy":
            template_bonus = 5
        elif house.template_id == "luxury":
            template_bonus = 15
        elif house.template_id == "mansion":
            template_bonus = 30
        
        bonus_coins += template_bonus
        
        return {
            "bonus_coins": bonus_coins,
            "bonus_happiness": bonus_happiness,
            "bonus_energy": bonus_energy,
            "house_level": level,
            "template": house.template_id,
            "message": f"🏠 Дом уровня {level} даёт ежедневный бонус!"
        }
    
    async def collect_daily_house_bonus(self, pet_id: int, user_id: int) -> Dict[str, Any]:
        """
        Собрать ежедневный бонус от дома
        
        Returns:
            {
                "success": bool,
                "message": str,
                "rewards": {"coins": int, "happiness": int, "energy": int}
            }
        """
        pet = await self.pet_repo.get_by_id(pet_id)
        if not pet:
            return {"success": False, "message": "Питомец не найден"}
        
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "Пользователь не найден"}
        
        # Получаем бонусы
        bonus_data = await self.get_daily_house_bonus(pet_id)
        if bonus_data.get("house_level", 0) == 0:
            return {"success": False, "message": bonus_data.get("message", "Ошибка")}
        
        # Проверяем, не собирали ли уже сегодня
        last_collected = getattr(pet, 'last_house_bonus', None)
        if last_collected and isinstance(last_collected, datetime):
            today = datetime.utcnow().date()
            if last_collected.date() == today:
                return {
                    "success": False,
                    "message": "Вы уже собирали ежедневный бонус дома сегодня!"
                }
        
        # Применяем бонусы
        user.coins += bonus_data["bonus_coins"]
        pet.happiness = min(100, pet.happiness + bonus_data["bonus_happiness"])
        pet.energy = min(pet.get_max_energy(), pet.energy + bonus_data["bonus_energy"])
        
        # Сохраняем время сбора
        pet.last_house_bonus = datetime.utcnow()
        
        await self.session.flush()
        
        return {
            "success": True,
            "message": bonus_data["message"],
            "rewards": {
                "coins": bonus_data["bonus_coins"],
                "happiness": bonus_data["bonus_happiness"],
                "energy": bonus_data["bonus_energy"]
            },
            "house_level": bonus_data["house_level"]
        }
    
    # === ИНТЕГРАЦИЯ С СИСТЕМОЙ ДОСТИЖЕНИЙ ===
    
    async def check_house_achievements(self, pet_id: int) -> Dict[str, Any]:
        """
        Проверить и обновить достижения, связанные с домом
        
        Возвращает список полученных достижений
        """
        house = await self.house_service.house_repo.get_by_pet_id(pet_id)
        if not house:
            return {"achievements_earned": []}
        
        achievements_earned = []
        
        # Проверяем достижения
        if house.level >= 3:
            achievements_earned.append({
                "id": "house_level_3",
                "name": "Уютный дом",
                "description": "Достигните уровня дома 3",
                "earned": True
            })
        
        if house.level >= 5:
            achievements_earned.append({
                "id": "house_level_5",
                "name": "Роскошный особняк",
                "description": "Достигните уровня дома 5",
                "earned": True
            })
        
        if house.template_id in ["luxury", "mansion"]:
            achievements_earned.append({
                "id": "house_luxury",
                "name": "Шик и блеск",
                "description": "Купите роскошный шаблон дома",
                "earned": True
            })
        
        # Проверяем количество посетителей
        if house.total_visitors >= 50:
            achievements_earned.append({
                "id": "house_popular",
                "name": "Популярный дом",
                "description": "50 посетителей дома",
                "earned": True
            })
        
        if house.total_visitors >= 100:
            achievements_earned.append({
                "id": "house_very_popular",
                "name": "Звёздный дом",
                "description": "100 посетителей дома",
                "earned": True
            })
        
        return {
            "achievements_earned": achievements_earned,
            "total_visitors": house.total_visitors,
            "house_level": house.level
        }
    
    # === СТАТИСТИКА ДОМА ===
    
    async def get_house_performance_stats(self, pet_id: int) -> Dict[str, Any]:
        """
        Получить статистику эффективности дома
        
        Возвращает:
        {
            "total_bonus_value": int,      # Общая ценность бонусов
            "visitors_per_day": float,     # Посетителей в день
            "upgrade_progress": float,     # Прогресс улучшения
            "suggestions": list            # Рекомендации по улучшению
        }
        """
        house = await self.house_service.house_repo.get_by_pet_id(pet_id)
        if not house:
            return {"error": "Дом не найден"}
        
        bonuses = await self.apply_house_bonuses_to_pet(pet_id)
        
        # Общая ценность бонусов
        total_bonus = (
            bonuses.get("energy_recovery_boost", 0) * 2 +
            bonuses.get("happiness_boost", 0) * 1.5 +
            bonuses.get("hunger_reduction", 0) * 2 +
            bonuses.get("luck_boost", 0) * 3
        )
        
        # Посетителей в день (за последние 7 дней)
        visits_count = await self.house_service.house_repo.get_visits_count(house.id, 7)
        visitors_per_day = visits_count / 7
        
        # Прогресс улучшения
        max_level = len(self.house_service.house_data.get("upgrade_costs", {})) + 1
        upgrade_progress = (house.level - 1) / (max_level - 1) * 100 if max_level > 1 else 100
        
        # Рекомендации
        suggestions = []
        
        if house.level < 3:
            suggestions.append("⬆️ Улучшите дом до 3 уровня для открытия сада")
        
        if house.template_id == "basic":
            suggestions.append("🏡 Купите шаблон 'Уютный домик' для большего количества комнат")
        
        if visitors_per_day < 1:
            suggestions.append("👥 Приглашайте друзей посетить ваш дом")
        
        # Проверяем количество комнат
        rooms = await self.house_service.house_repo.get_rooms(house.id)
        unlocked_rooms = [r for r in rooms if r.is_unlocked]
        max_rooms = 3  # По умолчанию для basic
        for template_id in ["basic", "cozy", "luxury", "mansion"]:
            tpl = self.house_service.house_data.get("house_templates", {}).get(template_id, {})
            if tpl and tpl.get("name") == house.template_id:
                max_rooms = tpl.get("max_rooms", 3)
                break
        
        if len(unlocked_rooms) < max_rooms:
            suggestions.append(f"🔓 Откройте новую комнату (у вас {len(unlocked_rooms)}/{max_rooms})")
        
        return {
            "total_bonus_value": round(total_bonus, 1),
            "visitors_per_day": round(visitors_per_day, 1),
            "upgrade_progress": round(upgrade_progress, 1),
            "suggestions": suggestions
        }
    
    # === ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ===
    
    async def apply_all_house_effects(self, pet_id: int, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Применить все эффекты дома к текущему контексту
        
        Это единый метод для применения всех бонусов дома
        к различным аспектам игры
        
        Args:
            pet_id: ID питомца
            context: словарь с параметрами контекста
                может содержать: 'hunger', 'energy', 'luck', 'happiness'
                
        Returns:
            словарь с применёнными эффектами
        """
        results = {}
        
        # Применяем бонусы к каждой характеристике, если она есть в контексте
        if "hunger" in context:
            adjusted, details = await self.apply_food_hunger_modifier(
                pet_id, 
                context["hunger"]
            )
            results["hunger"] = {
                "original": context["hunger"],
                "adjusted": adjusted,
                "details": details
            }
        
        if "energy" in context:
            adjusted, details = await self.apply_energy_recovery_boost(
                pet_id,
                context["energy"]
            )
            results["energy"] = {
                "original": context["energy"],
                "adjusted": adjusted,
                "details": details
            }
        
        if "luck" in context:
            adjusted, details = await self.apply_adventure_luck_boost(
                pet_id,
                context["luck"]
            )
            results["luck"] = {
                "original": context["luck"],
                "adjusted": adjusted,
                "details": details
            }
        
        if "happiness" in context:
            # Применяем бонус счастья
            bonuses = await self.apply_house_bonuses_to_pet(pet_id)
            boost = bonuses.get("happiness_boost", 0)
            adjusted = context["happiness"] + boost
            results["happiness"] = {
                "original": context["happiness"],
                "adjusted": adjusted,
                "details": {
                    "modifier_applied": boost > 0,
                    "boost_amount": boost,
                    "source": "house"
                }
            }
        
        return results
