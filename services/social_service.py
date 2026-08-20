import logging
from datetime import datetime, date
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import Bot

from database.repositories.social_repository import SocialRepository
from database.repositories.user_repository import UserRepository
from database.repositories.pet_repository import PetRepository
from database.repositories.inventory_repository import InventoryRepository
from database.repositories.gift_repository import GiftLogRepository
from database.repositories.achievement_repository import AchievementRepository
from database.models import Pet, User
from services.data_loader import data_loader
from services.chat_service import ChatService
from services.quest_service import QuestService
from utils.profanity_filter import validate_text

logger = logging.getLogger(__name__)


class SocialService:
    """Сервис для социальных взаимодействий"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.social_repo = SocialRepository(session)
        self.user_repo = UserRepository(session)
        self.pet_repo = PetRepository(session)
        self.inventory_repo = InventoryRepository(session)
        self.gift_log_repo = GiftLogRepository(session)
        self.achievement_repo = AchievementRepository(session)
        self.foods = data_loader.get("foods", {})
        self.titles = data_loader.get("titles", {})
        self.balance = data_loader.get_balance()
    
    # === ПРОСМОТР ПРОФИЛЯ ===
    
    async def get_pet_profile(self, viewer_id: int, pet_id: int) -> Dict[str, Any]:
        """Получить профиль питомца для просмотра"""
        pet = await self.pet_repo.get_by_id(pet_id)
        if not pet:
            return {"success": False, "message": "Питомец не найден"}
        
        user = await self.user_repo.get_by_id(pet.user_id)
        if not user:
            return {"success": False, "message": "Владелец не найден"}
        
        has_liked = False
        if viewer_id:
            like = await self.social_repo.get_like(viewer_id, pet_id)
            has_liked = like is not None
        
        title_data = self.titles.get(pet.title_id, {})
        title_text = f"{title_data.get('emoji', '')} {title_data.get('name', 'Нет титула')}" if pet.title_id else "🐣 Новичок"
        
        return {
            "success": True,
            "pet": pet,
            "owner": user,
            "has_liked": has_liked,
            "title_text": title_text,
            "hunger_status": pet.get_hunger_status()
        }
    
    # === ЛАЙКИ ===
    
    async def like_pet(self, from_user_id: int, pet_id: int) -> Dict[str, Any]:
        """Поставить лайк питомцу"""
        # Проверяем существование пользователя по telegram_id
        user = await self.user_repo.get_by_telegram_id(from_user_id)
        if not user:
            # Создаём пользователя, если его нет
            from database.repositories.user_repository import UserRepository
            user_repo = UserRepository(self.session)
            user = await user_repo.create(
                telegram_id=from_user_id,
                username=None,
                first_name=None,
                last_name=None
            )
            await self.session.flush()
            logger.info(f"Создан новый пользователь {from_user_id} при лайке")
        
        existing_like = await self.social_repo.get_like(from_user_id, pet_id)
        if existing_like:
            return {"success": False, "message": "Ты уже поставил лайк этому питомцу"}
        
        pet = await self.pet_repo.get_by_id(pet_id)
        if not pet:
            return {"success": False, "message": "Питомец не найден"}
        
        if pet.user_id == user.id:
            return {"success": False, "message": "Нельзя ставить лайк своему питомцу"}
        
        await self.social_repo.add_like(from_user_id, pet_id)
        pet.total_likes += 1
            
        likes = pet.total_likes
        if likes in [100, 500, 1000, 5000, 10000]:
            try:
                chat_service = ChatService(self.session)
                emoji_map = {
                    'dog': '🐶', 'cat': '🐱', 'fox': '🦊', 'wolf': '🐺',
                    'rabbit': '🐰', 'bear': '🐻', 'panda': '🐼', 'lion': '🦁',
                    'tiger': '🐯', 'dragon': '🐉', 'unicorn': '🦄', 'bird': '🐦',
                    'penguin': '🐧', 'owl': '🦉', 'elephant': '🐘', 'monkey': '🐒',
                    'koala': '🐨', 'sloth': '🦥', 'raccoon': '🦝', 'skunk': '🦨'
                }
                pet_emoji = emoji_map.get(pet.character_id, '🐾')
                message = f"{pet_emoji} У меня {likes} лайков! 🎉"
                await chat_service.add_event(
                    pet=pet,
                    event_type="likes_milestone",
                    message=message,
                    data={"likes_count": likes}
                )
                logger.info(f"✅ СООБЩЕНИЕ В ЧАТ ДОБАВЛЕНО (likes_milestone): pet_id={pet.id}, likes={likes}")
            except Exception as e:
                logger.error(f"❌ Ошибка добавления в чат: {e}")
        await self.pet_repo.update(pet)
        
        await self.session.flush()
        
        logger.info(f"Пользователь {from_user_id} поставил лайк питомцу {pet_id}")
        
        unlocked_titles = await self._unlock_social_titles(pet_id)
        
        return {
            "success": True,
            "message": f"❤️ Ты поставил лайк питомцу {pet.name}!",
            "total_likes": pet.total_likes,
            "unlocked_titles": unlocked_titles
        }
    
    async def unlike_pet(self, from_user_id: int, pet_id: int) -> Dict[str, Any]:
        """Убрать лайк"""
        user = await self.user_repo.get_by_telegram_id(from_user_id)
        if not user:
            return {"success": False, "message": "❌ Пользователь не найден. Используйте /start"}
        
        pet = await self.pet_repo.get_by_id(pet_id)
        if not pet:
            return {"success": False, "message": "Питомец не найден"}
        
        existing_like = await self.social_repo.get_like(from_user_id, pet_id)
        if not existing_like:
            return {"success": False, "message": "Ты не ставил лайк этому питомцу"}
        
        await self.social_repo.remove_like(from_user_id, pet_id)
        pet.total_likes = max(0, pet.total_likes - 1)
        await self.pet_repo.update(pet)
        
        await self.session.flush()
        
        return {
            "success": True,
            "message": f"💔 Ты убрал лайк у питомца {pet.name}",
            "total_likes": pet.total_likes
        }
    
    # === СОЦИАЛЬНЫЕ ТИТУЛЫ (ЧЕРЕЗ ДОСТИЖЕНИЯ) ===
    
    async def _unlock_social_titles(self, pet_id: int) -> List[Dict[str, Any]]:
        """Проверить и разблокировать социальные титулы через систему достижений"""
        pet = await self.pet_repo.get_by_id(pet_id)
        if not pet:
            return []
        
        social_title_map = {
            100: "social_likes_100",
            500: "social_likes_500",
            1000: "social_likes_1000",
            5000: "social_likes_5000",
            10000: "social_likes_10000"
        }
        
        unlocked = []
        
        for likes_required, title_id in social_title_map.items():
            if pet.total_likes >= likes_required:
                achievement = await self.achievement_repo.get_by_id(pet_id, title_id)
                if achievement:
                    continue
                
                await self.achievement_repo.unlock(pet_id, title_id)
                
                title_data = self.titles.get(title_id, {})
                if title_data:
                    unlocked.append({
                        "id": title_id,
                        "name": title_data.get("name", ""),
                        "emoji": title_data.get("emoji", ""),
                        "description": title_data.get("description", "")
                    })
                    
                    if not pet.title_id or pet.title_id == "newcomer":
                        pet.title_id = title_id
                        await self.session.flush()
                    
                    logger.info(f"🏆 Социальный титул '{title_data.get('name')}' разблокирован для питомца {pet_id}")
        
        return unlocked
    
    # === ПОДАРКИ ===
    
    async def check_gift_limits(self, user_id: int, item_rarity: str) -> Tuple[bool, str, int]:
        """Проверить лимиты подарков"""
        rarity_limits = {
            "common": float('inf'),
            "uncommon": float('inf'),
            "rare": 10,
            "epic": 10,
            "legendary": 10,
            "cosmetic": 5
        }
        
        if item_rarity in ["rare", "epic", "legendary"]:
            limit = 10
        elif item_rarity in ["cosmetic"]:
            limit = 5
        else:
            limit = float('inf')
        
        if limit == float('inf'):
            return True, "", 0
        
        today = datetime.utcnow().date()
        sent_count = await self.gift_log_repo.get_today_gift_count(user_id, item_rarity)
        remaining = limit - sent_count
        
        if remaining <= 0:
            return False, f"⚠️ Достигнут лимит подарков для редкости '{item_rarity}' ({limit}/день)", limit
        
        return True, f"Осталось {remaining} подарков", limit
    
    async def send_gift(
        self,
        from_user_id: int,
        to_user_id: int,
        item_id: str,
        quantity: int = 1,
        message: str = None,
        bot: Bot = None
    ) -> Dict[str, Any]:
        """Отправить подарок"""
        logger.debug(
            f"send_gift: from_user_id={from_user_id}, to_user_id={to_user_id}, "
            f"item_id={item_id}, quantity={quantity}"
        )
        
        from_user = await self.user_repo.get_by_telegram_id(from_user_id)
        if not from_user:
            return {"success": False, "message": "Отправитель не найден"}
        
        to_user = await self.user_repo.get_by_id(to_user_id)
        if not to_user:
            return {"success": False, "message": "Получатель не найден"}
        
        if from_user.id == to_user.id:
            return {"success": False, "message": "Нельзя отправить подарок себе"}
        
        food = self.foods.get(item_id)
        if not food:
            return {"success": False, "message": f"Можно дарить только еду (неизвестный предмет: {item_id})"}
        
        sender_pet = await self.pet_repo.get_by_user_id(from_user.id)
        if sender_pet:
            characters = data_loader.get("characters", {})
            character = characters.get(sender_pet.character_id, {})
            bonus = character.get("bonus", {})
            gift_bonus = bonus.get("gift", 1.0)
            
            if gift_bonus > 1.0:
                old_quantity = quantity
                quantity = int(quantity * gift_bonus)
                logger.info(f"🎁 Бонус Добряка: {old_quantity} → {quantity} (x{gift_bonus})")
        
        has_item = await self.inventory_repo.has_item(from_user.id, item_id, quantity)
        if not has_item:
            return {"success": False, "message": f"У тебя нет {quantity} шт. этого предмета"}
        
        if message:
            is_valid, error, filtered_message = validate_text(message, "Сообщение")
            if not is_valid:
                return {
                    "success": False,
                    "message": f"{error}\n\n"
                               f"📝 Исправленный вариант: {filtered_message}"
                }
        
        rarity = food.get("rarity", "common")
        can_send, limit_msg, limit = await self.check_gift_limits(from_user.id, rarity)
        if not can_send:
            return {"success": False, "message": limit_msg}
        
        removed = await self.inventory_repo.remove_item(from_user.id, item_id, quantity)
        if not removed:
            return {"success": False, "message": "Не удалось удалить предмет из инвентаря"}
        
        await self.inventory_repo.add_item(to_user.id, item_id, quantity)
        
        gift = await self.social_repo.send_gift(
            from_user_id=from_user.id,
            to_user_id=to_user.id,
            item_id=item_id,
            item_type="food",
            quantity=quantity,
            message=message
        )
        
        await self.gift_log_repo.increment_gift_count(
            user_id=from_user.id,
            item_id=item_id,
            item_rarity=rarity,
            quantity=quantity
        )
        
        await self.session.flush()
        
        logger.info(f"Пользователь {from_user_id} подарил {quantity}x {item_id} пользователю {to_user_id}")
        
        try:
            quest_service = QuestService(self.session)
            await quest_service.update_quest_progress(
                user_id=from_user_id,
                condition_type="send_gift",
                value=1
            )
            logger.info(f"📋 КВЕСТ ОБНОВЛЕН (send_gift): user_id={from_user_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка обновления квеста (send_gift): {e}")
        
        try:
            chat_service = ChatService(self.session)
            to_pet = await self.pet_repo.get_by_user_id(to_user.id)
            if to_pet:
                sender_name = from_user.first_name or from_user.username or "Неизвестно"
                food_name = food.get("name", item_id)
                food_emoji = food.get("emoji", "🎁")
                await chat_service.add_event(
                    pet=to_pet,
                    event_type="gift_received",
                    message=f"{sender_name} подарил мне {food_emoji} {food_name}! ❤️",
                    data={"sender_name": sender_name, "gift_name": food_name}
                )
                logger.info(f"✅ СООБЩЕНИЕ В ЧАТ ДОБАВЛЕНО (gift_received): pet_id={to_pet.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка добавления в чат (подарок): {e}")
        
        if bot and to_user.telegram_id:
            try:
                sender_name = from_user.first_name or from_user.username or "Неизвестно"
                food_emoji = food.get("emoji", "🎁")
                food_name = food.get("name", item_id)
                
                notification_text = (
                    f"🎁 <b>Ты получил подарок!</b>\n\n"
                    f"👤 От: {sender_name}\n"
                    f"🎁 Подарок: {food_emoji} {food_name} x{quantity}\n"
                )
                if message:
                    notification_text += f"💬 Сообщение: \"{message}\"\n\n"
                else:
                    notification_text += "\n"
                
                notification_text += f"📦 Подарок ждёт тебя в почте!\n"
                notification_text += f"📬 Загляни в почту, чтобы получить его!"
                
                await bot.send_message(
                    chat_id=to_user.telegram_id,
                    text=notification_text,
                    parse_mode="HTML"
                )
                logger.info(f"Уведомление о подарке отправлено пользователю {to_user.telegram_id}")
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление о подарке: {e}")
        
        return {
            "success": True,
            "message": f"🎁 Подарок отправлен!",
            "gift": gift,
            "item_name": food.get("name", item_id),
            "item_emoji": food.get("emoji", ""),
            "quantity": quantity
        }
    
    # === РЕЙТИНГ ===
    
    async def get_rating(self, rating_type: str = "level", limit: int = 10) -> Dict[str, Any]:
        if rating_type == "level":
            results = await self.social_repo.get_rating_by_level(limit)
        elif rating_type == "likes":
            results = await self.social_repo.get_rating_by_likes(limit)
        else:
            return {"success": False, "message": "Неверный тип рейтинга"}
        
        rating_list = []
        for pet, user in results:
            rating_list.append({
                "pet_id": pet.id,
                "pet_name": pet.name,
                "photo": pet.photo_file_id,
                "owner_name": user.first_name or user.username,
                "level": pet.level,
                "likes": pet.total_likes,
                "title": pet.title_id
            })
        
        return {
            "success": True,
            "type": rating_type,
            "rating": rating_list
        }
    
    # === КОЛИЧЕСТВО НЕПРОЧИТАННЫХ ПОДАРКОВ ===
    
    async def get_unread_gifts_count(self, user_id: int) -> int:
        """Получить количество непрочитанных подарков для пользователя"""
        user = await self.user_repo.get_by_telegram_id(user_id)
        if not user:
            return 0
        return await self.social_repo.get_unread_gifts_count(user.id)
    
    # === СЛУЧАЙНЫЙ ПИТОМЕЦ ===
    
    async def get_random_pet(self, exclude_pet_id: int) -> Optional[Pet]:
        return await self.pet_repo.get_random_pet(exclude_pet_id)