from typing import Optional, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from database.models import Inventory


class InventoryRepository:
    """Репозиторий для работы с инвентарем"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_item(self, user_id: int, item_id: str) -> Optional[Inventory]:
        """Получение предмета в инвентаре"""
        result = await self.session.execute(
            select(Inventory).where(
                Inventory.user_id == user_id,
                Inventory.item_id == item_id
            )
        )
        return result.scalar_one_or_none()
    
    async def get_all_items(self, user_id: int) -> List[Inventory]:
        """Получение всех предметов пользователя"""
        result = await self.session.execute(
            select(Inventory).where(Inventory.user_id == user_id)
        )
        return result.scalars().all()
    
    async def add_item(self, user_id: int, item_id: str, quantity: int = 1) -> Inventory:
        """Добавление предмета в инвентарь"""
        item = await self.get_item(user_id, item_id)
        if item:
            item.quantity += quantity
        else:
            item = Inventory(
                user_id=user_id,
                item_id=item_id,
                quantity=quantity
            )
            self.session.add(item)
        await self.session.flush()
        await self.session.refresh(item)
        return item
    
    async def remove_item(self, user_id: int, item_id: str, quantity: int = 1) -> bool:
        """Удаление предмета из инвентаря"""
        item = await self.get_item(user_id, item_id)
        if not item or item.quantity < quantity:
            return False
        
        item.quantity -= quantity
        if item.quantity <= 0:
            await self.session.delete(item)
        await self.session.flush()
        return True
    
    async def has_item(self, user_id: int, item_id: str, quantity: int = 1) -> bool:
        """Проверка наличия предмета"""
        item = await self.get_item(user_id, item_id)
        return item is not None and item.quantity >= quantity