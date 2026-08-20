import json
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from database.models import User, BattlePass


class PremiumRepository:
    """Репозиторий для работы с Premium и Battle Pass"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    # === PREMIUM ===
    
    async def activate_premium(self, user_id: int, duration_days: int = 30) -> Optional[User]:
        """Активировать Premium подписку"""
        user = await self.session.get(User, user_id)
        if not user:
            return None
        
        now = datetime.utcnow()
        if user.premium_until and user.premium_until > now:
            user.premium_until = user.premium_until + timedelta(days=duration_days)
        else:
            user.premium_until = now + timedelta(days=duration_days)
        
        await self.session.flush()
        return user
    
    async def deactivate_premium(self, user_id: int) -> Optional[User]:
        """Деактивировать Premium подписку"""
        user = await self.session.get(User, user_id)
        if not user:
            return None
        
        user.premium_until = None
        await self.session.flush()
        return user
    
    async def is_premium_active(self, user_id: int) -> bool:
        """Проверить, активен ли Premium"""
        user = await self.session.get(User, user_id)
        if not user or not user.premium_until:
            return False
        return datetime.utcnow() < user.premium_until
    
    async def get_premium_remaining_days(self, user_id: int) -> int:
        """Получить оставшиеся дни Premium"""
        user = await self.session.get(User, user_id)
        if not user or not user.premium_until:
            return 0
        
        now = datetime.utcnow()
        if now > user.premium_until:
            return 0
        
        delta = user.premium_until - now
        return delta.days
    
    # === BATTLE PASS ===
    
    async def get_or_create_battlepass(self, user_id: int, season_id: int = 1) -> BattlePass:
        """Получить или создать Battle Pass"""
        result = await self.session.execute(
            select(BattlePass).where(
                and_(
                    BattlePass.user_id == user_id,
                    BattlePass.season_id == season_id
                )
            )
        )
        battlepass = result.scalar_one_or_none()
        
        if not battlepass:
            battlepass = BattlePass(
                user_id=user_id,
                season_id=season_id,
                level=0,
                xp=0,
                premium_unlocked=False,
                claimed_rewards="{}"
            )
            self.session.add(battlepass)
            await self.session.flush()
        
        return battlepass
    
    async def add_battlepass_xp(self, user_id: int, xp: int, season_id: int = 1) -> BattlePass:
        """Добавить XP в Battle Pass"""
        battlepass = await self.get_or_create_battlepass(user_id, season_id)
        battlepass.xp += xp
        
        while battlepass.xp >= 100:
            battlepass.xp -= 100
            battlepass.level += 1
        
        await self.session.flush()
        return battlepass
    
    async def unlock_premium_battlepass(self, user_id: int, season_id: int = 1) -> Optional[BattlePass]:
        """Разблокировать Premium Battle Pass"""
        battlepass = await self.get_or_create_battlepass(user_id, season_id)
        if battlepass.premium_unlocked:
            return battlepass
        
        battlepass.premium_unlocked = True
        await self.session.flush()
        return battlepass
    
    async def claim_battlepass_reward(self, user_id: int, level: int, season_id: int = 1) -> bool:
        """Отметить получение награды за уровень Battle Pass"""
        battlepass = await self.get_or_create_battlepass(user_id, season_id)
        
        if battlepass.level < level:
            return False
        
        claimed = json.loads(battlepass.claimed_rewards or "{}")
        if str(level) in claimed:
            return False
        
        claimed[str(level)] = True
        battlepass.claimed_rewards = json.dumps(claimed)
        await self.session.flush()
        return True
    
    async def get_battlepass_progress(self, user_id: int, season_id: int = 1) -> dict:
        """Получить прогресс Battle Pass"""
        battlepass = await self.get_or_create_battlepass(user_id, season_id)
        
        return {
            "level": battlepass.level,
            "xp": battlepass.xp,
            "xp_to_next": 100,
            "premium_unlocked": battlepass.premium_unlocked,
            "claimed_rewards": json.loads(battlepass.claimed_rewards or "{}")
        }