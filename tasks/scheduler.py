"""
Планировщик фоновых задач
"""
import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Optional

from .daily_reset import DailyResetTask
from .recovery import RecoveryTask
from .competition_tasks import check_and_end_competitions, create_new_competition_if_needed

logger = logging.getLogger(__name__)


class TaskScheduler:
    """Планировщик фоновых задач"""
    
    def __init__(self):
        self._running = False
        self._tasks: list = []
    
    async def start(self) -> None:
        """Запустить планировщик"""
        if self._running:
            logger.warning("Планировщик уже запущен")
            return
        
        self._running = True
        logger.info("🚀 Запуск планировщика задач...")
        
        # ===== ПРОВЕРЯЕМ, НУЖЕН ЛИ СБРОС =====
        try:
            from datetime import datetime, timedelta
            from database.connection import async_session
            from database.models import DailyReward
            
            async with async_session() as session:
                # Проверяем, был ли сброс сегодня
                from sqlalchemy import select, func
                result = await session.execute(
                    select(func.max(DailyReward.last_claim_date))
                )
                last_reset = result.scalar()
                
                if last_reset:
                    today = datetime.utcnow().date()
                    if last_reset.date() != today:
                        logger.info("📅 Сброс не выполнен сегодня, запускаем...")
                        await DailyResetTask.run()
                else:
                    logger.info("📅 Сброс никогда не выполнялся, запускаем...")
                    await DailyResetTask.run()
        except Exception as e:
            logger.warning(f"⚠️ Не удалось проверить сброс: {e}")
        
        # Запускаем фоновые задачи
        self._tasks = [
            asyncio.create_task(self._run_daily_reset()),
            asyncio.create_task(self._run_recovery()),
            asyncio.create_task(self._run_competition_checks()),
        ]
        
        logger.info(f"✅ Запущено {len(self._tasks)} фоновых задач")
    
    async def stop(self) -> None:
        """Остановить планировщик"""
        if not self._running:
            return
        
        self._running = False
        logger.info("🛑 Остановка планировщика...")
        
        for task in self._tasks:
            if not task.done():
                task.cancel()
        
        # Ждём завершения всех задач
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        
        logger.info("✅ Планировщик остановлен")
    
    async def _run_daily_reset(self) -> None:
        """
        Задача ежедневного сброса
        Выполняется каждый день в 00:00 UTC
        """
        logger.info("📅 Запущена задача ежедневного сброса")
        
        while self._running:
            try:
                # Вычисляем время до следующего полуночи
                now = datetime.utcnow()
                target_time = datetime.combine(
                    now.date() + timedelta(days=1),
                    time(0, 0, 0)
                )
                
                # Ждём до полуночи
                wait_seconds = (target_time - now).total_seconds()
                if wait_seconds > 0:
                    logger.debug(f"До следующего сброса: {wait_seconds:.0f} секунд")
                    await asyncio.sleep(wait_seconds)
                
                # Выполняем сброс
                if self._running:
                    await DailyResetTask.run()
                
            except asyncio.CancelledError:
                logger.info("Задача ежедневного сброса отменена")
                break
            except Exception as e:
                logger.error(f"Ошибка в задаче ежедневного сброса: {e}")
                # Ждём перед повторной попыткой
                await asyncio.sleep(60)
    
    async def _run_recovery(self) -> None:
        """
        Задача восстановления характеристик
        Выполняется каждый час
        """
        logger.info("🔄 Запущена задача восстановления")
        
        while self._running:
            try:
                # Выполняем восстановление
                if self._running:
                    await RecoveryTask.run_for_active_users()
                
                # Ждём час
                await asyncio.sleep(3600)
                
            except asyncio.CancelledError:
                logger.info("Задача восстановления отменена")
                break
            except Exception as e:
                logger.error(f"Ошибка в задаче восстановления: {e}")
                # Ждём перед повторной попыткой
                await asyncio.sleep(60)

    async def _run_competition_checks(self) -> None:
        """
        Задача проверки соревнований
        Выполняется каждые 10 минут
        """
        logger.info("🏆 Запущена задача проверки соревнований")
        
        while self._running:
            try:
                if self._running:
                    # Проверяем и завершаем старые соревнования
                    await check_and_end_competitions()
                    # Создаем новое если нужно
                    await create_new_competition_if_needed()
                
                # Ждём 10 минут
                await asyncio.sleep(600)
                
            except asyncio.CancelledError:
                logger.info("Задача проверки соревнований отменена")
                break
            except Exception as e:
                logger.error(f"Ошибка в задаче проверки соревнований: {e}")
                # Ждём перед повторной попыткой
                await asyncio.sleep(60)


# Глобальный экземпляр планировщика
scheduler = TaskScheduler()
