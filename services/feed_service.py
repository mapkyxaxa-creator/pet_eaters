"""
Сервис для работы с социальной лентой
"""
import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.repositories.post_repository import PostRepository
from database.repositories.pet_repository import PetRepository
from database.repositories.user_repository import UserRepository
from database.repositories.photo_repository import PhotoRepository
from database.models import Subscription, Notification, Post
from services.data_loader import data_loader
from services.chat_service import ChatService

logger = logging.getLogger(__name__)


class FeedService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.post_repo = PostRepository(session)
        self.pet_repo = PetRepository(session)
        self.user_repo = UserRepository(session)
        self.photo_repo = PhotoRepository(session)
        self.characters = data_loader.get("characters", {})
    
    async def post_exists_for_photo(self, photo_id: int) -> bool:
        """Проверить, существует ли пост для данного фото"""
        result = await self.session.execute(
            select(Post).where(Post.photo_id == photo_id)
        )
        return result.scalar_one_or_none() is not None
    
    async def create_post(self, pet_id: int, photo_id: int, caption: str = None, is_published: bool = True) -> Dict[str, Any]:
        """Создать пост (по умолчанию опубликован)"""
        try:
            # ===== ПРОВЕРКА НА ДУБЛЬ =====
            exists = await self.post_exists_for_photo(photo_id)
            if exists:
                logger.warning(f"⚠️ Пост для фото {photo_id} уже существует! Пропускаем.")
                return {"success": True, "post_id": None, "already_exists": True}
            
            post = await self.post_repo.create_post(pet_id, photo_id, caption, is_published=is_published)
            return {"success": True, "post_id": post.id}
        except Exception as e:
            logger.error(f"Ошибка создания поста: {e}")
            return {"success": False, "message": str(e)}
    
    async def get_feed(self, viewer_pet_id: int, limit: int = 10) -> Dict[str, Any]:
        """
        Получить ленту (посты подписок + случайные)
        
        Args:
            viewer_pet_id: ID питомца, который смотрит ленту (для проверки лайков)
            limit: количество элементов
        """
        # Резолвим зрителя один раз — его user_id нужен для проверки лайков
        viewer_pet = await self.pet_repo.get_by_id(viewer_pet_id)
        viewer_user_id = viewer_pet.user_id if viewer_pet else None

        subscribed_ids = await self.post_repo.get_subscribed_pet_ids(viewer_pet_id)
        
        if viewer_pet_id not in subscribed_ids:
            subscribed_ids.append(viewer_pet_id)
        
        posts = await self.post_repo.get_feed_by_pet_ids(subscribed_ids, limit=limit // 2)
        
        items = []
        
        for post in posts:
            photo = await self.photo_repo.get_by_id(post["photo_id"])
            pet = await self.pet_repo.get_by_id(post["pet_id"])
            if pet:
                # ===== ИСПРАВЛЕНО: проверяем лайк от ТЕКУЩЕГО зрителя, а не автора =====
                has_liked = (
                    await self.post_repo.has_user_liked_post(viewer_user_id, post["id"])
                    if viewer_user_id else False
                )
                items.append({
                    "type": "post",
                    "data": {
                        **post,
                        "photo_file_id": photo.telegram_file_id if photo else None,
                        "pet_name": pet.name,
                        "has_liked": has_liked,
                        "character_emoji": self.characters.get(pet.character_id, {}).get("emoji", "🐾")
                    }
                })
        
        if len(items) < limit:
            random_pets = await self.pet_repo.get_random_pets(exclude_pet_id=viewer_pet_id, limit=2)
            for pet in random_pets:
                if pet:
                    user = await self.user_repo.get_by_id(pet.user_id)
                    items.append({
                        "type": "random_pet",
                        "data": {
                            "id": pet.id,
                            "name": pet.name,
                            "photo_file_id": pet.photo_file_id,
                            "level": pet.level,
                            "total_likes": pet.total_likes,
                            "game_id": pet.game_id,
                            "owner_name": user.first_name or user.username if user else "Неизвестно",
                            "character_emoji": self.characters.get(pet.character_id, {}).get("emoji", "🐾")
                        }
                    })
        
        return {"items": items}
    
    async def like_post(self, user_id: int, post_id: int) -> Dict[str, Any]:
        """Поставить лайк посту"""
        post = await self.post_repo.get_post(post_id)
        if not post:
            return {"success": False, "message": "Пост не найден"}
        
        result = await self.post_repo.like_post(user_id, post_id)
        if not result:
            return {"success": False, "message": "Ты уже лайкнул этот пост"}
        
        await self.session.flush()
        return {"success": True, "message": "❤️ Лайк поставлен!"}
    
    async def unlike_post(self, user_id: int, post_id: int) -> Dict[str, Any]:
        """Убрать лайк с поста"""
        post = await self.post_repo.get_post(post_id)
        if not post:
            return {"success": False, "message": "Пост не найден"}
        
        result = await self.post_repo.unlike_post(user_id, post_id)
        if not result:
            return {"success": False, "message": "Ты не лайкал этот пост"}
        
        await self.session.flush()
        return {"success": True, "message": "💔 Лайк убран"}
    
    async def add_comment(self, user_id: int, post_id: int, text: str) -> Dict[str, Any]:
        """Добавить комментарий"""
        # ===== ИСПРАВЛЕНО: post — это словарь, а не ORM-объект =====
        post_dict = await self.post_repo.get_post(post_id)
        if not post_dict:
            return {"success": False, "message": "Пост не найден"}
        
        pet = await self.pet_repo.get_by_user_id(user_id)
        if not pet:
            return {"success": False, "message": "У тебя нет питомца"}
        
        try:
            # Сохраняем комментарий
            comment = await self.post_repo.add_comment(
                post_id=post_id,
                user_id=user_id,
                pet_id=pet.id,
                text=text
            )
            
            # ===== ИСПРАВЛЕНО: обращаемся к словарю через ['pet'], а не .pet =====
            author_user_id = None
            pet_data = post_dict.get('pet')
            if pet_data and pet_data.get('user_id'):
                author_user_id = pet_data.get('user_id')
            
            if author_user_id:
                await self._create_notification(
                    user_id=author_user_id,
                    notification_type="comment",
                    text=f"{pet.name} оставил комментарий под вашим постом: \"{text[:50]}...\"",
                    data={"post_id": post_id, "comment_id": comment.get('id'), "pet_name": pet.name}
                )
            
            await self.session.flush()
            return {"success": True, "comment_id": comment.get('id')}
        except Exception as e:
            logger.error(f"Ошибка добавления комментария: {e}")
            return {"success": False, "message": str(e)}
    
    # ============================================================
    # ПОДПИСКИ
    # ============================================================
    
    async def subscribe(self, subscriber_pet_id: int, target_pet_id: int) -> Dict[str, Any]:
        """Подписаться на питомца"""
        if subscriber_pet_id == target_pet_id:
            return {"success": False, "message": "❌ Нельзя подписаться на себя"}
        
        existing = await self.post_repo.get_subscription(subscriber_pet_id, target_pet_id)
        if existing:
            return {"success": False, "message": "✅ Ты уже подписан на этого питомца"}
        
        subscription = Subscription(
            subscriber_pet_id=subscriber_pet_id,
            target_pet_id=target_pet_id,
            created_at=datetime.utcnow()
        )
        self.session.add(subscription)
        await self.session.flush()
        
        subscriber = await self.pet_repo.get_by_id(subscriber_pet_id)
        target = await self.pet_repo.get_by_id(target_pet_id)
        
        logger.info(f"➕ {subscriber.name if subscriber else 'Питомец'} подписался на {target.name if target else 'питомца'}")
        
        if target and target.user_id:
            await self._create_notification(
                user_id=target.user_id,
                notification_type="subscription",
                text=f"{subscriber.name if subscriber else 'Питомец'} подписался на вашего питомца!",
                data={"subscriber_pet_id": subscriber_pet_id, "target_pet_id": target_pet_id}
            )
        
        return {
            "success": True,
            "message": f"✅ Ты подписался на {target.name if target else 'питомца'}!"
        }
    
    async def unsubscribe(self, subscriber_pet_id: int, target_pet_id: int) -> Dict[str, Any]:
        """Отписаться от питомца"""
        existing = await self.post_repo.get_subscription(subscriber_pet_id, target_pet_id)
        if not existing:
            return {"success": False, "message": "❌ Ты не подписан на этого питомца"}
        
        await self.session.delete(existing)
        await self.session.flush()
        
        target = await self.pet_repo.get_by_id(target_pet_id)
        
        return {
            "success": True,
            "message": f"✅ Ты отписался от {target.name if target else 'питомца'}"
        }
    
    async def is_subscribed(self, subscriber_pet_id: int, target_pet_id: int) -> bool:
        """Проверить, подписан ли питомец"""
        subscription = await self.post_repo.get_subscription(subscriber_pet_id, target_pet_id)
        return subscription is not None
    
    async def get_subscribers_count(self, pet_id: int) -> int:
        """Получить количество подписчиков"""
        return await self.post_repo.get_subscribers_count(pet_id)
    
    async def get_subscriptions_count(self, pet_id: int) -> int:
        """Получить количество подписок"""
        return await self.post_repo.get_subscriptions_count(pet_id)
    
    async def get_subscribers_list(self, pet_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """Получить список подписчиков питомца"""
        subscriptions = await self.post_repo.get_subscribers(pet_id, limit)
        
        result = []
        for sub in subscriptions:
            subscriber_pet = await self.pet_repo.get_by_id(sub.subscriber_pet_id)
            if subscriber_pet:
                owner = await self.user_repo.get_by_id(subscriber_pet.user_id)
                result.append({
                    "id": subscriber_pet.id,
                    "name": subscriber_pet.name,
                    "level": subscriber_pet.level,
                    "game_id": subscriber_pet.game_id,
                    "emoji": self.characters.get(subscriber_pet.character_id, {}).get("emoji", "🐾"),
                    "owner_name": owner.first_name or owner.username if owner else "Неизвестно"
                })
        
        return result
    
    # ============================================================
    # УВЕДОМЛЕНИЯ
    # ============================================================
    
    async def _create_notification(self, user_id: int, notification_type: str, text: str, data: dict = None) -> None:
        """Создать уведомление для пользователя"""
        try:
            notification = Notification(
                user_id=user_id,
                type=notification_type,
                text=text,
                data=json.dumps(data) if data else None,
                is_read=False,
                created_at=datetime.utcnow()
            )
            self.session.add(notification)
            await self.session.flush()
            logger.info(f"🔔 Уведомление создано: user_id={user_id}, type={notification_type}")
        except Exception as e:
            logger.error(f"❌ Ошибка создания уведомления: {e}")
    
    async def get_notifications(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """Получить уведомления пользователя"""
        notifications = await self.post_repo.get_notifications(user_id, limit)
        
        return [
            {
                "id": n.id,
                "type": n.type,
                "text": n.text,
                "data": json.loads(n.data) if n.data else None,
                "is_read": n.is_read,
                "created_at": n.created_at
            }
            for n in notifications
        ]
    
    async def mark_notification_read(self, notification_id: int) -> bool:
        """Отметить уведомление как прочитанное"""
        notification = await self.session.get(Notification, notification_id)
        if notification:
            notification.is_read = True
            await self.session.flush()
            return True
        return False
    
    async def mark_all_notifications_read(self, user_id: int) -> int:
        """Отметить все уведомления как прочитанные"""
        from sqlalchemy import update
        
        result = await self.session.execute(
            update(Notification)
            .where(Notification.user_id == user_id)
            .where(Notification.is_read == False)
            .values(is_read=True)
        )
        await self.session.flush()
        return result.rowcount
    
    async def get_unread_notifications_count(self, user_id: int) -> int:
        """Получить количество непрочитанных уведомлений"""
        return await self.post_repo.get_unread_notifications_count(user_id)
    
    # ============================================================
    # ФОРМАТИРОВАНИЕ
    # ============================================================
    
    async def format_post(self, post: Dict[str, Any]) -> str:
        """Форматировать пост для отображения"""
        lines = [
            f"📸 <b>Пост от {post.get('character_emoji', '🐾')} {post.get('pet_name', 'Питомец')}</b>",
            ""
        ]
        
        if post.get("caption"):
            lines.append(f"💬 {post['caption']}")
            lines.append("")
        
        lines.append(f"❤️ {post.get('likes_count', 0)} лайков  💬 {post.get('comments_count', 0)} комментариев")
        
        created_at = post.get('created_at')
        if created_at:
            if isinstance(created_at, datetime):
                lines.append(f"🕐 {created_at.strftime('%d.%m.%Y %H:%M')}")
            elif isinstance(created_at, str):
                try:
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    lines.append(f"🕐 {dt.strftime('%d.%m.%Y %H:%M')}")
                except:
                    lines.append(f"🕐 {created_at}")
            else:
                lines.append(f"🕐 {created_at}")
        
        return "\n".join(lines)
    
    async def format_random_pet(self, pet: Dict[str, Any]) -> str:
        """Форматировать случайного питомца"""
        lines = [
            f"🐾 <b>СЛУЧАЙНЫЙ ПИТОМЕЦ</b>",
            f"{pet.get('character_emoji', '🐾')} <b>{pet.get('name', 'Безымянный')}</b>",
            f"⭐ Уровень {pet.get('level', 1)}",
            f"❤️ {pet.get('total_likes', 0)} лайков",
            f"🆔 ID: <code>{pet.get('game_id', '')}</code>",
            f"👤 Владелец: {pet.get('owner_name', 'Неизвестно')}"
        ]
        return "\n".join(lines)