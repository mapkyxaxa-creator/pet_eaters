import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class DataLoader:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            # Используем абсолютный путь относительно текущего файла
            self.data_dir = Path(__file__).resolve().parent.parent / "data"
            self.data: Dict[str, Dict[str, Any]] = {}
            self._loaded = False
            self.initialized = True
    
    async def load_all(self) -> None:
        if self._loaded:
            return
        
        if not self.data_dir.exists():
            logger.warning(f"Директория {self.data_dir} не найдена")
            return
        
        files = list(self.data_dir.glob("*.json"))
        logger.info(f"Найдено JSON файлов: {len(files)}")
        
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    file_data = json.load(f)
                    key = file_path.stem
                    self.data[key] = file_data
                    logger.info(f"Загружен {file_path.name} (ключей: {len(file_data)})")
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка парсинга {file_path.name}: {e}")
            except Exception as e:
                logger.error(f"Ошибка загрузки {file_path.name}: {e}")
        
        self._loaded = True
        
        required = ["balance", "characters"]
        for req in required:
            if req not in self.data:
                logger.error(f"Обязательный файл {req}.json отсутствует или пуст")
            else:
                logger.info(f"✅ {req}.json загружен (ключей: {len(self.data[req])})")
    
    async def reload(self, key: Optional[str] = None) -> None:
        """Перезагрузить данные из JSON-файлов"""
        if key:
            file_path = self.data_dir / f"{key}.json"
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        file_data = json.load(f)
                        self.data[key] = file_data
                        logger.info(f"🔄 Перезагружен {key}.json")
                except Exception as e:
                    logger.error(f"❌ Ошибка перезагрузки {key}.json: {e}")
            else:
                logger.warning(f"⚠️ Файл {key}.json не найден для перезагрузки")
        else:
            self.data.clear()
            self._loaded = False
            await self.load_all()
            logger.info("🔄 Все данные перезагружены")
    
    def get(self, key: str, default: Optional[Dict] = None) -> Dict:
        result = self.data.get(key, default or {})
        # Понижаем до DEBUG, чтобы не засорять логи
        logger.debug(f"📖 get('{key}') возвращает {len(result)} ключей")
        return result
    
    def get_balance(self) -> Dict:
        return self.data.get("balance", {})
    
    def get_characters(self) -> Dict:
        result = self.data.get("characters", {})
        logger.debug(f"📖 get_characters() возвращает {len(result)} ключей: {list(result.keys())}")
        return result


# Глобальный экземпляр
data_loader = DataLoader()
