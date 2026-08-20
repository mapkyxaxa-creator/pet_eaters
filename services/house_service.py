import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories.house_repository import HouseRepository
from database.repositories.pet_repository import PetRepository
from database.repositories.user_repository import UserRepository
from services.data_loader import data_loader
from utils.user_utils import ensure_user, ensure_pet

logger = logging.getLogger(__name__)


class HouseService:
    """Сервис для работы с системой дома"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.house_repo = HouseRepository(session)
        self.pet_repo = PetRepository(session)
        self.user_repo = UserRepository(session)
        self.house_data = data_loader.get("houses", {})
        self.furniture_data = data_loader.get("furniture", {})
        self.balance = data_loader.get_balance()
    
    # === ИНИЦИАЛИЗАЦИЯ ===
    
    async def ensure_house(self, pet_id: int) -> Dict[str, Any]:
        """Убедиться, что у питомца есть дом"""
        house = await self.house_repo.get_by_pet_id(pet_id)
        if house:
            # Проверяем существующие комнаты: если комната заблокирована, но должна быть разблокирована
            rooms = await self.house_repo.get_rooms(house.id)
            rooms_data = self.house_data.get("rooms", {})
            updated = False
            
            for room in rooms:
                room_info = rooms_data.get(room.room_type, {})
                unlock_level = room_info.get("unlock_level", 1)
                
                if not room.is_unlocked and unlock_level <= 1:
                    room.is_unlocked = True
                    updated = True
                    logger.info(f"Разблокирована комната {room.room_type} для дома питомца {pet_id}")
            
            if updated:
                await self.session.flush()
                await self.session.refresh(house)
            
            return {"success": True, "house": house}
        
        # Создаём дом
        house = await self.house_repo.create(pet_id, "basic")
        
        # Создаём базовые комнаты
        rooms_data = self.house_data.get("rooms", {})
        template = self.house_data.get("house_templates", {}).get("basic", {})
        default_rooms = template.get("rooms", ["living_room", "kitchen", "bedroom"])
        
        for room_type in default_rooms:
            room_info = rooms_data.get(room_type, {})
            is_unlocked = room_info.get("unlock_level", 1) <= 1
            await self.house_repo.create_room(house.id, room_type, is_unlocked)
        
        await self.session.flush()
        await self.session.refresh(house)
        
        logger.info(f"Создан дом для питомца {pet_id}")
        
        return {"success": True, "house": house}
    
    # === ИНФОРМАЦИЯ О ДОМЕ ===
    
    async def get_house_info(self, pet_id: int) -> Dict[str, Any]:
        """Получить полную информацию о доме"""
        result = await self.ensure_house(pet_id)
        if not result["success"]:
            return {"success": False, "message": "Не удалось создать дом"}
        
        house = result["house"]
        templates = self.house_data.get("house_templates", {})
        template = templates.get(house.template_id, templates.get("basic", {}))
        rooms_data = self.house_data.get("rooms", {})
        
        # Получаем комнаты
        rooms = await self.house_repo.get_rooms(house.id)
        room_list = []
        for room in rooms:
            room_info = rooms_data.get(room.room_type, {})
            furniture = await self.house_repo.get_furniture_by_room(room.id)
            furniture_list = []
            for f in furniture:
                f_data = self.furniture_data.get("furniture", {}).get(f.furniture_id, {})
                furniture_list.append({
                    "id": f.furniture_id,
                    "name": f_data.get("name", f.furniture_id),
                    "emoji": f_data.get("emoji", "📦"),
                    "quantity": f.quantity,
                    "bonuses": json.loads(f.bonuses) if f.bonuses else {}
                })
            
            room_list.append({
                "type": room.room_type,
                "name": room_info.get("name", room.room_type),
                "emoji": room_info.get("emoji", "📦"),
                "description": room_info.get("description", ""),
                "is_unlocked": room.is_unlocked,
                "bonuses": json.loads(room.bonuses) if room.bonuses else {},
                "furniture": furniture_list
            })
        
        # Рассчитываем общие бонусы
        bonuses = await self._calculate_house_bonuses(house, rooms)
        
        # Получаем статистику визитов
        visits_count = await self.house_repo.get_visits_count(house.id, 7)
        
        return {
            "success": True,
            "house": {
                "id": house.id,
                "template_id": house.template_id,
                "template_name": template.get("name", "Дом"),
                "template_emoji": template.get("emoji", "🏠"),
                "level": house.level,
                "max_level": len(self.house_data.get("upgrade_costs", {})) + 1,
                "rooms": room_list,
                "bonuses": bonuses,
                "total_visits": house.total_visits,
                "total_visitors": house.total_visitors,
                "visits_this_week": visits_count
            }
        }
    
    async def _calculate_house_bonuses(self, house, rooms) -> Dict[str, int]:
        """Рассчитать общие бонусы дома"""
        bonuses = {
            "energy_recovery_boost": 0,
            "happiness_boost": 0,
            "hunger_reduction": 0,
            "luck_boost": 0
        }
        
        # Бонусы от шаблона дома
        templates = self.house_data.get("house_templates", {})
        template = templates.get(house.template_id, {})
        template_bonuses = template.get("bonuses", {})
        for key in bonuses:
            bonuses[key] += template_bonuses.get(key, 0)
        
        # Бонусы от уровня дома
        level_bonus = (house.level - 1) * 5
        bonuses["energy_recovery_boost"] += level_bonus
        bonuses["happiness_boost"] += level_bonus // 2
        
        # Бонусы от комнат
        for room in rooms:
            if room.is_unlocked:
                room_bonuses = json.loads(room.bonuses) if room.bonuses else {}
                for key in bonuses:
                    bonuses[key] += room_bonuses.get(key, 0)
                
                # Бонусы от мебели в комнате
                furniture = await self.house_repo.get_furniture_by_room(room.id)
                for f in furniture:
                    f_bonuses = json.loads(f.bonuses) if f.bonuses else {}
                    for key in bonuses:
                        bonuses[key] += f_bonuses.get(key, 0) * f.quantity
        
        # Обновляем кэш бонусов в доме
        house.energy_recovery_boost = bonuses["energy_recovery_boost"]
        house.happiness_boost = bonuses["happiness_boost"]
        house.hunger_reduction = bonuses["hunger_reduction"]
        house.luck_boost = bonuses["luck_boost"]
        await self.session.flush()
        
        return bonuses
    
    # === УПРАВЛЕНИЕ ДОМОМ ===
    
    async def upgrade_house(self, pet_id: int) -> Dict[str, Any]:
        """Улучшить дом до следующего уровня"""
        result = await self.ensure_house(pet_id)
        if not result["success"]:
            return {"success": False, "message": "Дом не найден"}
        
        house = result["house"]
        upgrade_costs = self.house_data.get("upgrade_costs", {})
        next_level = house.level + 1
        
        cost_key = f"level_{next_level}"
        if cost_key not in upgrade_costs:
            return {"success": False, "message": "Дом уже максимального уровня"}
        
        cost = upgrade_costs[cost_key]
        
        # Проверяем баланс
        pet = await self.pet_repo.get_by_id(pet_id)
        if not pet:
            return {"success": False, "message": "Питомец не найден"}
        
        user = await self.user_repo.get_by_id(pet.user_id)
        if not user:
            return {"success": False, "message": "Пользователь не найден"}
        
        if user.coins < cost:
            return {
                "success": False,
                "message": f"Недостаточно монет! Нужно: {cost} 🪙",
                "need": cost,
                "have": user.coins
            }
        
        # Списываем монеты
        user.coins -= cost
        
        # Повышаем уровень
        old_level = house.level
        await self.house_repo.upgrade_level(house, next_level)
        
        # Разблокируем новые комнаты, если есть
        rooms_data = self.house_data.get("rooms", {})
        for room_type, room_info in rooms_data.items():
            unlock_level = room_info.get("unlock_level", 999)
            if unlock_level <= next_level:
                existing = await self.house_repo.get_room(house.id, room_type)
                if not existing:
                    await self.house_repo.create_room(house.id, room_type, True)
                elif not existing.is_unlocked:
                    await self.house_repo.unlock_room(existing)
        
        # Логируем улучшение
        await self.house_repo.add_upgrade_log(
            house.id,
            "level",
            str(old_level),
            str(next_level),
            cost
        )
        
        # Пересчитываем бонусы
        rooms = await self.house_repo.get_rooms(house.id)
        await self._calculate_house_bonuses(house, rooms)
        
        await self.session.flush()
        
        logger.info(f"Дом питомца {pet_id} улучшен до уровня {next_level}")
        
        return {
            "success": True,
            "message": f"🏠 Дом улучшен до уровня {next_level}!\n💰 Потрачено: {cost} 🪙",
            "new_level": next_level,
            "balance": user.coins
        }
    
    async def upgrade_house_template(self, pet_id: int, template_id: str) -> Dict[str, Any]:
        """Улучшить шаблон дома"""
        result = await self.ensure_house(pet_id)
        if not result["success"]:
            return {"success": False, "message": "Дом не найден"}
        
        house = result["house"]
        templates = self.house_data.get("house_templates", {})
        
        if template_id not in templates:
            return {"success": False, "message": "Шаблон не найден"}
        
        current_template = templates.get(house.template_id, {})
        new_template = templates.get(template_id, {})
        
        # Проверяем, что новый шаблон лучше
        template_keys = list(templates.keys())
        current_level = template_keys.index(house.template_id)
        new_level = template_keys.index(template_id)
        
        if new_level <= current_level:
            return {"success": False, "message": "Этот шаблон уже доступен или хуже текущего"}
        
        cost = new_template.get("cost", 0)
        
        pet = await self.pet_repo.get_by_id(pet_id)
        if not pet:
            return {"success": False, "message": "Питомец не найден"}
        
        user = await self.user_repo.get_by_id(pet.user_id)
        if not user:
            return {"success": False, "message": "Пользователь не найден"}
        
        if user.coins < cost:
            return {
                "success": False,
                "message": f"Недостаточно монет! Нужно: {cost} 🪙",
                "need": cost,
                "have": user.coins
            }
        
        user.coins -= cost
        old_template = house.template_id
        house.template_id = template_id
        
        # Добавляем новые комнаты
        rooms_data = self.house_data.get("rooms", {})
        new_rooms = new_template.get("rooms", [])
        for room_type in new_rooms:
            existing = await self.house_repo.get_room(house.id, room_type)
            if not existing:
                room_info = rooms_data.get(room_type, {})
                unlock_level = room_info.get("unlock_level", 1)
                await self.house_repo.create_room(house.id, room_type, unlock_level <= house.level)
        
        # Логируем
        await self.house_repo.add_upgrade_log(
            house.id,
            "template",
            old_template,
            template_id,
            0,
            cost
        )
        
        # Пересчитываем бонусы
        rooms = await self.house_repo.get_rooms(house.id)
        await self._calculate_house_bonuses(house, rooms)
        
        await self.session.flush()
        
        return {
            "success": True,
            "message": f"🏠 Шаблон обновлён!\n{new_template.get('emoji', '🏠')} {new_template.get('name', '')}\n💰 Потрачено: {cost} 🪙",
            "new_template": template_id,
            "balance": user.coins
        }
    
    # === МЕБЕЛЬ ===
    
    async def _validate_furniture_purchase(
        self,
        pet_id: int,
        furniture_id: str,
        room_type: str
    ) -> Dict[str, Any]:
        """
        Проверить, можно ли купить мебель
        
        Returns:
            {"valid": bool, "message": str, "room": HouseRoom, "furniture": dict, "user": User, "pet": Pet}
        """
        # Проверяем дом
        result = await self.ensure_house(pet_id)
        if not result["success"]:
            return {"valid": False, "message": "Дом не найден"}
        
        house = result["house"]
        
        # Проверяем мебель
        furniture_dict = self.furniture_data.get("furniture", {})
        furniture = furniture_dict.get(furniture_id)
        if not furniture:
            logger.warning(f"[buy_furniture] Мебель не найдена: furniture_id='{furniture_id}'")
            return {"valid": False, "message": "Мебель не найдена"}
        
        logger.info(f"[buy_furniture] Мебель найдена: {furniture_id} -> {furniture.get('name', 'Без имени')}")
        
        # Проверяем комнату
        room = await self.house_repo.get_room(house.id, room_type)
        if not room:
            logger.warning(f"[buy_furniture] Комната не найдена: house_id={house.id}, room_type='{room_type}'")
            return {"valid": False, "message": "Комната не найдена"}
        
        if not room.is_unlocked:
            logger.warning(f"[buy_furniture] Комната заблокирована: room_type='{room.room_type}'")
            return {"valid": False, "message": "Комната не разблокирована"}
        
        # Проверяем, подходит ли мебель для комнаты
        furniture_category = furniture.get("category", "")
        if furniture_category != room_type:
            logger.warning(f"[buy_furniture] Несоответствие категории: furniture_category='{furniture_category}', room_type='{room_type}'")
            return {
                "valid": False,
                "message": f"Эта мебель не подходит для комнаты '{room_type}'",
                "category": furniture_category,
                "room_type": room_type
            }
        
        # Проверяем баланс
        pet = await self.pet_repo.get_by_id(pet_id)
        if not pet:
            return {"valid": False, "message": "Питомец не найден"}
        
        user = await self.user_repo.get_by_id(pet.user_id)
        if not user:
            return {"valid": False, "message": "Пользователь не найден"}
        
        price_coins = furniture.get("price_coins", 0)
        price_premium = furniture.get("price_premium", 0)
        
        if price_coins > 0 and user.coins < price_coins:
            return {
                "valid": False,
                "message": f"Недостаточно монет! Нужно: {price_coins} 🪙",
                "need": price_coins,
                "have": user.coins
            }
        
        if price_premium > 0 and user.premium_currency < price_premium:
            return {
                "valid": False,
                "message": f"Недостаточно лапок! Нужно: {price_premium} 🐾",
                "need": price_premium,
                "have": user.premium_currency
            }
        
        return {
            "valid": True,
            "house": house,
            "room": room,
            "furniture": furniture,
            "user": user,
            "pet": pet,
            "price_coins": price_coins,
            "price_premium": price_premium
        }
    
    async def _apply_furniture_purchase(
        self,
        house,
        room,
        furniture_id: str,
        furniture: dict,
        user,
        price_coins: int,
        price_premium: int
    ) -> Dict[str, Any]:
        """Применить покупку мебели"""
        # Списываем средства
        user.coins -= price_coins
        user.premium_currency -= price_premium
        
        # Добавляем мебель
        bonuses = furniture.get("bonuses", {})
        await self.house_repo.add_furniture(room.id, furniture_id, bonuses)
        
        # Логируем
        await self.house_repo.add_upgrade_log(
            house.id,
            "furniture",
            "",
            furniture_id,
            price_coins,
            price_premium
        )
        
        # Пересчитываем бонусы
        rooms = await self.house_repo.get_rooms(house.id)
        await self._calculate_house_bonuses(house, rooms)
        
        await self.session.flush()
        
        logger.info(f"[buy_furniture] Успешно добавлена мебель: furniture_id='{furniture_id}', room_type='{room.room_type}', pet_id={house.pet_id}")
        
        return {
            "success": True,
            "message": f"{furniture.get('emoji', '🪑')} {furniture.get('name', '')} добавлен в {room.room_type}!",
            "furniture": furniture_id,
            "room": room.room_type,
            "balance_coins": user.coins,
            "balance_premium": user.premium_currency
        }
    
    async def buy_furniture(self, pet_id: int, furniture_id: str, room_type: str) -> Dict[str, Any]:
        """Купить мебель и разместить в комнате"""
        # 1. Валидация
        validation = await self._validate_furniture_purchase(pet_id, furniture_id, room_type)
        if not validation.get("valid"):
            return {"success": False, "message": validation.get("message", "Ошибка валидации")}
        
        # 2. Применяем покупку
        result = await self._apply_furniture_purchase(
            house=validation["house"],
            room=validation["room"],
            furniture_id=furniture_id,
            furniture=validation["furniture"],
            user=validation["user"],
            price_coins=validation["price_coins"],
            price_premium=validation["price_premium"]
        )
        
        return result
    
    async def remove_furniture(self, pet_id: int, furniture_id: str, room_type: str) -> Dict[str, Any]:
        """Удалить мебель из комнаты"""
        result = await self.ensure_house(pet_id)
        if not result["success"]:
            return {"success": False, "message": "Дом не найден"}
        
        house = result["house"]
        
        room = await self.house_repo.get_room(house.id, room_type)
        if not room:
            return {"success": False, "message": "Комната не найдена"}
        
        success = await self.house_repo.remove_furniture(room.id, furniture_id)
        if not success:
            return {"success": False, "message": "Мебель не найдена"}
        
        # Пересчитываем бонусы
        rooms = await self.house_repo.get_rooms(house.id)
        await self._calculate_house_bonuses(house, rooms)
        
        await self.session.flush()
        
        return {
            "success": True,
            "message": f"🗑️ Мебель удалена",
            "furniture": furniture_id,
            "room": room_type
        }
    
    # === ПОСЕЩЕНИЕ ===
    
    async def visit_house(self, visitor_pet_id: int, target_pet_id: int) -> Dict[str, Any]:
        """Посетить дом другого питомца"""
        if visitor_pet_id == target_pet_id:
            return {"success": False, "message": "Нельзя посетить свой дом"}
        
        house = await self.house_repo.get_by_pet_id(target_pet_id)
        if not house:
            return {"success": False, "message": "У питомца нет дома"}
        
        has_visited = await self.house_repo.has_visited_today(house.id, visitor_pet_id)
        if has_visited:
            return {"success": False, "message": "Вы уже посещали этот дом сегодня"}
        
        house_info = await self.get_house_info(target_pet_id)
        if not house_info["success"]:
            return {"success": False, "message": "Не удалось получить информацию о доме"}
        
        visit_reward = self.house_data.get("visit_reward", {})
        reward_coins = visit_reward.get("coins", 10)
        reward_happiness = visit_reward.get("happiness_boost", 2)
        
        visitor = await self.pet_repo.get_by_id(visitor_pet_id)
        if visitor:
            visitor.happiness = min(100, visitor.happiness + reward_happiness)
            await self.session.flush()
        
        user = await self.user_repo.get_by_id(visitor.user_id) if visitor else None
        if user:
            user.coins += reward_coins
            await self.session.flush()
        
        await self.house_repo.add_visit(
            house.id,
            visitor_pet_id,
            reward_coins,
            reward_happiness
        )
        
        house.total_visitors += 1
        await self.session.flush()
        
        return {
            "success": True,
            "message": f"""🏠 Вы посетили дом!

