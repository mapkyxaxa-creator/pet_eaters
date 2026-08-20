from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.sql import func
from database.models import Pet, User


class PetRepository:
    """Репозиторий для работы с питомцами"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_id(self, pet_id: int) -> Optional[Pet]:
        """Получение питомца по ID"""
        return await self.session.get(Pet, pet_id)
    
    async def get_by_user_id(self, user_id: int) -> Optional[Pet]:
        """Получение питомца по ID пользователя"""
        result = await self.session.execute(
            select(Pet).where(Pet.user_id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_game_id(self, game_id: str) -> Optional[Pet]:
        """Получение питомца по игровому ID"""
        result = await self.session.execute(
            select(Pet).where(Pet.game_id == game_id)
        )
        return result.scalar_one_or_none()
    
    async def get_all_by_user_id(self, user_id: int) -> List[Pet]:
        """Получение всех питомцев пользователя"""
        result = await self.session.execute(
            select(Pet).where(Pet.user_id == user_id)
        )
        return result.scalars().all()
    
    async def create(
        self,
        user_id: int,
        name: str,
        photo_file_id: str,
        character_id: str,
        game_id: str,
        stomach_capacity: int = 100,
        energy: int = 100,
        happiness: int = 50,
        luck: float = 0.05,
        smell: int = 10,
        eating_speed: int = 10,
    ) -> Pet:
        """Создание нового питомца"""
        pet = Pet(
            user_id=user_id,
            name=name,
            photo_file_id=photo_file_id,
            character_id=character_id,
            game_id=game_id,
            stomach_capacity=stomach_capacity,
            energy=energy,
            happiness=happiness,
            luck=luck,
            smell=smell,
            eating_speed=eating_speed,
        )
        self.session.add(pet)
        await self.session.flush()
        await self.session.refresh(pet)
        return pet
    
    async def update(self, pet: Pet) -> Pet:
        """Обновление питомца"""
        await self.session.flush()
        await self.session.refresh(pet)
        return pet
    
    async def has_pet(self, user_id: int) -> bool:
        """Проверка наличия питомца у пользователя"""
        result = await self.session.execute(
            select(Pet).where(Pet.user_id == user_id).limit(1)
        )
        return result.scalar_one_or_none() is not None
    
    async def get_by_name(self, name: str) -> Optional[Pet]:
        """Получение питомца по имени"""
        result = await self.session.execute(
            select(Pet).where(Pet.name == name)
        )
        return result.scalar_one_or_none()
    
    async def get_top_by_level(self, limit: int = 10) -> List[Pet]:
        """Получить топ питомцев по уровню"""
        result = await self.session.execute(
            select(Pet)
            .order_by(desc(Pet.level), desc(Pet.experience))
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_top_by_likes(self, limit: int = 10) -> List[Pet]:
        """Получить топ питомцев по лайкам"""
        result = await self.session.execute(
            select(Pet)
            .order_by(desc(Pet.total_likes))
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_random_pet(self, exclude_pet_id: int) -> Optional[Pet]:
        """Получить случайного питомца (не своего)"""
        result = await self.session.execute(
            select(Pet)
            .where(Pet.id != exclude_pet_id)
            .order_by(func.random())
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    async def get_random_pets(self, exclude_pet_id: int, limit: int = 2) -> List[Pet]:
        """Получить несколько случайных питомцев (для ленты)"""
        result = await self.session.execute(
            select(Pet)
            .where(Pet.id != exclude_pet_id)
            .order_by(func.random())
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_all(self) -> List[Pet]:
        """Получить всех питомцев"""
        result = await self.session.execute(select(Pet))
        return result.scalars().all()
    
    async def get_active_users_pets(self, since_date) -> List[Pet]:
        """
        Получить питомцев активных пользователей
        
        Args:
            since_date: дата, после которой пользователь был активен
        """
        result = await self.session.execute(
            select(Pet)
            .join(Pet.user)
            .where(User.last_active >= since_date)
        )
        return result.scalars().all()