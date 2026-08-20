import logging
from typing import Tuple, Dict, Any
from database.models import Pet
from services.data_loader import data_loader
from services.chat_service import ChatService

logger = logging.getLogger(__name__)


class LevelService:
    """Сервис для управления уровнем и XP"""
    
    def __init__(self, session, achievement_service=None):
        self.session = session
        self.balance = data_loader.get_balance()
        self.achievement_service = achievement_service
    
    def set_achievement_service(self, achievement_service):
        """Установить сервис достижений"""
        self.achievement_service = achievement_service
    
    def get_xp_for_level(self, level: int) -> int:
        """Расчет XP для следующего уровня"""
        xp_base = self.balance.get("xp_base", 100)
        xp_per_level = self.balance.get("xp_per_level", 50)
        return xp_base + (level - 1) * xp_per_level
    
    async def add_experience(self, pet: Pet, xp_amount: int) -> Tuple[bool, Dict[str, Any]]:
        """Добавление опыта питомцу"""
        old_level = pet.level
        pet.experience += xp_amount
        
        leveled_up = False
        levels_gained = 0
        
        while True:
            xp_needed = self.get_xp_for_level(pet.level)
            if pet.experience >= xp_needed:
                pet.level += 1
                pet.experience -= xp_needed
                leveled_up = True
                levels_gained += 1
                await self._apply_level_up(pet)
            else:
                break
        
        if leveled_up:
            # ===== ДОБАВЛЯЕМ В ЧАТ (если уровень кратен 5) =====
            if pet.level % 5 == 0:
                try:
                    chat_service = ChatService(self.session)
                    emoji_map = {
                        'dog': '🐶', 'cat': '🐱', 'fox': '🦊', 'wolf': '🐺',
                        'rabbit': '🐰', 'bear': '🐻', 'panda': '🐼', 'lion': '🦁',
                        'tiger': '🐯', 'dragon': '🐉', 'unicorn': '🦄', 'bird': '🐦',
                        'penguin': '🐧', 'owl': '🦉', 'elephant': '🐘', 'monkey': '🐒',
                        'koala': '🐨', 'sloth': '🦥', 'raccoon': '🦝', 'skunk': '🦨'
                    }
                    pet_emoji = emoji_map.get(pet.character_id, '🐾')
                    message = f"{pet_emoji} Я достиг {pet.level} уровня! 🎉"
                    await chat_service.add_event(
                        pet=pet,
                        event_type="level_up",
                        message=message,
                        data={"level": pet.level}
                    )
                    logger.info(f"✅ СООБЩЕНИЕ В ЧАТ ДОБАВЛЕНО (level_up): pet_id={pet.id}, level={pet.level}")
                except Exception as e:
                    logger.error(f"❌ Ошибка добавления в чат: {e}")
            logger.info(f"Питомец {pet.name} повысил уровень до {pet.level} (+{levels_gained} ур)")
            if self.achievement_service:
                unlocked = await self.achievement_service.check_all_achievements(pet.id)
                if unlocked:
                    logger.info(f"Питомец {pet.id} открыл достижения уровня")
        
        return leveled_up, {
            "old_level": old_level,
            "new_level": pet.level,
            "levels_gained": levels_gained,
            "xp_remaining": pet.experience,
            "xp_needed": self.get_xp_for_level(pet.level)
        }
    
    async def _apply_level_up(self, pet: Pet) -> None:
        """Применение бонусов за уровень"""
        stomach_per_level = self.balance.get("stomach_per_level", 20)
        smell_per_level = self.balance.get("smell_per_level", 1.5)
        luck_per_level = self.balance.get("luck_per_level", 0.005)
        eating_speed_per_level = self.balance.get("eating_speed_per_level", 1)
        
        pet.stomach_capacity += stomach_per_level
        pet.smell = int(pet.smell + smell_per_level)
        pet.luck = min(pet.luck + luck_per_level, self.balance.get("max_luck", 0.30))
        pet.eating_speed += eating_speed_per_level
        
        max_energy = self.balance.get("max_energy", 100)
        pet.energy = min(pet.energy + 10, max_energy)