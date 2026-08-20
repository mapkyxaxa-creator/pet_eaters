from sqlalchemy.ext.asyncio import AsyncSession

from services.food_service import FoodService
from services.level_service import LevelService
from services.achievement_service import AchievementService
from services.adventure_service import AdventureService
from services.inventory_service import InventoryService
from services.cosmetic_service import CosmeticService
from services.payment_service import PaymentService
from services.daily_service import DailyService
from services.quest_service import QuestService
from services.social_service import SocialService
from services.economy_service import EconomyService
from services.premium_service import PremiumService
from services.photo_service import PhotoService
from services.pet_service import PetService
from services.house_service import HouseService


def get_food_service(session: AsyncSession, data: dict):
    """
    Получить FoodService с зависимостями
    
    Args:
        session: Сессия БД
        data: Данные из хендлера (содержит get_services из dp)
    """
    get_services = data.get("get_services")
    if get_services:
        services = get_services(session)
        return services["food"]
    
    # Fallback
    level_service = LevelService(session)
    achievement_service = AchievementService(session)
    level_service.set_achievement_service(achievement_service)
    achievement_service.set_level_service(level_service)
    return FoodService(session, level_service, achievement_service)


def get_adventure_service(session: AsyncSession, data: dict):
    """Получить AdventureService с зависимостями"""
    get_services = data.get("get_services")
    if get_services:
        services = get_services(session)
        return services["adventure"]
    
    level_service = LevelService(session)
    achievement_service = AchievementService(session)
    level_service.set_achievement_service(achievement_service)
    achievement_service.set_level_service(level_service)
    return AdventureService(session, level_service, achievement_service)


def get_inventory_service(session: AsyncSession, data: dict):
    """
    Получить InventoryService с зависимостями
    
    Args:
        session: Сессия БД
        data: Данные из хендлера (содержит get_services из dp)
    """
    get_services = data.get("get_services")
    if get_services:
        services = get_services(session)
        return services["inventory"]
    
    # Fallback
    level_service = LevelService(session)
    achievement_service = AchievementService(session)
    level_service.set_achievement_service(achievement_service)
    achievement_service.set_level_service(level_service)
    return InventoryService(session, achievement_service)


def get_achievement_service(session: AsyncSession, data: dict):
    """
    Получить AchievementService с зависимостями
    
    Args:
        session: Сессия БД
        data: Данные из хендлера (содержит get_services из dp)
    """
    get_services = data.get("get_services")
    if get_services:
        services = get_services(session)
        return services["achievement"]
    
    # Fallback
    level_service = LevelService(session)
    achievement_service = AchievementService(session)
    level_service.set_achievement_service(achievement_service)
    achievement_service.set_level_service(level_service)
    return achievement_service

def get_cosmetic_service(session: AsyncSession, data: dict):
    """
    Получить CosmeticService с зависимостями
    
    Args:
        session: Сессия БД
        data: Данные из хендлера (содержит get_services из dp)
    """
    get_services = data.get("get_services")
    if get_services:
        services = get_services(session)
        return services["cosmetic"]
    
    return CosmeticService(session)


def get_payment_service(session: AsyncSession, data: dict):
    """
    Получить PaymentService с зависимостями
    
    Args:
        session: Сессия БД
        data: Данные из хендлера (содержит get_services из dp)
    """
    get_services = data.get("get_services")
    if get_services:
        services = get_services(session)
        return services["payment"]
    
    return PaymentService(session)


def get_daily_service(session: AsyncSession, data: dict):
    """
    Получить DailyService с зависимостями
    
    Args:
        session: Сессия БД
        data: Данные из хендлера (содержит get_services из dp)
    """
    get_services = data.get("get_services")
    if get_services:
        services = get_services(session)
        return services["daily"]
    
    return DailyService(session)


def get_quest_service(session: AsyncSession, data: dict):
    """
    Получить QuestService с зависимостями
    
    Args:
        session: Сессия БД
        data: Данные из хендлера (содержит get_services из dp)
    """
    get_services = data.get("get_services")
    if get_services:
        services = get_services(session)
        return services["quest"]
    
    return QuestService(session)


def get_social_service(session: AsyncSession, data: dict):
    """
    Получить SocialService с зависимостями
    
    Args:
        session: Сессия БД
        data: Данные из хендлера (содержит get_services из dp)
    """
    get_services = data.get("get_services")
    if get_services:
        services = get_services(session)
        return services["social"]
    
    return SocialService(session)


def get_economy_service(session: AsyncSession, data: dict):
    """
    Получить EconomyService с зависимостями
    
    Args:
        session: Сессия БД
        data: Данные из хендлера (содержит get_services из dp)
    """
    get_services = data.get("get_services")
    if get_services:
        services = get_services(session)
        return services["economy"]
    
    return EconomyService(session)


def get_premium_service(session: AsyncSession, data: dict):
    """
    Получить PremiumService с зависимостями
    
    Args:
        session: Сессия БД
        data: Данные из хендлера (содержит get_services из dp)
    """
    get_services = data.get("get_services")
    if get_services:
        services = get_services(session)
        return services["premium"]
    
    return PremiumService(session)


def get_photo_service(session: AsyncSession, data: dict):
    """
    Получить PhotoService с зависимостями
    
    Args:
        session: Сессия БД
        data: Данные из хендлера (содержит get_services из dp)
    """
    get_services = data.get("get_services")
    if get_services:
        services = get_services(session)
        return services["photo"]
    
    return PhotoService(session)


def get_pet_service(session: AsyncSession, data: dict):
    """
    Получить PetService с зависимостями
    
    Args:
        session: Сессия БД
        data: Данные из хендлера (содержит get_services из dp)
    """
    get_services = data.get("get_services")
    if get_services:
        services = get_services(session)
        return services["pet"]
    
    return PetService(session)


def get_house_service(session: AsyncSession, data: dict):
    """
    Получить HouseService с зависимостями
    
    Args:
        session: Сессия БД
        data: Данные из хендлера (содержит get_services из dp)
    """
    get_services = data.get("get_services")
    if get_services:
        services = get_services(session)
        return services["house"]
    
    return HouseService(session)
