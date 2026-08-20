"""
Задача для ежедневного сброса
Обновляет ежедневные награды и квесты
"""
import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import async_session
from database.repositories.daily_reward_repository import DailyRewardRepository
from database.repositories.quest_repository import QuestRepository
from services.daily_service import DailyService
from services.quest_service import QuestService

logger = logging.getLogger(__name__)


class DailyResetTask:
    """Задача для ежедневного сброса"""
    
    @staticmethod
    async def run() -> None:
        """
        Выполнить ежедневный сброс:
        1. Сбросить статус ежедневной награды
        2. Обновить ежедневные квесты
        """
        logger.info("🔄 Запуск ежедневного сброса...")
        
        try:
            async with async_session() as session:
                # Сброс ежедневных наград
                await DailyResetTask._reset_daily_rewards(session)
                
                # Сброс ежедневных квестов
                await DailyResetTask._reset_daily_quests(session)
                
                # ВАЖНО: без commit() эта задача (открывает сессию напрямую,
                # в обход миддлвари) ничего не сохраняет в БД.
                await session.commit()

                logger.info("✅ Ежедневный сброс завершён")
                
        except Exception as e:
            logger.error(f"❌ Ошибка при ежедневном сбросе: {e}")
            raise
    
    @staticmethod
    async def _reset_daily_rewards(session: AsyncSession) -> None:
        """Сброс статуса ежедневных наград"""
        repo = DailyRewardRepository(session)
        
        # Обновляем все записи, помечая, что награда не получена сегодня
        await repo.reset_all_for_new_day()
        
        logger.info("📅 Ежедневные награды сброшены")
        
        # Сброс ежедневных лайков
        await DailyResetTask._reset_daily_likes(session)
        
        # Сброс ежедневных подарков
        await DailyResetTask._reset_daily_gifts(session)
    
    @staticmethod
    async def _reset_daily_quests(session: AsyncSession) -> None:
        """Сброс ежедневных квестов"""
        # Обновляем прогресс квестов
        await QuestRepository(session).reset_all_daily_quests()
        
        logger.info("📋 Ежедневные квесты сброшены")
    
    @staticmethod
    async def _reset_daily_likes(session: AsyncSession) -> None:
        """Сброс ежедневных лайков"""
        from sqlalchemy import delete
        from database.models import Like
        
        # Удаляем лайки старше 24 часов
        cutoff = datetime.utcnow() - timedelta(days=1)
        result = await session.execute(
            delete(Like).where(Like.created_at < cutoff)
        )
        deleted = result.rowcount
        if deleted > 0:
            logger.info(f"❤️ Удалено {deleted} старых лайков")
    
    @staticmethod
    async def _reset_daily_gifts(session: AsyncSession) -> None:
        """Сброс ежедневных подарков"""
        from sqlalchemy import delete
        from database.models import GiftLog
        
        # Удаляем логи подарков старше 24 часов
        cutoff = datetime.utcnow() - timedelta(days=1)
        result = await session.execute(
            delete(GiftLog).where(GiftLog.created_at < cutoff)
        )
        deleted = result.rowcount
        if deleted > 0:
            logger.info(f"🎁 Удалено {deleted} старых записей подарков")
    
    @staticmethod
    async def check_and_run_if_needed() -> None:
        """
        Проверить, нужно ли выполнить сброс (если прошло больше 24 часов)
        """
        # Простая проверка по времени последнего сброса
        # В реальном проекте можно хранить timestamp в БД или использовать планировщик
        
        # Для простоты используем текущее время
        # При запуске бота проверяем, прошел ли день
        
        # Здесь можно добавить логику проверки из БД
        # Например, хранить last_reset в отдельной таблице
        
        # По умолчанию запускаем при каждом вызове
        # Планировщик будет вызывать это раз в час
        
        now = datetime.utcnow()
        
        # Проверяем, нужно ли выполнить сброс (если сейчас новый день)
        # Это будет определяться внешним планировщиком
        # Например, cron задача в 00:00
        
        # Если вызывается из планировщика, просто выполняем
        await DailyResetTask.run()
