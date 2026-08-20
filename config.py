import os
from dotenv import load_dotenv
from typing import Optional, List

load_dotenv()


class Config:
    """Конфигурация приложения"""
    
    # Telegram
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./pet_eaters.db"
    )
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Application
    APP_NAME: str = "Питомцы: Большой Жор"
    APP_VERSION: str = "1.0.0"
    
    # Admin IDs (список Telegram ID администраторов)
    ADMIN_IDS: List[int] = [2031001867]
    
    @classmethod
    def validate(cls) -> None:
        """Проверка обязательных переменных"""
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN не задан в .env файле")
        
        # Загружаем ADMIN_IDS из переменной окружения
        admin_ids_str = os.getenv("ADMIN_IDS", "")
        if admin_ids_str:
            try:
                cls.ADMIN_IDS = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip()]
            except ValueError:
                print(f"⚠️ Ошибка парсинга ADMIN_IDS: {admin_ids_str}")
                cls.ADMIN_IDS = [2031001867]
        else:
            # Значение по умолчанию для разработки
            cls.ADMIN_IDS = [2031001867]
            print(f"ℹ️ ADMIN_IDS не задан в .env, используется значение по умолчанию: {cls.ADMIN_IDS}")


config = Config()
