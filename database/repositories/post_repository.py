"""
Репозиторий для работы с постами в социальной ленте.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, desc, and_, delete, update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import (
    Post, Photo, Pet, User, Comment, Notification, 
    Subscription, PostLike
)


class PostRepository:
    """Репозиторий для управления постами"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ============================================================
    # ОСНОВНЫЕ МЕТОДЫ
    # ============================================================

    async def create_post(
        self,
        pet_id: int,
        photo_id: int,
        caption: Optional[str] = None,
        is_published: bool = False
    ) -> Post:
        """Создать новый пост"""
        post = Post(
            pet_id=pet_id,
            photo_id=photo_id,
            caption=caption,
            likes_count=0,
            comments_count=0,
            is_published=is_published,
            created_at=datetime.utcnow()
        )
        self.session.add(post)
        await self.session.flush()
        return post

    async def get_post(self, post_id: int) -> Optional[Dict[str, Any]]:
        """Получить пост по ID с подгрузкой связанных данных (возвращает словарь)"""
        result = await self.session.execute(
            select(Post)
            .where(Post.id == post_id)
            .options(
                selectinload(Post.pet).selectinload(Pet.user),
                selectinload(Post.photo),
                selectinload(Post.comments).selectinload(Comment.pet).selectinload(Pet.user)
            )
        )
        post = result.scalar_one_or_none()
        if not post:
            return None
        return await self._post_to_dict(post)
    
    async def get_post_by_id(self, post_id: int) -> Optional[Post]:
        """Получить пост по ID (возвращает ORM-объект)"""
        result = await self.session.execute(
            select(Post)
            .where(Post.id == post_id)
            .options(
                selectinload(Post.pet).selectinload(Pet.user),
                selectinload(Post.photo),
                selectinload(Post.comments).selectinload(Comment.pet).selectinload(Pet.user)
            )
        )
        return result.scalar_one_or_none()

    async def get_feed_by_pet_ids(
        self,
        pet_ids: List[int],
        limit: int = 10,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Получить ленту постов для списка питомцев"""
        if not pet_ids:
            return []

        result = await self.session.execute(
            select(Post)
            .where(
                Post.pet_id.in_(pet_ids),
                Post.is_published == True
            )
            .order_by(desc(Post.created_at))
            .limit(limit)
            .offset(offset)
            .options(
                selectinload(Post.pet).selectinload(Pet.user),
                selectinload(Post.photo),
                selectinload(Post.comments).selectinload(Comment.pet).selectinload(Pet.user)
            )
        )
        posts = result.scalars().all()
        return [await self._post_to_dict(post) for post in posts]

    async def get_posts_by_pet(
        self,
        pet_id: int,
        limit: int = 10,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Получить посты конкретного питомца"""
        result = await self.session.execute(
            select(Post)
            .where(
                Post.pet_id == pet_id,
                Post.is_published == True
            )
            .order_by(desc(Post.created_at))
            .limit(limit)
            .offset(offset)
            .options(
                selectinload(Post.pet).selectinload(Pet.user),
                selectinload(Post.photo),
                selectinload(Post.comments).selectinload(Comment.pet).selectinload(Pet.user)
            )
        )
        posts = result.scalars().all()
        return [await self._post_to_dict(post) for post in posts]

    async def get_pending_posts(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Получить посты на модерации"""
        result = await self.session.execute(
            select(Post)
            .where(Post.is_published == False)
            .order_by(desc(Post.created_at))
            .limit(limit)
            .options(
                selectinload(Post.pet).selectinload(Pet.user),
                selectinload(Post.photo)
            )
        )
        posts = result.scalars().all()
        return [await self._post_to_dict(post) for post in posts]

    async def publish_post(self, post_id: int) -> bool:
        """Опубликовать пост"""
        result = await self.session.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(is_published=True, updated_at=datetime.utcnow())
            .returning(Post.id)
        )
        await self.session.flush()
        return result.scalar_one_or_none() is not None

    async def delete_post(self, post_id: int) -> bool:
        """Удалить пост"""
        result = await self.session.execute(
            delete(Post).where(Post.id == post_id).returning(Post.id)
        )
        await self.session.flush()
        return result.scalar_one_or_none() is not None

    # ============================================================
    # ЛАЙКИ
    # ============================================================

    async def like_post(self, user_id: int, post_id: int) -> bool:
        """Поставить лайк посту"""
        existing = await self.session.execute(
            select(PostLike).where(
                PostLike.post_id == post_id,
                PostLike.user_id == user_id
            )
        )
        if existing.scalar_one_or_none():
            return False
        
        like = PostLike(
            post_id=post_id,
            user_id=user_id,
            created_at=datetime.utcnow()
        )
        self.session.add(like)
        
        await self.session.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(likes_count=Post.likes_count + 1, updated_at=datetime.utcnow())
        )
        await self.session.flush()
        return True

    async def unlike_post(self, user_id: int, post_id: int) -> bool:
        """Убрать лайк с поста"""
        result = await self.session.execute(
            delete(PostLike)
            .where(
                PostLike.post_id == post_id,
                PostLike.user_id == user_id
            )
            .returning(PostLike.id)
        )
        if result.scalar_one_or_none():
            await self.session.execute(
                update(Post)
                .where(Post.id == post_id)
                .values(likes_count=Post.likes_count - 1, updated_at=datetime.utcnow())
            )
            await self.session.flush()
            return True
        return False

    async def has_user_liked_post(self, user_id: int, post_id: int) -> bool:
        """Проверить, поставил ли пользователь лайк посту"""
        result = await self.session.execute(
            select(PostLike).where(
                PostLike.post_id == post_id,
                PostLike.user_id == user_id
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_likes_count(self, post_id: int) -> int:
        """Получить количество лайков поста"""
        result = await self.session.execute(
            select(func.count(PostLike.id))
            .where(PostLike.post_id == post_id)
        )
        return result.scalar() or 0

    # ============================================================
    # КОММЕНТАРИИ
    # ============================================================

    async def get_comments(self, post_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """Получить комментарии к посту"""
        result = await self.session.execute(
            select(Comment)
            .where(
                Comment.post_id == post_id,
                Comment.is_deleted == False
            )
            .order_by(desc(Comment.created_at))
            .limit(limit)
            .options(
                selectinload(Comment.pet).selectinload(Pet.user),
                selectinload(Comment.user)
            )
        )
        comments = result.scalars().all()
        return [await self._comment_to_dict(comment) for comment in comments]

    async def add_comment(
        self,
        post_id: int,
        user_id: int,
        pet_id: int,
        text: str
    ) -> Dict[str, Any]:
        """Добавить комментарий к посту"""
        comment = Comment(
            post_id=post_id,
            user_id=user_id,
            pet_id=pet_id,
            text=text,
            created_at=datetime.utcnow()
        )
        self.session.add(comment)
        
        await self.session.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(comments_count=Post.comments_count + 1, updated_at=datetime.utcnow())
        )
        await self.session.flush()
        return await self._comment_to_dict(comment)

    async def delete_comment(self, comment_id: int) -> bool:
        """Удалить комментарий"""
        # Получаем комментарий, чтобы обновить счётчик поста
        comment = await self.session.get(Comment, comment_id)
        if not comment:
            return False
        
        # Помечаем как удалённый
        await self.session.execute(
            update(Comment)
            .where(Comment.id == comment_id)
            .values(is_deleted=True, updated_at=datetime.utcnow())
        )
        
        # Обновляем счётчик комментариев поста
        await self.session.execute(
            update(Post)
            .where(Post.id == comment.post_id)
            .values(comments_count=Post.comments_count - 1, updated_at=datetime.utcnow())
        )
        await self.session.flush()
        return True

    # ============================================================
    # ПОДПИСКИ
    # ============================================================

    async def get_subscribed_pet_ids(self, pet_id: int) -> List[int]:
        """Получить ID питомцев, на которых подписан данный питомец"""
        result = await self.session.execute(
            select(Subscription.target_pet_id)
            .where(Subscription.subscriber_pet_id == pet_id)
        )
        return result.scalars().all()

    async def get_subscription(self, subscriber_pet_id: int, target_pet_id: int) -> Optional[Subscription]:
        """Получить подписку"""
        result = await self.session.execute(
            select(Subscription)
            .where(
                Subscription.subscriber_pet_id == subscriber_pet_id,
                Subscription.target_pet_id == target_pet_id
            )
        )
        return result.scalar_one_or_none()

    async def get_subscribers_count(self, pet_id: int) -> int:
        """Получить количество подписчиков питомца"""
        result = await self.session.execute(
            select(func.count(Subscription.id))
            .where(Subscription.target_pet_id == pet_id)
        )
        return result.scalar() or 0

    async def get_subscriptions_count(self, pet_id: int) -> int:
        """Получить количество подписок питомца"""
        result = await self.session.execute(
            select(func.count(Subscription.id))
            .where(Subscription.subscriber_pet_id == pet_id)
        )
        return result.scalar() or 0

    async def get_subscribers(self, pet_id: int, limit: int = 20) -> List[Subscription]:
        """Получить список подписчиков питомца"""
        result = await self.session.execute(
            select(Subscription)
            .where(Subscription.target_pet_id == pet_id)
            .limit(limit)
        )
        return result.scalars().all()

    # ============================================================
    # УВЕДОМЛЕНИЯ
    # ============================================================

    async def get_unread_notifications_count(self, user_id: int) -> int:
        """Получить количество непрочитанных уведомлений"""
        result = await self.session.execute(
            select(func.count(Notification.id))
            .where(
                Notification.user_id == user_id,
                Notification.is_read == False
            )
        )
        return result.scalar() or 0

    async def get_notifications(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0
    ) -> List[Notification]:
        """Получить уведомления пользователя"""
        result = await self.session.execute(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(desc(Notification.created_at))
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    async def mark_notification_read(self, notification_id: int) -> bool:
        """Отметить уведомление как прочитанное"""
        result = await self.session.execute(
            update(Notification)
            .where(Notification.id == notification_id)
            .values(is_read=True)
            .returning(Notification.id)
        )
        await self.session.flush()
        return result.scalar_one_or_none() is not None

    async def mark_all_notifications_read(self, user_id: int) -> int:
        """Отметить все уведомления как прочитанные"""
        result = await self.session.execute(
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_read == False
            )
            .values(is_read=True)
            .returning(Notification.id)
        )
        await self.session.flush()
        return len(result.scalars().all())

    # ============================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ============================================================

    async def _post_to_dict(self, post: Post) -> Dict[str, Any]:
        """Преобразовать объект Post в словарь"""
        pet_data = None
        if post.pet:
            pet_data = {
                "id": post.pet.id,
                "name": post.pet.name,
                "level": post.pet.level,
                "photo_file_id": post.pet.photo_file_id,
                "title_id": post.pet.title_id,
                "character_id": post.pet.character_id,
                "game_id": post.pet.game_id,
                "user_id": post.pet.user_id
            }
            if post.pet.user:
                pet_data["owner_name"] = (
                    post.pet.user.username or 
                    post.pet.user.first_name or 
                    f"Игрок {post.pet.user.telegram_id}"
                )
                pet_data["owner_telegram_id"] = post.pet.user.telegram_id

        photo_data = None
        if post.photo:
            photo_data = {
                "id": post.photo.id,
                "telegram_file_id": post.photo.telegram_file_id,
                "caption": post.photo.caption,
                "is_main": post.photo.is_main
            }

        comments_data = []
        if post.comments:
            for comment in post.comments:
                if not comment.is_deleted:
                    comments_data.append(await self._comment_to_dict(comment))

        return {
            "id": post.id,
            "pet_id": post.pet_id,
            "photo_id": post.photo_id,
            "caption": post.caption,
            "likes_count": post.likes_count or 0,
            "comments_count": post.comments_count or 0,
            "is_published": post.is_published,
            "created_at": post.created_at.isoformat() if post.created_at else None,
            "updated_at": post.updated_at.isoformat() if post.updated_at else None,
            "pet": pet_data,
            "photo": photo_data,
            "comments": comments_data
        }

    async def _comment_to_dict(self, comment: Comment) -> Dict[str, Any]:
        """Преобразовать объект Comment в словарь"""
        pet_data = None
        if comment.pet:
            pet_data = {
                "id": comment.pet.id,
                "name": comment.pet.name,
                "level": comment.pet.level,
                "photo_file_id": comment.pet.photo_file_id,
                "game_id": comment.pet.game_id
            }
            if comment.pet.user:
                pet_data["owner_name"] = (
                    comment.pet.user.username or 
                    comment.pet.user.first_name or 
                    f"Игрок {comment.pet.user.telegram_id}"
                )

        user_data = None
        if comment.user:
            user_data = {
                "id": comment.user.id,
                "telegram_id": comment.user.telegram_id,
                "username": comment.user.username or comment.user.first_name or f"Игрок {comment.user.telegram_id}"
            }

        return {
            "id": comment.id,
            "post_id": comment.post_id,
            "user_id": comment.user_id,
            "pet_id": comment.pet_id,
            "text": comment.text,
            "created_at": comment.created_at.isoformat() if comment.created_at else None,
            "updated_at": comment.updated_at.isoformat() if comment.updated_at else None,
            "is_deleted": comment.is_deleted,
            "pet": pet_data,
            "user": user_data
        }