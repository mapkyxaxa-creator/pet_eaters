"""
Фоновые задачи для бота
"""
from .daily_reset import DailyResetTask
from .recovery import RecoveryTask
from .competition_tasks import check_and_end_competitions, create_new_competition_if_needed

__all__ = [
    "DailyResetTask",
    "RecoveryTask",
    "check_and_end_competitions",
    "create_new_competition_if_needed",
]