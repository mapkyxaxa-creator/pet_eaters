#!/usr/bin/env python3
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault

from config import config
from database.connection import init_db, close_db
from middlewares.database import DatabaseMiddleware
from middlewares.throttling import ThrottlingMiddleware
from handlers import (
    start, pet_creation, profile, menu, food, shop, inventory,
    adventure, achievements, daily, social, rating, photos,
    mailbox, house, house_bonus, progress, common, story, chat,
    competition, feed, notifications, onboarding, admin, moderation
)
from services.data_loader import data_loader
from services.level_service import LevelService
from services.achievement_service import AchievementService
from services.food_service_with_house import FoodServiceWithHouse
from services.adventure_service import AdventureService
from services.inventory_service import InventoryService
from services.quest_service import QuestService
from services.social_service import SocialService
from services.daily_service import DailyService
from services.economy_service import EconomyService
from services.photo_service import PhotoService
from services.payment_service import PaymentService
from services.cosmetic_service import CosmeticService
from services.premium_service import PremiumService
from services.pet_service import PetService
from services.house_service import HouseService
from services.house_patch import apply_house_patches
from tasks.scheduler import scheduler
from tasks.adventure_completion import cleanup_stale_adventures

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


async def set_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command="start", description="🏠 Главное меню"),
        BotCommand(command="profile", description="👤 Мой профиль"),
        BotCommand(command="menu", description="📋 Главное меню"),
        BotCommand(command="eat", description="🍽️ Покормить питомца"),
        BotCommand(command="shop", description="🏪 Магазин"),
        BotCommand(command="inventory", description="🎒 Инвентарь"),
        BotCommand(command="adventure", description="⚔️ Приключения"),
        BotCommand(command="achievements", description="🏆 Достижения"),
        BotCommand(command="progress", description="📊 Прогресс"),
        BotCommand(command="daily", description="📅 Ежедневное"),
        BotCommand(command="rating", description="📊 Рейтинг"),
        BotCommand(command="photos", description="📸 Альбом фото"),
        BotCommand(command="house", description="🏠 Дом"),
        BotCommand(command="chat", description="💬 Чат питомцев"),
        BotCommand(command="story", description="📖 Сюжет"),
        BotCommand(command="view", description="👤 Профиль игрока"),
        BotCommand(command="competition", description="🏆 Соревнования"),
        BotCommand(command="feed", description="📸 Лента"),
        BotCommand(command="notifications", description="🔔 Уведомления"),
        BotCommand(command="admin_stats", description="📊 Статистика (админ)"),
        BotCommand(command="moderation", description="📸 Модерация (админ)"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())


def get_services(session):
    """Фабрика сервисов"""
    level_service = LevelService(session)
    achievement_service = AchievementService(session)
    
    level_service.set_achievement_service(achievement_service)
    achievement_service.set_level_service(level_service)
    
    food_service = FoodServiceWithHouse(session, level_service, achievement_service)
    adventure_service = AdventureService(session, level_service, achievement_service)
    inventory_service = InventoryService(session, achievement_service)
    quest_service = QuestService(session)
    social_service = SocialService(session)
    daily_service = DailyService(session)
    economy_service = EconomyService(session)
    photo_service = PhotoService(session)
    payment_service = PaymentService(session)
    cosmetic_service = CosmeticService(session)
    premium_service = PremiumService(session)
    pet_service = PetService(session)
    house_service = HouseService(session)
    
    return {
        "level": level_service,
        "achievement": achievement_service,
        "food": food_service,
        "adventure": adventure_service,
        "inventory": inventory_service,
        "quest": quest_service,
        "social": social_service,
        "daily": daily_service,
        "economy": economy_service,
        "photo": photo_service,
        "payment": payment_service,
        "cosmetic": cosmetic_service,
        "premium": premium_service,
        "pet": pet_service,
        "house": house_service,
    }


async def main() -> None:
    logger.info(f"Запуск {config.APP_NAME} v{config.APP_VERSION}")
    
    try:
        config.validate()
    except ValueError as e:
        logger.error(f"Ошибка конфигурации: {e}")
        return
    
    await init_db()
    logger.info("База данных инициализирована")
    
    try:
        await data_loader.load_all()
        logger.info(f"Загружено данных: {len(data_loader.data)} файлов")
    except Exception as e:
        logger.error(f"Ошибка загрузки данных: {e}")
        return
    
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # ===== MIDDLEWARE =====
    dp.message.middleware(DatabaseMiddleware())
    dp.callback_query.middleware(DatabaseMiddleware())
    dp.message.middleware(ThrottlingMiddleware())
    dp.callback_query.middleware(ThrottlingMiddleware())
    
    # ===== ПРАВИЛЬНАЯ ПЕРЕДАЧА СЕРВИСОВ =====
    dp.workflow_data["get_services"] = get_services
    
    # ===== РЕГИСТРАЦИЯ РОУТЕРОВ =====
    dp.include_routers(
        start.router,
        pet_creation.router,
        profile.router,
        menu.router,
        food.router,
        shop.router,
        inventory.router,
        adventure.router,
        achievements.router,
        daily.router,
        social.router,
        rating.router,
        photos.router,
        mailbox.router,
        house.router,
        house_bonus.router,
        progress.router,
        story.router,
        chat.router,
        competition.router,
        feed.router,
        notifications.router,
        onboarding.router,
        admin.router,
        moderation.router,
    )
    
    await set_commands(bot)

    # ===== ЗАПУСК ПЛАНИРОВЩИКА =====
    await scheduler.start()
    
    # ===== ОЧИСТКА ЗАВИСШИХ ПРИКЛЮЧЕНИЙ =====
    try:
        await cleanup_stale_adventures(bot, max_age_seconds=3600)
        logger.info("🧹 Очистка зависших приключений выполнена")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка очистки приключений: {e}")

    logger.info("Бот запущен и готов к работе")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await scheduler.stop()
        await close_db()
        await bot.session.close()
        logger.info("Бот остановлен")


if __name__ == "__main__":
    asyncio.run(main())