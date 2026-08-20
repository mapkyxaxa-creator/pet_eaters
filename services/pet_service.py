import logging
import random
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories.pet_repository import PetRepository
from database.models import Pet
from services.data_loader import data_loader

logger = logging.getLogger(__name__)


class PetService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.pet_repo = PetRepository(session)
        self.balance = data_loader.get_balance()
    
    def generate_game_id(self, name: str) -> str:
        """Генерация уникального игрового ID"""
        prefix = name[:3].upper()
        number = random.randint(1000, 99999)
        return f"{prefix}-{number}"
    
    async def create_unique_game_id(self, name: str) -> str:
        """Создать уникальный game_id (с проверкой)"""
        while True:
            game_id = self.generate_game_id(name)
            existing = await self.pet_repo.get_by_game_id(game_id)
            if not existing:
                return game_id
    
    async def create_pet(
        self,
        user_id: int,
        name: str,
        photo_file_id: str,
        character_id: str,
        character_bonus: Optional[Dict] = None
    ) -> Pet:
        """Создание нового питомца"""
        starting_stomach = self.balance.get("starting_stomach", 100)
        starting_energy = self.balance.get("starting_energy", 100)
        starting_happiness = self.balance.get("starting_happiness", 50)
        starting_luck = self.balance.get("starting_luck", 0.05)
        starting_smell = self.balance.get("starting_smell", 10)
        starting_eating_speed = self.balance.get("starting_eating_speed", 10)
        
        # Генерируем уникальный game_id
        game_id = await self.create_unique_game_id(name)
        
        pet = await self.pet_repo.create(
            user_id=user_id,
            name=name,
            photo_file_id=photo_file_id,
            character_id=character_id,
            game_id=game_id,
            stomach_capacity=starting_stomach,
            energy=starting_energy,
            happiness=starting_happiness,
            luck=starting_luck,
            smell=starting_smell,
            eating_speed=starting_eating_speed,
        )
        
        logger.info(f"Создан питомец {pet.id} (имя: {pet.name}, game_id: {game_id}) для пользователя {user_id}")
        return pet