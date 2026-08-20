import logging
from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories.user_repository import UserRepository
from database.repositories.inventory_repository import InventoryRepository
from services.data_loader import data_loader

logger = logging.getLogger(__name__)


class EconomyService:
    """Сервис для работы с экономикой"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.inventory_repo = InventoryRepository(session)
        self.foods = data_loader.get("foods", {})
    
    async def buy_item(self, user_id: int, item_id: str, quantity: int = 1) -> dict:
        """Покупка предмета"""
        user = await self.user_repo.get_by_telegram_id(user_id)
        if not user:
            return {"success": False, "message": "Пользователь не найден"}
        
        food = self.foods.get(item_id)
        if not food:
            return {"success": False, "message": "Такой еды не существует"}
        
        price = food.get("coin_value", 0) * quantity
        if user.coins < price:
            return {
                "success": False,
                "message": f"Недостаточно монет! Нужно: {price}, у вас: {user.coins}"
            }
        
        # Списываем монеты
        user.coins -= price
        
        # Добавляем в инвентарь
        await self.inventory_repo.add_item(user.id, item_id, quantity)
        
        await self.session.flush()
        
        logger.info(f"Пользователь {user_id} купил {quantity}x {item_id} за {price} монет")
        
        return {
            "success": True,
            "message": f"✅ Куплено {food.get('emoji', '')} {food.get('name', item_id)} x{quantity} за {price} монет",
            "item": food,
            "quantity": quantity,
            "price": price,
            "remaining_coins": user.coins
        }
    
    async def sell_item(self, user_id: int, item_id: str, quantity: int = 1) -> dict:
        """Продажа предмета"""
        user = await self.user_repo.get_by_telegram_id(user_id)
        if not user:
            return {"success": False, "message": "Пользователь не найден"}
        
        food = self.foods.get(item_id)
        if not food:
            return {"success": False, "message": "Такой еды не существует"}
        
        # Проверяем наличие в инвентаре
        if not await self.inventory_repo.has_item(user.id, item_id, quantity):
            return {"success": False, "message": f"У вас нет {quantity} шт. {food.get('name', item_id)}"}
        
        sell_price = food.get("sell_price", 0) * quantity
        
        # Удаляем из инвентаря
        await self.inventory_repo.remove_item(user.id, item_id, quantity)
        
        # Добавляем монеты
        user.coins += sell_price
        
        await self.session.flush()
        
        logger.info(f"Пользователь {user_id} продал {quantity}x {item_id} за {sell_price} монет")
        
        return {
            "success": True,
            "message": f"💰 Продано {food.get('emoji', '')} {food.get('name', item_id)} x{quantity} за {sell_price} монет",
            "item": food,
            "quantity": quantity,
            "price": sell_price,
            "remaining_coins": user.coins
        }
    
    async def get_balance(self, user_id: int) -> dict:
        """Получение баланса"""
        user = await self.user_repo.get_by_telegram_id(user_id)
        if not user:
            return {"success": False, "message": "Пользователь не найден"}
        
        return {
            "success": True,
            "coins": user.coins
        }