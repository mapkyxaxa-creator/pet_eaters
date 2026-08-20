"""Задачи для соревнований"""
import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import async_session
from services.competition_service import CompetitionService

logger = logging.getLogger(__name__)


def _is_week_over() -> bool:
    """Проверить, закончилась ли текущая неделя (воскресенье 23:59)"""
    now = datetime.utcnow()
    # Неделя считается закончившейся, если:
    # 1. Это воскресенье после 23:00
    # 2. Или это понедельник или позже
    if now.weekday() == 6 and now.hour >= 23:
        return True
    if now.weekday() >= 0:  # Понедельник или позже
        # Проверяем, прошло ли воскресенье
        # Если сейчас понедельник или позднее, то неделя закончилась
        # Но если это понедельник до 23:00, то неделя только что закончилась
        if now.weekday() == 0 and now.hour < 23:
            # Это понедельник, значит неделя закончилась
            return True
        if now.weekday() > 0:
            # Вторник или позже, неделя точно закончилась
            return True
    return False


async def check_and_end_competitions():
    """Проверить и завершить просроченные соревнования"""
    logger.info("🔍 Проверка соревнований на завершение...")
    
    try:
        async with async_session() as session:
            service = CompetitionService(session)
            competition = await service.get_active_competition()
            
            if not competition:
                logger.info("ℹ️ Нет активных соревнований")
                return
            
            # Проверяем, закончилась ли неделя
            if _is_week_over():
                logger.info(f"⏰ Неделя закончилась! Завершаем соревнование {competition.id}...")
                await service.end_active_competition()
                logger.info(f"✅ Соревнование {competition.id} завершено")
            else:
                # Вычисляем дни до конца недели
                now = datetime.utcnow()
                days_until_sunday = 6 - now.weekday()
                hours_until_end = (days_until_sunday * 24) + (23 - now.hour)
                logger.info(f"⏳ До конца недели: {days_until_sunday} дней, {hours_until_end % 24} часов")
                
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке соревнований: {e}")


async def create_new_competition_if_needed():
    """Создать новое соревнование, если нет активного"""
    logger.info("🔍 Проверка необходимости создания нового соревнования...")
    
    try:
        async with async_session() as session:
            service = CompetitionService(session)
            competition = await service.get_active_competition()
            
            if not competition:
                # Проверяем, не понедельник ли сегодня
                now = datetime.utcnow()
                if now.weekday() == 0 and now.hour >= 0:
                    logger.info("📅 Понедельник! Создаём новое соревнование...")
                    await service.get_or_create_active_competition()
                    logger.info("✅ Новое соревнование создано")
                else:
                    # Если нет активного, но неделя ещё не началась — создаём
                    if not _is_week_over():
                        logger.info("📅 Создаём соревнование на текущую неделю...")
                        await service.get_or_create_active_competition()
                        logger.info("✅ Новое соревнование создано")
                    else:
                        logger.info("ℹ️ Неделя закончилась, новое начнётся в понедельник")
            else:
                logger.info(f"ℹ️ Активное соревнование уже есть: id={competition.id}")
                
    except Exception as e:
        logger.error(f"❌ Ошибка при создании соревнования: {e}")