from typing import Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, delete
from database.models import PetCosmetic, PetFrame, Pet


class CosmeticRepository:
    """Репозиторий для работы с косметикой"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    # === КОСМЕТИКА ===
    
    async def unlock_cosmetic(self, pet_id: int, cosmetic_id: str) -> PetCosmetic:
        """Разблокировать косметику для питомца"""
        # Проверяем, не разблокирована ли уже
        existing = await self.get_cosmetic(pet_id, cosmetic_id)
        if existing:
            return existing
        
        cosmetic = PetCosmetic(
            pet_id=pet_id,
            cosmetic_id=cosmetic_id,
            unlocked_at=datetime.utcnow()
        )
        self.session.add(cosmetic)
        await self.session.flush()
        return cosmetic
    
    async def get_cosmetic(self, pet_id: int, cosmetic_id: str) -> Optional[PetCosmetic]:
        """Получить конкретную косметику"""
        result = await self.session.execute(
            select(PetCosmetic).where(
                and_(
                    PetCosmetic.pet_id == pet_id,
                    PetCosmetic.cosmetic_id == cosmetic_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_all_cosmetics(self, pet_id: int) -> List[PetCosmetic]:
        """Получить всю разблокированную косметику питомца"""
        result = await self.session.execute(
            select(PetCosmetic)
            .where(PetCosmetic.pet_id == pet_id)
            .order_by(PetCosmetic.unlocked_at)
        )
        return result.scalars().all()
    
    async def has_cosmetic(self, pet_id: int, cosmetic_id: str) -> bool:
        """Проверить, разблокирована ли косметика"""
        cosmetic = await self.get_cosmetic(pet_id, cosmetic_id)
        return cosmetic is not None
    
    async def apply_cosmetic(self, pet_id: int, cosmetic_id: str) -> bool:
        """Надеть косметику на питомца"""
        pet = await self.session.get(Pet, pet_id)
        if not pet:
            return False
        
        # Проверяем, что косметика разблокирована
        if not await self.has_cosmetic(pet_id, cosmetic_id):
            return False
        
        pet.cosmetic_id = cosmetic_id
        await self.session.flush()
        return True
    
    async def remove_cosmetic(self, pet_id: int) -> bool:
        """Снять косметику с питомца"""
        pet = await self.session.get(Pet, pet_id)
        if not pet:
            return False
        pet.cosmetic_id = None
        await self.session.flush()
        return True
    
    # === РАМКИ ===
    
    async def unlock_frame(self, pet_id: int, frame_id: str) -> PetFrame:
        """Разблокировать рамку для питомца"""
        existing = await self.get_frame(pet_id, frame_id)
        if existing:
            return existing
        
        frame = PetFrame(
            pet_id=pet_id,
            frame_id=frame_id,
            unlocked_at=datetime.utcnow()
        )
        self.session.add(frame)
        await self.session.flush()
        return frame
    
    async def get_frame(self, pet_id: int, frame_id: str) -> Optional[PetFrame]:
        """Получить конкретную рамку"""
        result = await self.session.execute(
            select(PetFrame).where(
                and_(
                    PetFrame.pet_id == pet_id,
                    PetFrame.frame_id == frame_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_all_frames(self, pet_id: int) -> List[PetFrame]:
        """Получить все разблокированные рамки питомца"""
        result = await self.session.execute(
            select(PetFrame)
            .where(PetFrame.pet_id == pet_id)
            .order_by(PetFrame.unlocked_at)
        )
        return result.scalars().all()
    
    async def has_frame(self, pet_id: int, frame_id: str) -> bool:
        """Проверить, разблокирована ли рамка"""
        frame = await self.get_frame(pet_id, frame_id)
        return frame is not None
    
    async def apply_frame(self, pet_id: int, frame_id: str) -> bool:
        """Надеть рамку на питомца"""
        pet = await self.session.get(Pet, pet_id)
        if not pet:
            return False
        
        if not await self.has_frame(pet_id, frame_id):
            return False
        
        pet.frame_id = frame_id
        await self.session.flush()
        return True
    
    async def remove_frame(self, pet_id: int) -> bool:
        """Снять рамку с питомца"""
        pet = await self.session.get(Pet, pet_id)
        if not pet:
            return False
        pet.frame_id = None
        await self.session.flush()
        return True