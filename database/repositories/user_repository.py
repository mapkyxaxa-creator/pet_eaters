from typing import Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database.models import User


class UserRepository:
    """Репозиторий для работы с пользователями"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Получение пользователя по telegram_id"""
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_id(self, user_id: int) -> Optional[User]:
        """Получение пользователя по ID"""
        return await self.session.get(User, user_id)
    
    async def get_by_username(self, username: str) -> Optional[User]:
        """Получение пользователя по username (без @)"""
        if username.startswith("@"):
            username = username[1:]
        result = await self.session.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()
    
    async def create(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> User:
        """Создание нового пользователя"""
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            coins=500  # Стартовые монеты
        )
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user
    
    async def update_last_active(self, user_id: int) -> None:
        """Обновление времени последней активности"""
        user = await self.session.get(User, user_id)
        if user:
            user.last_active = datetime.utcnow()
            await self.session.flush()
    
    async def update_coins(self, user_id: int, amount: int) -> Optional[User]:
        """Обновить количество монет пользователя"""
        user = await self.session.get(User, user_id)
        if user:
            user.coins += amount
            await self.session.flush()
            await self.session.refresh(user)
            return user
        return None
    
    async def get_all_users(self, limit: int = 100, offset: int = 0) -> list:
        """Получить список всех пользователей"""
        result = await self.session.execute(
            select(User)
            .order_by(User.created_at)
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()
    
    async def count_users(self) -> int:
        """Получить общее количество пользователей"""
        result = await self.session.execute(
            select(func.count(User.id))
        )
        return result.scalar() or 0
    
    async def get_onboarding_step(self, user_id: int) -> int:
        """Получить текущий шаг онбординга"""
        user = await self.session.get(User, user_id)
        if user:
            return user.onboarding_step
        return 0
    
    async def set_onboarding_step(self, user_id: int, step: int) -> bool:
        """Установить шаг онбординга"""
        user = await self.session.get(User, user_id)
        if user:
            user.onboarding_step = step
            await self.session.flush()
            return True
        return False
    
    async def is_onboarding_complete(self, user_id: int) -> bool:
        """Проверить, завершён ли онбординг"""
        user = await self.session.get(User, user_id)
        if user:
            return user.onboarding_step >= 7
        return False
