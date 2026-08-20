import logging
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories.user_repository import UserRepository
from database.repositories.pet_repository import PetRepository
from database.repositories.cosmetic_repository import CosmeticRepository
from services.data_loader import data_loader
from services.chat_service import ChatService
from services.payment_service import PaymentService

logger = logging.getLogger(__name__)


class CosmeticService:
    """Сервис для работы с косметикой и рамками"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.pet_repo = PetRepository(session)
        self.cosmetic_repo = CosmeticRepository(session)
        self.payment_service = PaymentService(session)
        self.cosmetics_data = data_loader.get("cosmetics", {}).get("cosmetics", [])
        self.frames_data = data_loader.get("frames", {}).get("frames", [])
    
    # === КОСМЕТИКА ===
    
    async def get_all_cosmetics(self) -> List[Dict[str, Any]]:
        """Получить все доступные косметические предметы"""
        return self.cosmetics_data
    
    async def get_cosmetic(self, cosmetic_id: str) -> Optional[Dict[str, Any]]:
        """Получить косметический предмет по ID"""
        for item in self.cosmetics_data:
            if item.get("id") == cosmetic_id:
                return item
        return None
    
    async def get_pet_cosmetics(self, pet_id: int) -> List[Dict[str, Any]]:
        """Получить разблокированную косметику питомца"""
        cosmetics = await self.cosmetic_repo.get_all_cosmetics(pet_id)
        
        result = []
        for c in cosmetics:
            cosmetic_data = await self.get_cosmetic(c.cosmetic_id)
            if cosmetic_data:
                result.append({
                    "id": c.cosmetic_id,
                    "name": cosmetic_data.get("name"),
                    "emoji": cosmetic_data.get("emoji"),
                    "category": cosmetic_data.get("category"),
                    "rarity": cosmetic_data.get("rarity"),
                    "unlocked_at": c.unlocked_at.strftime("%d.%m.%Y")
                })
        
        return result
    
    async def buy_cosmetic(self, user_id: int, pet_id: int, cosmetic_id: str) -> Dict[str, Any]:
        """
        Купить косметику за лапки
        
        Args:
            user_id: Telegram ID пользователя
            pet_id: ID питомца
            cosmetic_id: ID косметики
        
        Returns:
            {
                "success": bool,
                "message": str
            }
        """
        # Проверяем косметику
        cosmetic = await self.get_cosmetic(cosmetic_id)
        if not cosmetic:
            return {"success": False, "message": "Такой косметики не существует"}
        
        # Проверяем пользователя
        user = await self.user_repo.get_by_telegram_id(user_id)
        if not user:
            return {"success": False, "message": "Пользователь не найден"}
        
        # Проверяем питомца
        pet = await self.pet_repo.get_by_id(pet_id)
        if not pet or pet.user_id != user.id:
            return {"success": False, "message": "Питомец не найден"}
        
        # Проверяем, не куплена ли уже
        if await self.cosmetic_repo.has_cosmetic(pet_id, cosmetic_id):
            return {"success": False, "message": "Эта косметика уже куплена"}
        
        # Проверяем баланс
        price = cosmetic.get("price", 0)
        if user.premium_currency < price:
            return {
                "success": False,
                "message": f"Недостаточно 💎! Нужно: {price}, у тебя: {user.premium_currency}",
                "need": price,
                "have": user.premium_currency
            }
        
        # Списываем лапки
        user.premium_currency -= price
        
        # Разблокируем косметику
        await self.cosmetic_repo.unlock_cosmetic(pet_id, cosmetic_id)
        
        # Если это первая купленная косметика - надеваем её
        pet_cosmetics = await self.cosmetic_repo.get_all_cosmetics(pet_id)
        if len(pet_cosmetics) == 1:
            pet.cosmetic_id = cosmetic_id
            await self.session.flush()
        
        await self.session.flush()
        
        logger.info(f"Пользователь {user_id} купил косметику {cosmetic_id} за {price} 💎")
        
        return {
            "success": True,
            "message": f"✅ {cosmetic.get('emoji')} {cosmetic.get('name')} куплена!",
            "cosmetic": cosmetic,
            "balance": user.premium_currency
        }
    
    async def apply_cosmetic(self, user_id: int, pet_id: int, cosmetic_id: str) -> Dict[str, Any]:
        """Надеть косметику на питомца"""
        pet = await self.pet_repo.get_by_id(pet_id)
        if not pet or pet.user_id != (await self.user_repo.get_by_telegram_id(user_id)).id:
            return {"success": False, "message": "Питомец не найден"}
        
        if not await self.cosmetic_repo.has_cosmetic(pet_id, cosmetic_id):
            return {"success": False, "message": "Эта косметика не куплена"}
        
        await self.cosmetic_repo.apply_cosmetic(pet_id, cosmetic_id)
        await self.session.flush()
        
        cosmetic = await self.get_cosmetic(cosmetic_id)
        
        return {
            "success": True,
            "message": f"✅ {cosmetic.get('emoji')} {cosmetic.get('name')} надета!",
            "cosmetic": cosmetic
        }
    
    async def remove_cosmetic(self, user_id: int, pet_id: int) -> Dict[str, Any]:
        """Снять косметику с питомца"""
        pet = await self.pet_repo.get_by_id(pet_id)
        if not pet or pet.user_id != (await self.user_repo.get_by_telegram_id(user_id)).id:
            return {"success": False, "message": "Питомец не найден"}
        
        await self.cosmetic_repo.remove_cosmetic(pet_id)
        await self.session.flush()
        
        return {
            "success": True,
            "message": "✅ Косметика снята!"
        }
    
    # === РАМКИ ===
    
    async def get_all_frames(self) -> List[Dict[str, Any]]:
        """Получить все доступные рамки"""
        return self.frames_data
    
    async def get_frame(self, frame_id: str) -> Optional[Dict[str, Any]]:
        """Получить рамку по ID"""
        for frame in self.frames_data:
            if frame.get("id") == frame_id:
                return frame
        return None
    
    async def get_pet_frames(self, pet_id: int) -> List[Dict[str, Any]]:
        """Получить разблокированные рамки питомца"""
        frames = await self.cosmetic_repo.get_all_frames(pet_id)
        
        result = []
        for f in frames:
            frame_data = await self.get_frame(f.frame_id)
            if frame_data:
                result.append({
                    "id": f.frame_id,
                    "name": frame_data.get("name"),
                    "emoji": frame_data.get("emoji"),
                    "rarity": frame_data.get("rarity"),
                    "unlocked_at": f.unlocked_at.strftime("%d.%m.%Y")
                })
        
        return result
    
    async def buy_frame(self, user_id: int, pet_id: int, frame_id: str) -> Dict[str, Any]:
        """Купить рамку за лапки"""
        frame = await self.get_frame(frame_id)
        if not frame:
            return {"success": False, "message": "Такой рамки не существует"}
        
        user = await self.user_repo.get_by_telegram_id(user_id)
        if not user:
            return {"success": False, "message": "Пользователь не найден"}
        
        pet = await self.pet_repo.get_by_id(pet_id)
        if not pet or pet.user_id != user.id:
            return {"success": False, "message": "Питомец не найден"}
        
        if await self.cosmetic_repo.has_frame(pet_id, frame_id):
            return {"success": False, "message": "Эта рамка уже куплена"}
        
        price = frame.get("price", 0)
        if user.premium_currency < price:
            return {
                "success": False,
                "message": f"Недостаточно 💎! Нужно: {price}, у тебя: {user.premium_currency}",
                "need": price,
                "have": user.premium_currency
            }
        
        user.premium_currency -= price
        await self.cosmetic_repo.unlock_frame(pet_id, frame_id)
        
        # Если это первая купленная рамка - надеваем её
        pet_frames = await self.cosmetic_repo.get_all_frames(pet_id)
        if len(pet_frames) == 1:
            pet.frame_id = frame_id
            await self.session.flush()
        
        await self.session.flush()
        
        logger.info(f"Пользователь {user_id} купил рамку {frame_id} за {price} 💎")
        
        return {
            "success": True,
            "message": f"✅ {frame.get('emoji')} {frame.get('name')} куплена!",
            "frame": frame,
            "balance": user.premium_currency
        }
    
    async def apply_frame(self, user_id: int, pet_id: int, frame_id: str) -> Dict[str, Any]:
        """Надеть рамку на питомца"""
        pet = await self.pet_repo.get_by_id(pet_id)
        if not pet or pet.user_id != (await self.user_repo.get_by_telegram_id(user_id)).id:
            return {"success": False, "message": "Питомец не найден"}
        
        if not await self.cosmetic_repo.has_frame(pet_id, frame_id):
            return {"success": False, "message": "Эта рамка не куплена"}
        
        await self.cosmetic_repo.apply_frame(pet_id, frame_id)
        await self.session.flush()
        
        frame = await self.get_frame(frame_id)
        
        return {
            "success": True,
            "message": f"✅ {frame.get('emoji')} {frame.get('name')} надета!",
            "frame": frame
        }
    
    async def remove_frame(self, user_id: int, pet_id: int) -> Dict[str, Any]:
        """Снять рамку с питомца"""
        pet = await self.pet_repo.get_by_id(pet_id)
        if not pet or pet.user_id != (await self.user_repo.get_by_telegram_id(user_id)).id:
            return {"success": False, "message": "Питомец не найден"}
        
        await self.cosmetic_repo.remove_frame(pet_id)
        await self.session.flush()
        
        return {
            "success": True,
            "message": "✅ Рамка снята!"
        }