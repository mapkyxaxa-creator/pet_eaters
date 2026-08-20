from typing import Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update, delete
from database.models import QuestProgress


class QuestRepository:
    """Репозиторий для работы с заданиями"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_user_id(self, user_id: int) -> List[QuestProgress]:
        """Получить все задания пользователя"""
        result = await self.session.execute(
            select(QuestProgress).where(QuestProgress.user_id == user_id)
        )
        return result.scalars().all()
    
    async def get_by_id(self, user_id: int, quest_id: str) -> Optional[QuestProgress]:
        """Получить конкретное задание"""
        result = await self.session.execute(
            select(QuestProgress).where(
                and_(
                    QuestProgress.user_id == user_id,
                    QuestProgress.quest_id == quest_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def create_or_update(
        self,
        user_id: int,
        quest_id: str,
        progress: int = 0,
        completed: bool = False
    ) -> QuestProgress:
        """Создать или обновить задание"""
        quest = await self.get_by_id(user_id, quest_id)
        
        if quest:
            quest.progress = progress
            quest.completed = completed
            if completed and not quest.completed_at:
                quest.completed_at = datetime.utcnow()
            await self.session.flush()
            return quest
        
        quest = QuestProgress(
            user_id=user_id,
            quest_id=quest_id,
            progress=progress,
            completed=completed,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow() if completed else None
        )
        self.session.add(quest)
        await self.session.flush()
        return quest
    
    async def update_progress(self, user_id: int, quest_id: str, progress: int) -> QuestProgress:
        """Обновить прогресс задания"""
        quest = await self.get_by_id(user_id, quest_id)
        if quest:
            quest.progress = progress
            await self.session.flush()
        return quest
    
    async def complete_quest(self, user_id: int, quest_id: str) -> bool:
        """Отметить задание как выполненное"""
        quest = await self.get_by_id(user_id, quest_id)
        if quest and not quest.completed:
            quest.completed = True
            quest.completed_at = datetime.utcnow()
            await self.session.flush()
            return True
        return False
    
    async def reset_daily_quests(self, user_id: int) -> None:
        """Сбросить ежедневные задания для конкретного пользователя"""
        await self.session.execute(
            delete(QuestProgress).where(QuestProgress.user_id == user_id)
        )
        await self.session.flush()
    
    async def claim_reward(self, user_id: int, quest_id: str) -> bool:
        """Забрать награду за задание"""
        quest = await self.get_by_id(user_id, quest_id)
        if not quest or not quest.completed or quest.claimed:
            return False
        
        quest.claimed = True
        quest.claimed_at = datetime.utcnow()
        await self.session.flush()
        return True
    
    async def reset_all_daily_quests(self) -> None:
        """Сбросить ежедневные задания для всех пользователей (с проверкой даты)"""
        now = datetime.utcnow()
        today = now.date()
        
        # Получаем все задания
        result = await self.session.execute(select(QuestProgress))
        all_quests = result.scalars().all()
        
        for quest in all_quests:
            # Если задание создано не сегодня — удаляем
            if quest.started_at.date() != today:
                await self.session.delete(quest)
        
        await self.session.flush()