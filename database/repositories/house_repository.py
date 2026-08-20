import json
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta  # <-- ПЕРЕНЕСЕНО В НАЧАЛО
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from database.models import (
    House, HouseRoom, HouseFurniture, HouseDecoration, 
    HouseVisit, HouseUpgradeLog, Pet
)


class HouseRepository:
    """Репозиторий для работы с домами"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    # === HOUSE ===
    
    async def get_by_pet_id(self, pet_id: int) -> Optional[House]:
        """Получить дом по ID питомца"""
        result = await self.session.execute(
            select(House).where(House.pet_id == pet_id)
        )
        return result.scalar_one_or_none()
    
    async def create(self, pet_id: int, template_id: str = "basic") -> House:
        """Создать новый дом для питомца"""
        house = House(
            pet_id=pet_id,
            template_id=template_id,
            level=1
        )
        self.session.add(house)
        await self.session.flush()
        return house
    
    async def update(self, house: House) -> House:
        """Обновить дом"""
        await self.session.flush()
        await self.session.refresh(house)
        return house
    
    async def upgrade_level(self, house: House, new_level: int) -> House:
        """Повысить уровень дома"""
        house.level = new_level
        await self.session.flush()
        await self.session.refresh(house)
        return house
    
    async def update_bonuses(self, house: House) -> House:
        """Обновить бонусы дома на основе комнат и мебели"""
        await self.session.flush()
        await self.session.refresh(house)
        return house
    
    async def get_all_visitable(self, exclude_pet_id: int) -> List[House]:
        """Получить все дома, доступные для посещения (кроме своего)"""
        result = await self.session.execute(
            select(House)
            .join(Pet, House.pet_id == Pet.id)
            .where(Pet.id != exclude_pet_id)
            .order_by(func.random())
            .limit(20)
        )
        return result.scalars().all()
    
    async def get_by_template(self, template_id: str) -> List[House]:
        """Получить дома по шаблону"""
        result = await self.session.execute(
            select(House).where(House.template_id == template_id)
        )
        return result.scalars().all()
    
    # === ROOMS ===
    
    async def get_room(self, house_id: int, room_type: str) -> Optional[HouseRoom]:
        """Получить комнату по типу"""
        result = await self.session.execute(
            select(HouseRoom).where(
                HouseRoom.house_id == house_id,
                HouseRoom.room_type == room_type
            )
        )
        return result.scalar_one_or_none()
    
    async def get_rooms(self, house_id: int) -> List[HouseRoom]:
        """Получить все комнаты дома"""
        result = await self.session.execute(
            select(HouseRoom).where(HouseRoom.house_id == house_id)
        )
        return result.scalars().all()
    
    async def create_room(self, house_id: int, room_type: str, is_unlocked: bool = False) -> HouseRoom:
        """Создать комнату"""
        room = HouseRoom(
            house_id=house_id,
            room_type=room_type,
            is_unlocked=is_unlocked
        )
        self.session.add(room)
        await self.session.flush()
        return room
    
    async def unlock_room(self, room: HouseRoom) -> HouseRoom:
        """Разблокировать комнату"""
        room.is_unlocked = True
        await self.session.flush()
        await self.session.refresh(room)
        return room
    
    async def update_room_bonuses(self, room: HouseRoom, bonuses: Dict) -> HouseRoom:
        """Обновить бонусы комнаты"""
        room.bonuses = json.dumps(bonuses)
        await self.session.flush()
        await self.session.refresh(room)
        return room
    
    # === FURNITURE ===
    
    async def get_furniture(self, room_id: int, furniture_id: str) -> Optional[HouseFurniture]:
        """Получить мебель в комнате"""
        result = await self.session.execute(
            select(HouseFurniture).where(
                HouseFurniture.room_id == room_id,
                HouseFurniture.furniture_id == furniture_id
            )
        )
        return result.scalar_one_or_none()
    
    async def get_furniture_by_room(self, room_id: int) -> List[HouseFurniture]:
        """Получить всю мебель в комнате"""
        result = await self.session.execute(
            select(HouseFurniture).where(HouseFurniture.room_id == room_id)
        )
        return result.scalars().all()
    
    async def get_furniture_by_house(self, house_id: int) -> List[HouseFurniture]:
        """Получить всю мебель в доме"""
        result = await self.session.execute(
            select(HouseFurniture)
            .join(HouseRoom, HouseFurniture.room_id == HouseRoom.id)
            .where(HouseRoom.house_id == house_id)
        )
        return result.scalars().all()
    
    async def add_furniture(self, room_id: int, furniture_id: str, bonuses: Dict) -> HouseFurniture:
        """Добавить мебель в комнату"""
        existing = await self.get_furniture(room_id, furniture_id)
        if existing:
            existing.quantity += 1
            await self.session.flush()
            await self.session.refresh(existing)
            return existing
        
        furniture = HouseFurniture(
            room_id=room_id,
            furniture_id=furniture_id,
            quantity=1,
            bonuses=json.dumps(bonuses)
        )
        self.session.add(furniture)
        await self.session.flush()
        return furniture
    
    async def remove_furniture(self, room_id: int, furniture_id: str) -> bool:
        """Удалить мебель из комнаты"""
        furniture = await self.get_furniture(room_id, furniture_id)
        if not furniture:
            return False
        
        if furniture.quantity > 1:
            furniture.quantity -= 1
            await self.session.flush()
        else:
            await self.session.delete(furniture)
            await self.session.flush()
        return True
    
    # === DECORATIONS ===
    
    async def get_decorations(self, house_id: int) -> List[HouseDecoration]:
        """Получить все декорации дома"""
        result = await self.session.execute(
            select(HouseDecoration).where(
                HouseDecoration.house_id == house_id,
                HouseDecoration.is_active == True
            )
        )
        return result.scalars().all()
    
    async def add_decoration(self, house_id: int, decoration_id: str) -> HouseDecoration:
        """Добавить декорацию"""
        decoration = HouseDecoration(
            house_id=house_id,
            decoration_id=decoration_id,
            is_active=True
        )
        self.session.add(decoration)
        await self.session.flush()
        return decoration
    
    async def remove_decoration(self, house_id: int, decoration_id: str) -> bool:
        """Удалить декорацию"""
        result = await self.session.execute(
            select(HouseDecoration).where(
                HouseDecoration.house_id == house_id,
                HouseDecoration.decoration_id == decoration_id,
                HouseDecoration.is_active == True
            )
        )
        decoration = result.scalar_one_or_none()
        if decoration:
            decoration.is_active = False
            await self.session.flush()
            return True
        return False
    
    # === VISITS ===
    
    async def has_visited_today(self, house_id: int, visitor_pet_id: int) -> bool:
        """Проверить, посещал ли питомец дом сегодня"""
        today = datetime.utcnow().date()
        result = await self.session.execute(
            select(HouseVisit).where(
                HouseVisit.house_id == house_id,
                HouseVisit.visitor_pet_id == visitor_pet_id,
                func.date(HouseVisit.visit_date) == today
            )
        )
        return result.scalar_one_or_none() is not None
    
    async def add_visit(self, house_id: int, visitor_pet_id: int, 
                        reward_coins: int = 0, reward_happiness: int = 0) -> HouseVisit:
        """Добавить визит"""
        visit = HouseVisit(
            house_id=house_id,
            visitor_pet_id=visitor_pet_id,
            reward_coins=reward_coins,
            reward_happiness=reward_happiness
        )
        self.session.add(visit)
        await self.session.flush()
        
        house = await self.session.get(House, house_id)
        if house:
            house.total_visits += 1
            await self.session.flush()
        
        return visit
    
    async def get_visits_count(self, house_id: int, days: int = 7) -> int:
        """Получить количество посещений за последние N дней"""
        since_date = datetime.utcnow() - timedelta(days=days)
        result = await self.session.execute(
            select(func.count(HouseVisit.id)).where(
                HouseVisit.house_id == house_id,
                HouseVisit.visit_date >= since_date
            )
        )
        return result.scalar() or 0
    
    # === UPGRADE LOGS ===
    
    async def add_upgrade_log(self, house_id: int, upgrade_type: str,
                              old_value: str, new_value: str,
                              cost_coins: int = 0, cost_premium: int = 0) -> HouseUpgradeLog:
        """Записать лог улучшения"""
        log = HouseUpgradeLog(
            house_id=house_id,
            upgrade_type=upgrade_type,
            old_value=old_value,
            new_value=new_value,
            cost_coins=cost_coins,
            cost_premium=cost_premium
        )
        self.session.add(log)
        await self.session.flush()
        return log