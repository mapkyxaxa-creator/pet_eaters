"""Репозиторий для работы с соревнованиями"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select, func, and_, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from database.models import Season, Competition, CompetitionResult


class CompetitionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active_season(self) -> Optional[Season]:
        """Получить активный сезон"""
        result = await self.session.execute(
            select(Season).where(
                and_(
                    Season.is_active == True,
                    Season.start_date <= datetime.utcnow(),
                    Season.end_date >= datetime.utcnow()
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_active_competition(self) -> Optional[Competition]:
        """Получить активное соревнование"""
        result = await self.session.execute(
            select(Competition)
            .where(
                and_(
                    Competition.is_active == True,
                    Competition.ended_at.is_(None)
                )
            )
            .order_by(Competition.started_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create_season(self, season_data: Dict[str, Any]) -> Season:
        """Создать новый сезон"""
        season = Season(**season_data)
        self.session.add(season)
        await self.session.commit()
        await self.session.refresh(season)
        return season

    async def create_competition(self, competition_data: Dict[str, Any]) -> Competition:
        """Создать новое соревнование"""
        competition = Competition(**competition_data)
        self.session.add(competition)
        await self.session.commit()
        await self.session.refresh(competition)
        return competition

    async def create_result(self, result_data: Dict[str, Any]) -> CompetitionResult:
        """Создать результат соревнования"""
        result = CompetitionResult(**result_data)
        self.session.add(result)
        await self.session.commit()
        await self.session.refresh(result)
        return result

    async def get_participant_result(
        self, competition_id: int, pet_id: int
    ) -> Optional[CompetitionResult]:
        """Получить результат участника в соревновании"""
        result = await self.session.execute(
            select(CompetitionResult).where(
                and_(
                    CompetitionResult.competition_id == competition_id,
                    CompetitionResult.pet_id == pet_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def update_result_score(self, result_id: int, score: int) -> CompetitionResult:
        """Обновить результат участника"""
        result = await self.session.get(CompetitionResult, result_id)
        if result:
            result.score = score
            await self.session.commit()
            await self.session.refresh(result)
        return result

    async def get_competition_results(
        self, competition_id: int, limit: int = 10
    ) -> List[CompetitionResult]:
        """Получить топ-результаты соревнования"""
        result = await self.session.execute(
            select(CompetitionResult)
            .where(CompetitionResult.competition_id == competition_id)
            .order_by(desc(CompetitionResult.score))
            .limit(limit)
            .options(selectinload(CompetitionResult.pet))
        )
        return result.scalars().all()

    async def get_user_competitions(
        self, user_id: int, limit: int = 10
    ) -> List[CompetitionResult]:
        """Получить все соревнования пользователя"""
        result = await self.session.execute(
            select(CompetitionResult)
            .where(CompetitionResult.user_id == user_id)
            .order_by(desc(CompetitionResult.created_at))
            .limit(limit)
            .options(selectinload(CompetitionResult.competition))
        )
        return result.scalars().all()

    async def get_user_best_result(self, user_id: int) -> Optional[CompetitionResult]:
        """Получить лучший результат пользователя"""
        result = await self.session.execute(
            select(CompetitionResult)
            .where(CompetitionResult.user_id == user_id)
            .order_by(desc(CompetitionResult.score))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def increment_participants(self, competition_id: int) -> None:
        """Увеличить счетчик участников"""
        competition = await self.session.get(Competition, competition_id)
        if competition:
            competition.participants_count += 1
            await self.session.commit()

    async def end_competition(self, competition_id: int) -> None:
        """Завершить соревнование"""
        competition = await self.session.get(Competition, competition_id)
        if competition:
            competition.is_active = False
            competition.ended_at = datetime.utcnow()
            await self.session.commit()

    async def calculate_ranks(self, competition_id: int) -> None:
        """Рассчитать места участников"""
        results = await self.session.execute(
            select(CompetitionResult)
            .where(CompetitionResult.competition_id == competition_id)
            .order_by(desc(CompetitionResult.score))
        )
        results = results.scalars().all()
        
        for idx, result in enumerate(results, 1):
            result.rank = idx
        
        await self.session.commit()

    async def get_all_time_top(self, limit: int = 50) -> List[CompetitionResult]:
        """Получить топ-результаты за все время"""
        result = await self.session.execute(
            select(CompetitionResult)
            .order_by(desc(CompetitionResult.score))
            .limit(limit)
            .options(selectinload(CompetitionResult.pet))
        )
        return result.scalars().all()

    async def has_participated(self, competition_id: int, pet_id: int) -> bool:
        """Проверить, участвует ли питомец в соревновании"""
        result = await self.session.execute(
            select(CompetitionResult).where(
                and_(
                    CompetitionResult.competition_id == competition_id,
                    CompetitionResult.pet_id == pet_id
                )
            )
        )
        return result.scalar_one_or_none() is not None
