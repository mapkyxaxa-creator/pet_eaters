import logging
import random
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories.pet_repository import PetRepository
from database.repositories.user_repository import UserRepository
from database.repositories.inventory_repository import InventoryRepository
from database.repositories.adventure_repository import AdventureRepository
from database.models import AdventureHistory, Pet
from services.data_loader import data_loader
from services.quest_service import QuestService
from services.story_service import StoryService
from services.chat_service import ChatService

logger = logging.getLogger(__name__)


class AdventureService:
    """Сервис для работы с приключениями"""
    
    def __init__(self, session: AsyncSession, level_service, achievement_service):
        self.session = session
        self.pet_repo = PetRepository(session)
        self.user_repo = UserRepository(session)
        self.inventory_repo = InventoryRepository(session)
        self.adventure_repo = AdventureRepository(session)
        self.level_service = level_service
        self.achievement_service = achievement_service
        self.quest_service = QuestService(session)
        self.balance = data_loader.get_balance()
        self.locations = data_loader.get("locations", {})
        self.events = data_loader.get("events", {})
        self.foods = data_loader.get("foods", {})
    
    async def get_available_locations(self, pet_level: int) -> Dict[str, Any]:
        """Получение доступных локаций для уровня питомца"""
        available = {}
        for loc_id, loc_data in self.locations.items():
            min_level = loc_data.get("min_level", 0)
            if pet_level >= min_level:
                available[loc_id] = loc_data
        return available
    
    async def start_adventure(
        self,
        user_id: int,
        pet_id: int,
        location_id: str
    ) -> Dict[str, Any]:
        """
        Начало приключения
        
        Returns:
            {
                "success": bool,
                "message": str,
                "adventure_id": int,
                "duration": int,
                "energy_cost": int,
                "location_name": str,
                "cooldown_until": datetime
            }
        """
        # Проверяем пользователя
        user = await self.user_repo.get_by_telegram_id(user_id)
        if not user:
            return {"success": False, "message": "Пользователь не найден"}
        
        # Проверяем питомца
        pet = await self.pet_repo.get_by_id(pet_id)
        if not pet:
            return {"success": False, "message": "Питомец не найден"}
        
        # Проверяем локацию
        location = self.locations.get(location_id)
        if not location:
            return {"success": False, "message": "Локация не найдена"}
        
        # Проверяем уровень
        min_level = location.get("min_level", 0)
        if pet.level < min_level:
            return {
                "success": False,
                "message": f"Для этой локации нужен уровень {min_level}. Твой уровень: {pet.level}"
            }
        
        # Проверяем кулдаун
        cooldown = await self.adventure_repo.get_cooldown(pet_id, location_id)
        if cooldown and cooldown.cooldown_until > datetime.utcnow():
            remaining = cooldown.cooldown_until - datetime.utcnow()
            minutes = int(remaining.total_seconds() / 60)
            return {
                "success": False,
                "message": f"⏳ Подожди {minutes} минут до следующего приключения в {location.get('name', '')}"
            }
        
        # Проверяем энергию
        energy_cost = location.get("energy_cost", 10)
        if pet.energy < energy_cost:
            return {
                "success": False,
                "message": f"Недостаточно энергии! Нужно {energy_cost}, у тебя {pet.energy}"
            }
        
        # Тратим энергию
        logger.info(f"⚡ ТРАТА ЭНЕРГИИ: pet_id={pet_id}, energy_before={pet.energy + energy_cost}, energy_cost={energy_cost}, energy_after={pet.energy}")
        pet.energy -= energy_cost
        
        # ===== БОНУС НЕПОСЕДЫ (-15% времени) =====
        duration = location.get("duration", 300)
        characters = data_loader.get("characters", {})
        character = characters.get(pet.character_id, {})
        bonus = character.get("bonus", {})
        if "duration" in bonus:
            old_duration = duration
            duration = int(duration * bonus["duration"])
            logger.info(f"⚡ Применён бонус Непоседы к длительности: {old_duration} → {duration} (x{bonus['duration']})")
        
        logger.info(f"📝 СОЗДАНИЕ ЗАПИСИ ПРИКЛЮЧЕНИЯ: pet_id={pet_id}, location_id={location_id}, duration={duration}")
        adventure = AdventureHistory(
            pet_id=pet_id,
            location_id=location_id,
            started_at=datetime.utcnow(),
            duration=duration
        )
        self.session.add(adventure)
        await self.session.flush()
        logger.info(f"💾 FLUSH ВЫПОЛНЕН: adventure_id={adventure.id}, pet_id={pet_id}")
        
        # Обновляем кулдаун
        cooldown_until = datetime.utcnow() + timedelta(seconds=location.get("cooldown", 0))
        await self.adventure_repo.set_cooldown(pet_id, location_id, cooldown_until)
        
        await self.session.commit()
        logger.info(f"✅ ПРИКЛЮЧЕНИЕ УСПЕШНО СОХРАНЕНО: adventure_id={adventure.id}")
        
        return {
            "success": True,
            "message": f"🚀 {location.get('emoji', '')} Отправляемся в {location.get('name', '')}!",
            "adventure_id": adventure.id,
            "duration": duration,
            "energy_cost": energy_cost,
            "location_name": location.get('name', ''),
            "cooldown_until": cooldown_until
        }
    
    async def complete_adventure(self, adventure_id: int) -> Dict[str, Any]:
        """
        Завершить приключение по ID
        
        Args:
            adventure_id: ID приключения
            
        Returns:
            Dict с результатом приключения
        """
        adventure = await self.adventure_repo.get_adventure_by_id(adventure_id)
        if not adventure:
            return {"success": False, "message": "Приключение не найдено"}
        
        # Проверяем, не завершено ли уже
        if adventure.completed_at is not None:
            return {"success": False, "message": "Приключение уже завершено"}
        
        return await self._complete_adventure(adventure)
    
    async def complete_pending_adventure(self, pet_id: int) -> Dict[str, Any]:
        """Завершить ожидающее приключение"""
        adventure = await self.adventure_repo.get_pending_adventure(pet_id)
        if not adventure:
            return {"success": False, "message": "Нет активных приключений"}
        
        # Проверяем, завершилось ли приключение по времени
        if adventure.completed_at > datetime.utcnow():
            remaining = adventure.completed_at - datetime.utcnow()
            minutes = int(remaining.total_seconds() / 60)
            seconds = int(remaining.total_seconds() % 60)
            return {
                "success": False,
                "message": f"⏳ Приключение еще не завершено! Осталось {minutes}м {seconds}с"
            }
        
        return await self._complete_adventure(adventure)
    
    async def _complete_adventure(self, adventure: AdventureHistory) -> Dict[str, Any]:
        """Завершение приключения и выдача награды"""
        pet = await self.pet_repo.get_by_id(adventure.pet_id)
        if not pet:
            return {"success": False, "message": "Питомец не найден"}
        
        # Получаем локацию
        location = self.locations.get(adventure.location_id, {})
        location_name = location.get("name", adventure.location_id)
        location_emoji = location.get("emoji", "")
        
        # Выбираем событие (с учётом бонуса Хулигана)
        event_result = self._get_event(adventure.location_id, pet)
        
        # ЛОГИРОВАНИЕ СОБЫТИЯ
        logger.info(f"🔍 [ADVENTURE DEBUG] Получено событие для локации {adventure.location_id}: {event_result}")
        
        # Обрабатываем награду
        reward_text = ""
        xp_gained = 0
        coins_gained = 0
        item_gained = None
        event_type = "reward"
        event_id = None
        event_text = "🌿 Простая прогулка. Ничего особенного не случилось."
        
        # Сохраняем user_id для обновления заданий
        user_id = None
        
        # Получаем бонус характера для монет и XP
        characters = data_loader.get("characters", {})
        character = characters.get(pet.character_id, {})
        bonus = character.get("bonus", {})
        coins_bonus = bonus.get("coins", 1.0)  # Барин: 1.1
        xp_bonus = bonus.get("xp", 1.0)       # для будущих бонусов
        
        if event_result:
            logger.info(f"🔍 [ADVENTURE DEBUG] Начинаем обработку события: id={event_result.get('id')}, type={event_result.get('type')}")
            event = event_result
            event_id = event.get("id")
            event_text = event.get("text", "")
            event_type = event.get("type", "reward")
            reward = event.get("reward", "")
            
            if event_type == "food":
                # Награда едой
                if isinstance(reward, dict):
                    item_id = reward.get("item", "")
                    quantity = reward.get("amount", 1)
                else:
                    item_id = reward
                    quantity = 1
                    if isinstance(reward, str) and "×" in reward:
                        parts = reward.split("×")
                        item_id = parts[0].strip()
                        quantity = int(parts[1].strip())
                
                logger.info(f"🔍 [ADVENTURE DEBUG] food награда: item_id={item_id}, quantity={quantity}, reward_raw={reward}")
                
                user = await self.user_repo.get_by_id(pet.user_id)
                if user:
                    user_id = user.telegram_id
                    logger.info(f"📦 ДОБАВЛЕНИЕ В ИНВЕНТАРЬ: user_id={user.id}, item_id={item_id}, quantity={quantity}")
                    await self.inventory_repo.add_item(user.id, item_id, quantity)
                    item_gained = {"id": item_id, "quantity": quantity}
                    logger.info(f"✅ ПРЕДМЕТ ДОБАВЛЕН В ИНВЕНТАРЬ: user_id={user.id}, item_id={item_id}, quantity={quantity}")
                
                # ===== ПРОВЕРКА: если это golden_ticket — НЕ ДАЁМ XP =====
                food_data = self.foods.get(item_id, {})
                if item_id == "golden_ticket":
                    xp_gained = 0
                    logger.info(f"🎫 ЗОЛОТОЙ БИЛЕТ: XP не начисляется (специальный предмет)")
                else:
                    xp_gained = food_data.get("experience", 15)
                    
                    # Применяем бонус XP
                    if xp_bonus > 1.0:
                        old_xp = xp_gained
                        xp_gained = int(xp_gained * xp_bonus)
                        logger.info(f"⭐ Применён бонус XP: {old_xp} → {xp_gained}")
                
                logger.info(f"🔍 [ADVENTURE DEBUG] food XP: item_id={item_id}, xp_gained={xp_gained}, food_data={food_data}")
                
                # Проверяем редкость еды (только если это реальная еда)
                rarity = food_data.get("rarity", "common")
                if rarity == "legendary" and item_id != "golden_ticket":
                    pet.found_legendary += 1
                    logger.info(f"🌟 ЛЕГЕНДАРНАЯ ЕДА НАЙДЕНА! pet_id={pet.id}, item_id={item_id}")
                    try:
                        food_name = food_data.get('name', item_id)
                        food_emoji = food_data.get('emoji', '🍖')
                        chat_service = ChatService(self.session)
                        message = f"{food_emoji} Я НАШЁЛ {food_name}! 🔥"
                        await chat_service.add_event(
                            pet=pet,
                            event_type="legendary_found",
                            message=message,
                            data={"food_id": item_id, "food_name": food_name}
                        )
                        logger.info(f"✅ СООБЩЕНИЕ В ЧАТ ДОБАВЛЕНО (legendary): pet_id={pet.id}")
                    except Exception as e:
                        logger.error(f"❌ Ошибка добавления в чат: {e}")
                elif rarity == "epic" and item_id != "golden_ticket":
                    try:
                        food_name = food_data.get('name', item_id)
                        food_emoji = food_data.get('emoji', '🍖')
                        chat_service = ChatService(self.session)
                        message = f"{food_emoji} Я нашёл {food_name}! 🟣"
                        await chat_service.add_event(
                            pet=pet,
                            event_type="epic_found",
                            message=message,
                            data={"food_id": item_id, "food_name": food_name}
                        )
                        logger.info(f"✅ СООБЩЕНИЕ В ЧАТ ДОБАВЛЕНО (epic): pet_id={pet.id}")
                    except Exception as e:
                        logger.error(f"❌ Ошибка добавления в чат: {e}")
                
                reward_text = f"🍽️ Найдена еда: {food_data.get('emoji', '')} {food_data.get('name', item_id)} x{quantity}"
            
            elif event_type == "rich":
                logger.info(f"🔍 [ADVENTURE DEBUG] Обработка события rich: {event}")
                
                reward_data = event.get("reward", {})
                coins_gained = reward_data.get("coins", 50) if isinstance(reward_data, dict) else event.get("reward_coins", 50)
                xp_gained = event.get("reward_xp", 30)
                happiness_gained = event.get("reward_happiness", 5)
                item_id = reward_data.get("item", None) if isinstance(reward_data, dict) else event.get("reward_item", None)
                
                # Применяем бонус к монетам (Барин)
                if coins_bonus > 1.0:
                    old_coins = coins_gained
                    coins_gained = int(coins_gained * coins_bonus)
                    logger.info(f"💰 Применён бонус к монетам: {old_coins} → {coins_gained}")
                
                # Применяем бонус XP
                if xp_bonus > 1.0:
                    old_xp = xp_gained
                    xp_gained = int(xp_gained * xp_bonus)
                    logger.info(f"⭐ Применён бонус XP: {old_xp} → {xp_gained}")
                
                logger.info(f"🔍 [ADVENTURE DEBUG] rich награды: coins={coins_gained}, xp={xp_gained}, happiness={happiness_gained}, item={item_id}")
                quantity = 1
                
                user = await self.user_repo.get_by_id(pet.user_id)
                if user:
                    user_id = user.telegram_id
                    logger.info(f"💰 НАГРАДА RICH: user_id={user.id}, coins_gained={coins_gained}, total_coins={user.coins + coins_gained}")
                    user.coins += coins_gained
                    if item_id:
                        logger.info(f"📦 ДОБАВЛЕНИЕ ПРЕДМЕТА ОТ RICH: user_id={user.id}, item_id={item_id}, quantity={quantity}")
                        await self.inventory_repo.add_item(user.id, item_id, quantity)
                        item_gained = {"id": item_id, "quantity": quantity}
                
                old_happiness = pet.happiness
                pet.happiness = min(100, pet.happiness + happiness_gained)
                logger.info(f"❤️ ИЗМЕНЕНИЕ СЧАСТЬЯ: pet_id={pet.id}, old_happiness={old_happiness}, gained={happiness_gained}, new_happiness={pet.happiness}")
                
                reward_text = f"👤 <b>Рич появился!</b>\n\n{event_text}\n\n🎁 Награда: {coins_gained} монет, {xp_gained} XP, +{happiness_gained} счастья"
                if item_id:
                    reward_text += f", {item_id} x{quantity}"
                
                try:
                    story_service = StoryService(self.session)
                    next_chapter = story_service.get_next_chapter(pet)
                    if next_chapter and next_chapter.get("location") == adventure.location_id:
                        reward_text += f"\n\n💡 Рич: \"Кстати, я слышал, что в {next_chapter.get('name')} есть что-то интересное...\""
                except Exception as e:
                    logger.error(f"Ошибка при проверке сюжета для Рича: {e}")
            
            elif event_type == "reward":
                logger.info(f"🔍 [ADVENTURE DEBUG] Обработка события reward: reward={reward}")
                
                if isinstance(reward, dict):
                    if reward.get("type") == "happiness":
                        amount = reward.get("amount", 5)
                        old_happiness = pet.happiness
                        pet.happiness = min(pet.happiness + amount, 100)
                        logger.info(f"❤️ НАГРАДА СЧАСТЬЕМ: pet_id={pet.id}, old_happiness={old_happiness}, gained={amount}, new_happiness={pet.happiness}")
                        reward_text = f"❤️ Счастье +{amount}"
                        xp_gained = 15
                    elif reward.get("item"):
                        item_id = reward.get("item")
                        quantity = reward.get("amount", 1)
                        user = await self.user_repo.get_by_id(pet.user_id)
                        if user:
                            user_id = user.telegram_id
                            await self.inventory_repo.add_item(user.id, item_id, quantity)
                            item_gained = {"id": item_id, "quantity": quantity}
                        reward_text = f"🎁 Получен {item_id} x{quantity}"
                        xp_gained = 15
                    else:
                        coins_gained = reward.get("amount", 10)
                        if coins_bonus > 1.0:
                            old_coins = coins_gained
                            coins_gained = int(coins_gained * coins_bonus)
                            logger.info(f"💰 Применён бонус к монетам: {old_coins} → {coins_gained}")
                        user = await self.user_repo.get_by_id(pet.user_id)
                        if user:
                            user_id = user.telegram_id
                            user.coins += coins_gained
                        reward_text = f"💰 Получено {coins_gained} монет"
                        xp_gained = max(5, min(20, coins_gained // 5))
                elif isinstance(reward, str):
                    if "happiness" in reward:
                        try:
                            amount = int(reward.split("_")[0])
                            old_happiness = pet.happiness
                            pet.happiness = min(pet.happiness + amount, 100)
                            logger.info(f"❤️ НАГРАДА СЧАСТЬЕМ: pet_id={pet.id}, old_happiness={old_happiness}, gained={amount}, new_happiness={pet.happiness}")
                            reward_text = f"❤️ Счастье +{amount}"
                            xp_gained = 15
                        except (ValueError, IndexError):
                            coins_gained = int(reward) if reward.isdigit() else 10
                            if coins_bonus > 1.0:
                                coins_gained = int(coins_gained * coins_bonus)
                            user = await self.user_repo.get_by_id(pet.user_id)
                            if user:
                                user_id = user.telegram_id
                                user.coins += coins_gained
                            reward_text = f"💰 Получено {coins_gained} монет"
                            xp_gained = 10
                    else:
                        try:
                            coins_gained = int(reward)
                            if coins_bonus > 1.0:
                                old_coins = coins_gained
                                coins_gained = int(coins_gained * coins_bonus)
                                logger.info(f"💰 Применён бонус к монетам: {old_coins} → {coins_gained}")
                            user = await self.user_repo.get_by_id(pet.user_id)
                            if user:
                                user_id = user.telegram_id
                                user.coins += coins_gained
                            reward_text = f"💰 Получено {coins_gained} монет"
                            xp_gained = max(5, min(20, coins_gained // 5))
                        except ValueError:
                            item_id = reward
                            quantity = 1
                            user = await self.user_repo.get_by_id(pet.user_id)
                            if user:
                                user_id = user.telegram_id
                                await self.inventory_repo.add_item(user.id, item_id, quantity)
                                item_gained = {"id": item_id, "quantity": quantity}
                            reward_text = f"🎁 Получен {item_id}"
                            xp_gained = 15
                else:
                    coins_gained = 10
                    if coins_bonus > 1.0:
                        coins_gained = int(coins_gained * coins_bonus)
                    user = await self.user_repo.get_by_id(pet.user_id)
                    if user:
                        user_id = user.telegram_id
                        user.coins += coins_gained
                    reward_text = f"💰 Получено {coins_gained} монет"
                    xp_gained = 10
            
            elif event_type == "penalty":
                logger.info(f"🔍 [ADVENTURE DEBUG] Обработка события penalty: reward={reward}")
                
                if isinstance(reward, dict):
                    amount = reward.get("amount", 10)
                else:
                    amount = int(reward) if str(reward).lstrip('-').isdigit() else 10
                    if not str(reward).startswith("-"):
                        amount = -amount
                
                coins_gained = amount
                xp_gained = 5
                user = await self.user_repo.get_by_id(pet.user_id)
                if user:
                    user_id = user.telegram_id
                    old_coins = user.coins
                    user.coins = max(0, user.coins + amount)
                    logger.info(f"💔 ШТРАФ МОНЕТАМИ: user_id={user.id}, old_coins={old_coins}, penalty={abs(amount)}, new_coins={user.coins}")
                reward_text = f"💔 Потеряно {abs(amount)} монет"
            
            event_text = f"{event_text}\n\n{reward_text}"
        else:
            # Событие не выбралось - даем минимальную награду
            logger.info(f"🔍 [ADVENTURE DEBUG] Нет события, выдаем минимальную награду")
            xp_gained = 5
            coins_gained = 10
            if coins_bonus > 1.0:
                coins_gained = int(coins_gained * coins_bonus)
            user = await self.user_repo.get_by_id(pet.user_id)
            if user:
                user_id = user.telegram_id
                user.coins += coins_gained
                logger.info(f"💰 МИНИМАЛЬНАЯ НАГРАДА: user_id={user.id}, coins_gained={coins_gained}, total_coins={user.coins + coins_gained}")
            reward_text = f"💰 Нашёл {coins_gained} монет"
            event_text = f"🌿 Простая прогулка. {reward_text}"
            logger.info(f"🔍 [ADVENTURE DEBUG] Минимальная награда установлена: xp={xp_gained}, coins={coins_gained}")
        
        # Начисляем XP
        if xp_gained > 0:
            leveled_up, _ = await self.level_service.add_experience(pet, xp_gained)
            if leveled_up:
                reward_text += "\n🎉 <b>НОВЫЙ УРОВЕНЬ!</b>"
        
        # Обновляем статистику питомца
        pet.total_adventures += 1
        
        # ===== ЛОГИРОВАНИЕ НАГРАД =====
        logger.info(f"[ADVENTURE COMPLETE] pet_id={pet.id}, location={adventure.location_id}")
        logger.info(f"  → XP gained: {xp_gained}")
        logger.info(f"  → Coins gained: {coins_gained}")
        logger.info(f"  → Item gained: {item_gained}")
        logger.info(f"  → Event type: {event_type}")
        logger.info(f"  → Event result: {event_result}")
        
        if xp_gained == 0 and coins_gained == 0 and item_gained is None:
            logger.warning(f"⚠️ [ADVENTURE DEBUG] ВНИМАНИЕ: Нулевые награды! event_result={event_result}, event_type={event_type}")
        
        logger.info(f"🔚 ЗАВЕРШЕНИЕ ПРИКЛЮЧЕНИЯ ЧЕРЕЗ РЕПОЗИТОРИЙ: adventure_id={adventure.id}, xp_gained={xp_gained}, coins_gained={coins_gained}, item={item_gained}")
        
        if event_result and xp_gained == 0 and coins_gained == 0 and item_gained is None:
            logger.warning(f"⚠️ [ADVENTURE DEBUG] КРИТИЧНО: Награды все нулевые, хотя событие есть! event={event_result}")
        
        await self.adventure_repo.complete_adventure(
            adventure_id=adventure.id,
            reward_type=event_type if event_result else "reward",
            reward_amount=coins_gained if coins_gained > 0 else None,
            reward_item_id=item_gained["id"] if item_gained else None,
            event_id=event_id if event_result else None,
            event_text=event_text,
            xp_gained=xp_gained,
            coins_gained=coins_gained
        )
        
        saved_adventure = await self.adventure_repo.get_adventure_by_id(adventure.id)
        if saved_adventure:
            logger.info(f"✅ ПРИКЛЮЧЕНИЕ ЗАВЕРШЕНО В РЕПОЗИТОРИИ: adventure_id={adventure.id}, saved_xp={saved_adventure.xp_gained}, saved_coins={saved_adventure.coins_gained}")
        else:
            logger.error(f"❌ НЕ УДАЛОСЬ ПОЛУЧИТЬ СОХРАНЕННОЕ ПРИКЛЮЧЕНИЕ: adventure_id={adventure.id}")
        
        logger.info(f"💾 ПРИКЛЮЧЕНИЕ СОХРАНЕНО: adventure_id={adventure.id}")
        
        # ===== ОБНОВЛЯЕМ ЕЖЕДНЕВНЫЕ ЗАДАНИЯ =====
        if user_id:
            logger.info(f"📋 ОБНОВЛЕНИЕ КВЕСТОВ: user_id={user_id}")
            await self.quest_service.update_quest_progress(
                user_id=user_id,
                condition_type="adventure_count",
                value=1
            )
            logger.info(f"✅ КВЕСТ ОБНОВЛЕН (adventure_count): user_id={user_id}")
            
            if event_result and event_result.get("reward"):
                reward = event_result.get("reward")
                if isinstance(reward, str) and "×" not in reward:
                    if reward in self.foods:
                        food_data = self.foods.get(reward, {})
                        rarity = food_data.get("rarity", "common")
                        if rarity in ["rare", "epic", "legendary"]:
                            logger.info(f"📋 ОБНОВЛЕНИЕ КВЕСТА (find_rarity): user_id={user_id}, rarity={rarity}")
                            await self.quest_service.update_quest_progress(
                                user_id=user_id,
                                condition_type="find_rarity",
                                value=1,
                                item_id=rarity
                            )
                            logger.info(f"✅ КВЕСТ ОБНОВЛЕН (find_rarity): user_id={user_id}, rarity={rarity}")
                elif isinstance(reward, dict):
                    item_id = reward.get("item", "")
                    if item_id and item_id in self.foods:
                        food_data = self.foods.get(item_id, {})
                        rarity = food_data.get("rarity", "common")
                        if rarity in ["rare", "epic", "legendary"]:
                            logger.info(f"📋 ОБНОВЛЕНИЕ КВЕСТА (find_rarity) из dict: user_id={user_id}, rarity={rarity}")
                            await self.quest_service.update_quest_progress(
                                user_id=user_id,
                                condition_type="find_rarity",
                                value=1,
                                item_id=rarity
                            )
                            logger.info(f"✅ КВЕСТ ОБНОВЛЕН (find_rarity): user_id={user_id}, rarity={rarity}")
        
        # ===== ПРОВЕРЯЕМ ДОСТИЖЕНИЯ =====
        logger.info(f"🏆 ПРОВЕРКА ДОСТИЖЕНИЙ: pet_id={pet.id}")
        unlocked = await self.achievement_service.check_all_achievements(pet.id)
        if unlocked:
            logger.info(f"🎉 НОВЫЕ ДОСТИЖЕНИЯ РАЗБЛОКИРОВАНЫ: pet_id={pet.id}, count={len(unlocked)}")
            for ach in unlocked:
                logger.info(f"  → {ach.get('data', {}).get('name', 'Unknown')}")
        
        # ===== ПРОВЕРЯЕМ СЮЖЕТНУЮ ГЛАВУ =====
        story_result = None
        story_event = None
        try:
            logger.info(f"📖 ПРОВЕРКА СЮЖЕТА: pet_id={pet.id}, location={adventure.location_id}")
            story_service = StoryService(self.session)
            
            story_result = await story_service.check_adventure_completion(pet, adventure.location_id)
            if story_result:
                logger.info(f"✅ СЮЖЕТНАЯ ГЛАВА ЗАВЕРШЕНА: pet_id={pet.id}, chapter={story_result.get('chapter', {}).get('name', 'Unknown')}")
            
            if not story_result:
                npc_chance = story_service.get_npc_appearance_chance(adventure.location_id, pet)
                if random.random() < npc_chance:
                    story_event = story_service.get_story_event_for_location(adventure.location_id, pet)
                    if story_event:
                        logger.info(f"👤 NPC ВСТРЕЧА: pet_id={pet.id}, location={adventure.location_id}")
        except Exception as e:
            logger.error(f"Ошибка при проверке сюжетной главы: {e}")
        
        logger.info(f"💾 ФИНАЛЬНЫЙ COMMIT: adventure_id={adventure.id}, pet_id={pet.id}, все изменения сохраняются")
        await self.session.commit()
        logger.info(f"✅ ВСЕ ДАННЫЕ УСПЕШНО СОХРАНЕНЫ: adventure_id={adventure.id}")
        
        # Формируем сообщение с уведомлениями о достижениях
        message = f"{location_emoji} <b>{location_name}</b>\n\n{event_text}\n\n✨ Опыт: +{xp_gained}"
        
        if unlocked:
            message += "\n\n🏆 <b>НОВЫЕ ДОСТИЖЕНИЯ!</b>\n"
            for ach in unlocked:
                ach_data = ach.get("data", {})
                message += f"{ach_data.get('emoji', '')} {ach_data.get('name', '')}\n"
        
        if story_event:
            message += "\n\n" + story_event
        
        if story_result:
            chapter = story_result.get('chapter', {})
            reward = story_result.get('reward', {})
            message += "\n\n📖 <b>СЮЖЕТНАЯ ГЛАВА ЗАВЕРШЕНА!</b>\n"
            message += f"{chapter.get('emoji', '')} {chapter.get('name', '')}\n"
            description = chapter.get('description', '')
            if description:
                message += f"{description}\n"
            coins_reward = reward.get('coins', 0)
            xp_reward = reward.get('xp', 0)
            title = reward.get('title', '')
            if coins_reward:
                message += f"🪙 +{coins_reward} монет\n"
            if xp_reward:
                message += f"⭐ +{xp_reward} опыта\n"
            if title:
                message += f"🏆 Титул: {title}\n"
        
        return {
            "success": True,
            "message": message,
            "completed": True,
            "xp_gained": xp_gained,
            "coins_gained": coins_gained,
            "item_gained": item_gained,
            "event_text": event_text,
            "unlocked_achievements": unlocked,
            "story_result": story_result
        }
    
    def _get_event(self, location_id: str, pet: Pet) -> Optional[Dict]:
        """Получение случайного события для локации с учётом бонуса Хулигана"""
        events = self.events.get(location_id, [])
        logger.info(f"🔍 [ADVENTURE DEBUG] _get_event: локация {location_id}, найдено событий: {len(events)}")
        
        if not events:
            logger.warning(f"⚠️ [ADVENTURE DEBUG] Нет событий для локации {location_id}")
            return None
        
        # ===== БОНУС ХАРАКТЕРА (Хулиган) =====
        characters = data_loader.get("characters", {})
        character = characters.get(pet.character_id, {})
        bonus = character.get("bonus", {})
        rarity_bonus = bonus.get("rarity", 1.0)
        
        # Взвешенный выбор с учётом бонуса Хулигана
        weighted_events = []
        for event in events:
            weight = event.get("weight", 1)
            # Для событий с едой увеличиваем вес, если редкость выше common
            if event.get("type") == "food" and rarity_bonus > 1.0:
                reward = event.get("reward")
                if isinstance(reward, str) and reward in self.foods:
                    food_data = self.foods.get(reward, {})
                    rarity = food_data.get("rarity", "common")
                    if rarity in ["uncommon", "rare", "epic", "legendary"]:
                        weight = int(weight * rarity_bonus)
                        logger.info(f"🍀 Бонус Хулигана: вес события {event.get('id')} увеличен до {weight}")
            weighted_events.append((event, weight))
        
        total_weight = sum(w for _, w in weighted_events)
        roll = random.random() * total_weight
        
        current = 0
        for event, weight in weighted_events:
            current += weight
            if roll <= current:
                logger.info(f"🔍 [ADVENTURE DEBUG] Выбрано событие: id={event.get('id')}, type={event.get('type')}, weight={weight}")
                return event
        
        logger.info(f"🔍 [ADVENTURE DEBUG] Возвращаем первое событие: {events[0].get('id') if events else 'None'}")
        return events[0] if events else None
    
    async def get_adventure_history(self, pet_id: int, limit: int = 5) -> list:
        """Получение истории приключений"""
        return await self.adventure_repo.get_adventure_history(pet_id, limit)
    
    async def recover_energy(self, pet) -> None:
        """Восстановление энергии (lazy update) с учётом бонуса Сони"""
        if not pet.last_recovery:
            pet.last_recovery = datetime.utcnow()
            await self.session.flush()
            return
        
        now = datetime.utcnow()
        minutes_passed = (now - pet.last_recovery).total_seconds() / 60
        
        interval = self.balance.get("energy_recovery_interval", 30)
        recovery_amount = self.balance.get("energy_recovery", 10)
        
        # ===== БОНУС ХАРАКТЕРА (Соня) =====
        characters = data_loader.get("characters", {})
        character = characters.get(pet.character_id, {})
        bonus = character.get("bonus", {})
        if "recovery" in bonus:
            recovery_amount = int(recovery_amount * bonus["recovery"])
            logger.info(f"💤 Применён бонус Сони к восстановлению: x{bonus['recovery']}")
        
        recoveries = int(minutes_passed / interval)
        
        if recoveries > 0:
            max_energy = self.balance.get("max_energy", 100)
            old_energy = pet.energy
            pet.energy = min(pet.energy + recoveries * recovery_amount, max_energy)
            pet.last_recovery = now
            logger.info(f"⚡ ВОССТАНОВЛЕНИЕ ЭНЕРГИИ: pet_id={pet.id}, old_energy={old_energy}, recovered={recoveries * recovery_amount}, new_energy={pet.energy}")
            await self.session.flush()
            logger.info(f"💾 ЭНЕРГИЯ СОХРАНЕНА: pet_id={pet.id}, energy={pet.energy}")
    
    async def check_adventure_by_id(self, adventure_id: int) -> Dict[str, Any]:
        """
        Проверка статуса приключения по ID
        """
        adventure = await self.adventure_repo.get_adventure_by_id(adventure_id)
        if not adventure:
            return {
                "success": False,
                "completed": False,
                "message": "❌ Приключение не найдено"
            }
        
        if adventure.completed_at is not None:
            location = self.locations.get(adventure.location_id, {})
            location_name = location.get("name", adventure.location_id)
            location_emoji = location.get("emoji", "🗺️")
            
            message = (
                f"{location_emoji} <b>Приключение завершено!</b>\n\n"
                f"📍 {location_name}\n"
                f"⭐ XP: +{adventure.xp_gained or 0}\n"
                f"🪙 Монет: +{adventure.coins_gained or 0}\n"
            )
            
            if adventure.event_text:
                message += f"\n📖 {adventure.event_text}"
            
            return {
                "success": True,
                "completed": True,
                "message": message,
                "xp_gained": adventure.xp_gained or 0,
                "coins_gained": adventure.coins_gained or 0,
                "event_text": adventure.event_text
            }
        
        elapsed = (datetime.utcnow() - adventure.started_at).total_seconds()
        remaining = max(0, adventure.duration - elapsed)
        
        return {
            "success": False,
            "completed": False,
            "remaining_seconds": int(remaining),
            "message": f"⏳ Приключение в процессе... Осталось {int(remaining)} сек."
        }
    
    async def check_adventure(
        self,
        user_id: int,
        pet_id: int,
        location_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Проверка статуса приключения для питомца
        """
        user = await self.user_repo.get_by_telegram_id(user_id)
        if not user:
            return {
                "can_start": False,
                "has_active": False,
                "message": "❌ Пользователь не найден",
                "error": "user_not_found"
            }
        
        pet = await self.pet_repo.get_by_id(pet_id)
        if not pet:
            return {
                "can_start": False,
                "has_active": False,
                "message": "❌ Питомец не найден",
                "error": "pet_not_found"
            }
        
        await self.recover_energy(pet)
        
        result = {
            "can_start": False,
            "has_active": False,
            "energy": pet.energy,
            "pet_level": pet.level,
            "available_locations": [],
            "message": ""
        }
        
        active_adventure = await self.adventure_repo.get_active_adventure(pet_id)
        if active_adventure:
            result["has_active"] = True
            result["message"] = "⏳ У питомца уже есть активное приключение! Завершите его перед началом нового."
            result["can_start"] = False
            return result
        
        if location_id:
            location = self.locations.get(location_id)
            if not location:
                return {
                    "can_start": False,
                    "has_active": False,
                    "message": "❌ Локация не найдена",
                    "error": "location_not_found",
                    **result
                }
            
            min_level = location.get("min_level", 0)
            is_level_ok = pet.level >= min_level
            
            cooldown = await self.adventure_repo.get_cooldown(pet_id, location_id)
            cooldown_until = cooldown.cooldown_until if cooldown else None
            
            energy_cost = location.get("energy_cost", 10)
            has_energy = pet.energy >= energy_cost
            
            is_cooldown_ok = True
            cooldown_message = ""
            if cooldown_until and cooldown_until > datetime.utcnow():
                is_cooldown_ok = False
                remaining = cooldown_until - datetime.utcnow()
                minutes = int(remaining.total_seconds() / 60)
                seconds = int(remaining.total_seconds() % 60)
                cooldown_message = f"⏳ Кулдаун: {minutes} мин {seconds} сек"
            
            result.update({
                "can_start": is_level_ok and has_energy and is_cooldown_ok,
                "cooldown_until": cooldown_until,
                "location": location,
                "energy_needed": energy_cost,
                "location_level": min_level,
                "is_level_ok": is_level_ok,
                "is_cooldown_ok": is_cooldown_ok,
                "has_energy": has_energy
            })
            
            messages = []
            if is_level_ok and has_energy and is_cooldown_ok:
                messages.append(f"✅ Можно начать приключение в {location.get('name', '')}!")
                messages.append(f"⚡ Нужно энергии: {energy_cost} (у тебя: {pet.energy})")
            else:
                if not is_level_ok:
                    messages.append(f"❌ Нужен уровень {min_level} (твой: {pet.level})")
                if not has_energy:
                    messages.append(f"❌ Недостаточно энергии! Нужно {energy_cost}, у тебя {pet.energy}")
                if not is_cooldown_ok:
                    messages.append(cooldown_message)
            
            result["message"] = "\n".join(messages)
            
        else:
            available = await self.get_available_locations(pet.level)
            result["available_locations"] = list(available.keys())
            
            if not available:
                result["message"] = "❌ Нет доступных локаций для текущего уровня"
                result["can_start"] = False
                return result
            
            available_with_status = []
            for loc_id, loc_data in available.items():
                cooldown = await self.adventure_repo.get_cooldown(pet_id, loc_id)
                cooldown_until = cooldown.cooldown_until if cooldown else None
                is_cooldown_ok = not (cooldown_until and cooldown_until > datetime.utcnow())
                energy_cost = loc_data.get("energy_cost", 10)
                has_energy = pet.energy >= energy_cost
                
                available_with_status.append({
                    "id": loc_id,
                    "name": loc_data.get("name", ""),
                    "emoji": loc_data.get("emoji", ""),
                    "level": loc_data.get("min_level", 0),
                    "energy_cost": energy_cost,
                    "cooldown_until": cooldown_until,
                    "can_start": is_cooldown_ok and has_energy,
                    "is_cooldown_ok": is_cooldown_ok,
                    "has_energy": has_energy
                })
            
            result["available_with_status"] = available_with_status
            
            can_start_any = any(loc["can_start"] for loc in available_with_status)
            result["can_start"] = can_start_any
            
            if can_start_any:
                best_loc = max(
                    [loc for loc in available_with_status if loc["can_start"]],
                    key=lambda x: x["level"],
                    default=None
                )
                if best_loc:
                    result["message"] = (
                        f"✅ Доступно приключений: {len([l for l in available_with_status if l['can_start']])}\n"
                        f"🌟 Лучшая: {best_loc['emoji']} {best_loc['name']} (ур. {best_loc['level']})\n"
                        f"⚡ Энергия: {pet.energy}"
                    )
                else:
                    result["message"] = "⚠️ Доступны локации, но недостаточно энергии или кулдаун"
            else:
                reasons = []
                has_cooldown = any(not loc["is_cooldown_ok"] for loc in available_with_status)
                has_energy_issue = any(not loc["has_energy"] for loc in available_with_status)
                
                if has_cooldown:
                    reasons.append("⏳ Некоторые локации на кулдауне")
                if has_energy_issue:
                    reasons.append(f"⚡ Недостаточно энергии (нужно минимум {min(loc['energy_cost'] for loc in available_with_status)})")
                
                result["message"] = f"❌ Нельзя начать приключение: {', '.join(reasons)}"
        
        return result