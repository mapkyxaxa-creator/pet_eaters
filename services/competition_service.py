"""Сервис для работы с соревнованиями"""
import random
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories.competition_repository import CompetitionRepository
from database.repositories.pet_repository import PetRepository
from database.repositories.user_repository import UserRepository
from database.repositories.achievement_repository import AchievementRepository
from database.models import Competition, CompetitionResult
from services.data_loader import data_loader

logger = logging.getLogger(__name__)


class CompetitionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.competition_repo = CompetitionRepository(session)
        self.pet_repo = PetRepository(session)
        self.user_repo = UserRepository(session)
        self.achievement_repo = AchievementRepository(session)
        self.foods = data_loader.get("foods", {})
        self.competition_data = data_loader.get("competitions", {})
        self.titles_data = data_loader.get("titles", {})
    
    def _get_week_range(self, reference_date: datetime = None) -> Tuple[datetime, datetime]:
        """
        Получить начало и конец текущей недели (пн 00:00 — вс 23:59)
        """
        if reference_date is None:
            reference_date = datetime.utcnow()
        
        # Находим понедельник текущей недели
        days_since_monday = reference_date.weekday()  # 0 = понедельник
        start = reference_date - timedelta(days=days_since_monday)
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Воскресенье 23:59
        end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        
        return start, end
    
    def _is_week_over(self, reference_date: datetime = None) -> bool:
        """Проверить, закончилась ли текущая неделя"""
        if reference_date is None:
            reference_date = datetime.utcnow()
        _, end = self._get_week_range(reference_date)
        return reference_date > end
    
    def _get_next_week_start(self, reference_date: datetime = None) -> datetime:
        """Получить начало следующей недели (пн 00:00)"""
        if reference_date is None:
            reference_date = datetime.utcnow()
        start, _ = self._get_week_range(reference_date)
        return start + timedelta(days=7)
    
    async def get_active_competition(self) -> Optional[Competition]:
        """Получить активное соревнование"""
        return await self.competition_repo.get_active_competition()
    
    async def get_or_create_active_competition(self) -> Competition:
        """Получить активное соревнование или создать новое"""
        competition = await self.competition_repo.get_active_competition()
        if competition:
            logger.info(f"🏆 Активное соревнование уже есть: id={competition.id}, type={competition.type}")
            return competition
        
        # Проверяем, закончилась ли неделя
        if self._is_week_over():
            # Если неделя закончилась, создаём новое со следующей недели
            start_date = self._get_next_week_start()
        else:
            # Используем текущую неделю
            start_date, _ = self._get_week_range()
        
        # Проверяем активный сезон
        season = await self.competition_repo.get_active_season()
        if not season:
            logger.info("📅 Создаём новый сезон...")
            season = await self._create_season()
        
        # Создаём новое соревнование
        comp_type = random.choice(self.competition_data.get("competition_types", []))
        competition_data = {
            "type": comp_type["id"],
            "season_id": season.id,
            "started_at": start_date,
            "is_active": True,
        }
        competition = await self.competition_repo.create_competition(competition_data)
        
        logger.info(f"🏆 Создано новое соревнование: id={competition.id}, type={comp_type['id']}, start={start_date}")
        return competition
    
    async def _create_season(self) -> Any:
        """Создать новый сезон"""
        from database.models import Season
        
        current_season = await self.competition_repo.get_active_season()
        if current_season:
            return current_season
        
        season_id = int(datetime.utcnow().timestamp())
        duration_days = 365  # сезон на год
        
        season_data = {
            "season_id": season_id,
            "name": f"Сезон {datetime.utcnow().strftime('%Y')}",
            "start_date": datetime.utcnow(),
            "end_date": datetime.utcnow() + timedelta(days=duration_days),
            "is_active": True,
        }
        
        season = await self.competition_repo.create_season(season_data)
        logger.info(f"📅 Создан сезон: id={season.id}, name={season.name}")
        return season
    
    async def join_competition(self, pet_id: int, user_id: int) -> Dict[str, Any]:
        """Зарегистрироваться на соревнование"""
        competition = await self.get_or_create_active_competition()
        
        # Проверяем, не закончилась ли уже неделя
        if self._is_week_over():
            return {
                "success": False,
                "message": "❌ Эта неделя уже завершена! Новое соревнование начнётся в понедельник."
            }
        
        existing = await self.competition_repo.get_participant_result(
            competition.id, pet_id
        )
        if existing:
            return {
                "success": False,
                "message": "Ты уже участвуешь в этом соревновании! 🏆"
            }
        
        result_data = {
            "competition_id": competition.id,
            "pet_id": pet_id,
            "user_id": user_id,
            "score": 0,
        }
        await self.competition_repo.create_result(result_data)
        await self.competition_repo.increment_participants(competition.id)
        
        pet = await self.pet_repo.get_by_id(pet_id)
        if pet:
            pet.total_competitions = (pet.total_competitions or 0) + 1
            await self.session.flush()
        
        logger.info(f"✅ Пользователь {user_id} зарегистрировался в соревновании {competition.id}")
        
        return {
            "success": True,
            "message": "Ты успешно зарегистрировался на соревнование! 🎉",
            "competition_type": competition.type,
        }
    
    async def get_competition_status(self, pet_id: int) -> Dict[str, Any]:
        """Получить статус участия питомца в соревновании"""
        competition = await self.competition_repo.get_active_competition()
        if not competition:
            return {
                "success": False,
                "message": "Нет активных соревнований. Загляни позже! 🏆"
            }
        
        result = await self.competition_repo.get_participant_result(
            competition.id, pet_id
        )
        
        is_participating = result is not None
        
        # Получаем информацию о текущей неделе
        start, end = self._get_week_range()
        days_left = (end - datetime.utcnow()).days + 1
        if days_left < 0:
            days_left = 0
        
        data = {
            "success": True,
            "competition": competition,
            "is_participating": is_participating,
            "score": result.score if result else 0,
            "league": self._get_league(result.score) if result else None,
            "rank": result.rank if result else None,
            "week_start": start.strftime("%d.%m.%Y"),
            "week_end": end.strftime("%d.%m.%Y"),
            "days_left": days_left
        }
        
        if is_participating:
            data["result_id"] = result.id
            
        return data
    
    async def submit_food_eaten(self, pet_id: int, food_amount: int) -> Dict[str, Any]:
        """Зафиксировать съеденную еду в соревновании"""
        # Проверяем, не закончилась ли неделя
        if self._is_week_over():
            return {"success": False, "message": "❌ Эта неделя уже завершена! Жди нового соревнования."}
        
        competition = await self.competition_repo.get_active_competition()
        if not competition:
            return {"success": False, "message": "Нет активных соревнований"}
        
        result = await self.competition_repo.get_participant_result(
            competition.id, pet_id
        )
        if not result:
            return {"success": False, "message": "Ты не участвуешь в соревновании"}
        
        new_score = result.score + food_amount
        await self.competition_repo.update_result_score(result.id, new_score)
        
        logger.info(f"🏆 Очки соревнования: pet_id={pet_id}, +{food_amount}, всего={new_score}")
        
        return {
            "success": True,
            "score": new_score,
            "added": food_amount,
        }
    
    async def get_competition_top(self, limit: int = 10) -> List[CompetitionResult]:
        """Получить топ участников в активном соревновании"""
        competition = await self.competition_repo.get_active_competition()
        if not competition:
            return []
        
        return await self.competition_repo.get_competition_results(
            competition.id, limit
        )
    
    async def get_my_results(self, user_id: int) -> List[CompetitionResult]:
        """Получить результаты пользователя"""
        return await self.competition_repo.get_user_competitions(user_id, 20)
    
    async def end_active_competition(self) -> None:
        """Завершить активное соревнование (в воскресенье 23:59)"""
        competition = await self.competition_repo.get_active_competition()
        if not competition:
            logger.info("Нет активных соревнований для завершения")
            return
        
        logger.info(f"🏆 Завершаем соревнование {competition.id}...")
        
        await self.competition_repo.calculate_ranks(competition.id)
        
        results = await self.competition_repo.get_competition_results(
            competition.id, 100
        )
        
        logger.info(f"📊 Всего участников: {len(results)}")
        
        for idx, result in enumerate(results, 1):
            reward_coins, reward_xp, reward_title = self._calculate_rewards(
                idx, len(results)
            )
            result.reward_coins = reward_coins
            result.reward_xp = reward_xp
            if reward_title:
                result.reward_title = reward_title
            
            league = self._get_league(result.score)
            result.league_id = league
            
            logger.info(f"🏅 Место {idx}: pet_id={result.pet_id}, score={result.score}, coins={reward_coins}, xp={reward_xp}, title={reward_title}")
            
            # Увеличиваем счётчик побед
            pet = await self.pet_repo.get_by_id(result.pet_id)
            if pet:
                pet.competition_wins = (pet.competition_wins or 0) + 1
                logger.info(f"🏆 Победа #{pet.competition_wins} для питомца {pet.id}")
                
                # Создаём достижение для титула за место
                if reward_title:
                    title_id = None
                    for tid, tdata in self.titles_data.items():
                        if tdata.get("name") == reward_title:
                            title_id = tid
                            break
                    
                    if title_id:
                        achievement_exists = await self.achievement_repo.get_by_id(pet.id, title_id)
                        if not achievement_exists:
                            await self.achievement_repo.unlock(pet.id, title_id)
                            logger.info(f"👑 Достижение '{reward_title}' (ID: {title_id}) создано для питомца {pet.id}")
                        
                        if not pet.title_id or pet.title_id == "newcomer":
                            pet.title_id = title_id
                            logger.info(f"👑 Титул '{reward_title}' назначен питомцу {pet.id}")
                    else:
                        logger.warning(f"⚠️ Титул '{reward_title}' не найден в titles.json")
        
        await self.session.flush()
        
        await self.competition_repo.end_competition(competition.id)
        
        logger.info(f"✅ Соревнование {competition.id} завершено, награды назначены")
    
    async def claim_rewards(self, user_id: int) -> Dict[str, Any]:
        """Забрать награды за завершенное соревнование"""
        results = await self.competition_repo.get_user_competitions(user_id, 50)
        unclaimed = [r for r in results if not r.rewards_claimed and r.reward_coins > 0]
        
        if not unclaimed:
            return {"success": False, "message": "Нет доступных наград 🎁"}
        
        total_coins = 0
        total_xp = 0
        titles = []
        
        for result in unclaimed:
            user = await self.user_repo.get_by_id(user_id)
            if user:
                user.coins += result.reward_coins
                total_coins += result.reward_coins
                
                pet = await self.pet_repo.get_by_id(result.pet_id)
                if pet:
                    from services.level_service import LevelService
                    level_service = LevelService(self.session)
                    await level_service.add_experience(pet, result.reward_xp)
                    total_xp += result.reward_xp
                    
                    if result.reward_title:
                        titles.append(result.reward_title)
            
            result.rewards_claimed = True
        
        await self.session.flush()
        
        message = f"🎁 Награды получены!\n🪙 Монеты: +{total_coins}\n⭐ Опыт: +{total_xp}"
        if titles:
            message += f"\n🏅 Титулы: {', '.join(titles)}"
        
        logger.info(f"✅ Пользователь {user_id} забрал награды: coins={total_coins}, xp={total_xp}")
        
        return {"success": True, "message": message}
    
    def _get_league(self, score: int) -> Optional[str]:
        """Определить лигу по очкам"""
        leagues = self.competition_data.get("leagues", [])
        for league in leagues:
            if league["min_score"] <= score <= league["max_score"]:
                return league["id"]
        return None
    
    def _calculate_rewards(
        self, rank: int, total_participants: int
    ) -> Tuple[int, int, Optional[str]]:
        """Рассчитать награду в зависимости от места"""
        if rank == 1:
            return 500, 200, "Победитель Жора"
        elif rank == 2:
            return 300, 150, "Серебряный Жор"
        elif rank == 3:
            return 200, 100, "Бронзовый Жор"
        elif rank <= 10:
            return 100, 50, "Лучший едок"
        elif rank <= 25:
            return 50, 25, None
        elif rank <= 50:
            return 25, 10, None
        else:
            return 10, 5, None
    
    async def get_competition_info(self) -> Dict[str, Any]:
        """Получить информацию о текущем соревновании"""
        competition = await self.competition_repo.get_active_competition()
        if not competition:
            return {
                "success": False,
                "message": "Нет активных соревнований 🏆"
            }
        
        comp_type = None
        for ct in self.competition_data.get("competition_types", []):
            if ct["id"] == competition.type:
                comp_type = ct
                break
        
        start, end = self._get_week_range()
        
        return {
            "success": True,
            "type": competition.type,
            "name": comp_type["name"] if comp_type else competition.type,
            "emoji": comp_type["emoji"] if comp_type else "🏆",
            "description": comp_type["description"] if comp_type else "",
            "participants": competition.participants_count,
            "started_at": competition.started_at,
            "week_start": start.strftime("%d.%m.%Y"),
            "week_end": end.strftime("%d.%m.%Y"),
            "days_left": (end - datetime.utcnow()).days + 1
        }