{house_info['house']['template_emoji']} {house_info['house']['template_name']}
📊 Уровень: {house_info['house']['level']}

🎁 Награда:
🪙 +{reward_coins} монет
😊 +{reward_happiness} счастья

💡 Заходите завтра снова!""",
            "rewards": {
                "coins": reward_coins,
                "happiness": reward_happiness
            }
        }
    
    # === ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ===
    
    async def get_available_templates(self, pet_id: int) -> List[Dict[str, Any]]:
        """Получить список доступных шаблонов для дома"""
        result = await self.ensure_house(pet_id)
        if not result["success"]:
            return []
        
        house = result["house"]
        templates = self.house_data.get("house_templates", {})
        
        available = []
        template_keys = list(templates.keys())
        current_index = template_keys.index(house.template_id)
        
        for i, (key, template) in enumerate(templates.items()):
            if i > current_index:
                available.append({
                    "id": key,
                    "name": template.get("name", key),
                    "emoji": template.get("emoji", "🏠"),
                    "description": template.get("description", ""),
                    "cost": template.get("cost", 0),
                    "bonuses": template.get("bonuses", {}),
                    "is_locked": i > current_index + 1
                })
        
        return available
    
    async def get_available_furniture(self, room_type: str) -> List[Dict[str, Any]]:
        """Получить список мебели для комнаты"""
        furniture_dict = self.furniture_data.get("furniture", {})
        
        available = []
        for key, item in furniture_dict.items():
            if item.get("category") == room_type:
                available.append({
                    "id": key,
                    "name": item.get("name", key),
                    "emoji": item.get("emoji", "📦"),
                    "description": item.get("description", ""),
                    "price_coins": item.get("price_coins", 0),
                    "price_premium": item.get("price_premium", 0),
                    "bonuses": item.get("bonuses", {}),
                    "rarity": item.get("rarity", "common")
                })
        
        return available
    
    async def get_house_bonuses_for_pet(self, pet_id: int) -> Dict[str, int]:
        """Получить бонусы дома для применения к питомцу"""
        house = await self.house_repo.get_by_pet_id(pet_id)
        if not house:
            return {
                "energy_recovery_boost": 0,
                "happiness_boost": 0,
                "hunger_reduction": 0,
                "luck_boost": 0
            }
        
        return {
            "energy_recovery_boost": house.energy_recovery_boost,
            "happiness_boost": house.happiness_boost,
            "hunger_reduction": house.hunger_reduction,
            "luck_boost": house.luck_boost
        }
    
    # === ЕЖЕДНЕВНЫЙ БОНУС ДОМА ===
    
    async def can_claim_daily_bonus(self, pet_id: int) -> bool:
        """Проверить, можно ли получить бонус дома сегодня"""
        pet = await self.pet_repo.get_by_id(pet_id)
        if not pet:
            return False
        if not pet.last_house_bonus:
            return True
        today = datetime.utcnow().date()
        return pet.last_house_bonus.date() != today
    
    async def claim_daily_bonus(self, pet_id: int, user_id: int) -> Dict[str, Any]:
        """Получить ежедневный бонус дома"""
        pet = await self.pet_repo.get_by_id(pet_id)
        if not pet:
            return {"success": False, "message": "Питомец не найден"}
        
        if not await self.can_claim_daily_bonus(pet_id):
            return {"success": False, "message": "Бонус уже получен сегодня! Возвращайся завтра ⏳"}
        
        house = await self.house_repo.get_by_pet_id(pet_id)
        if not house:
            return {"success": False, "message": "У тебя нет дома!"}
        
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "message": "Пользователь не найден"}
        
        # Рассчитываем бонус
        bonus_coins = 5 * house.level
        bonus_happiness = 1 * house.level
        bonus_energy = 2 * house.level
        
        # Бонус за шаблон
        if house.template_id == "cozy":
            bonus_coins += 5
        elif house.template_id == "luxury":
            bonus_coins += 15
        elif house.template_id == "mansion":
            bonus_coins += 30
        
        # Начисляем
        user.coins += bonus_coins
        pet.happiness = min(100, pet.happiness + bonus_happiness)
        pet.energy = min(100, pet.energy + bonus_energy)
        pet.last_house_bonus = datetime.utcnow()
        
        await self.session.flush()
        
        logger.info(f"🏠 Бонус дома получен: pet={pet_id}, coins={bonus_coins}, happiness={bonus_happiness}, energy={bonus_energy}")
        
        return {
            "success": True,
            "message": f"🎁 Бонус дома получен!\n🪙 +{bonus_coins} монет\n😊 +{bonus_happiness} счастья\n⚡ +{bonus_energy} энергии",
            "coins": bonus_coins,
            "happiness": bonus_happiness,
            "energy": bonus_energy
        }