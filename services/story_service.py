"""
Сервис для управления сюжетными главами
"""
import json
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Pet
from database.repositories.user_repository import UserRepository
from services.data_loader import data_loader
from services.level_service import LevelService

logger = logging.getLogger(__name__)


class StoryService:
    """Сервис для работы с сюжетными главами"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.story_data = self._load_story_data()
    
    def _load_story_data(self) -> Dict[str, Any]:
        """Загрузить данные сюжета из JSON"""
        try:
            with open('data/story.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error("story.json not found")
            return {"chapters": []}
        except json.JSONDecodeError as e:
            logger.error(f"Invalid story.json: {e}")
            return {"chapters": []}
    
    def get_all_chapters(self) -> List[Dict[str, Any]]:
        """Получить все главы"""
        return self.story_data.get("chapters", [])
    
    def get_chapter_by_id(self, chapter_id: str) -> Optional[Dict[str, Any]]:
        """Получить главу по ID"""
        for chapter in self.get_all_chapters():
            if chapter.get("id") == chapter_id:
                return chapter
        return None
    
    def get_chapter_by_location(self, location: str) -> Optional[Dict[str, Any]]:
        """Получить главу по локации"""
        for chapter in self.get_all_chapters():
            if chapter.get("location") == location:
                return chapter
        return None
    
    def get_current_chapter(self, pet: Pet) -> Optional[Dict[str, Any]]:
        """Получить текущую главу (последнюю пройденную)"""
        if pet.story_progress == 0:
            return None
        
        for chapter in self.get_all_chapters():
            if chapter.get("id") == f"chapter_{pet.story_progress}":
                return chapter
        return None
    
    def get_next_chapter(self, pet: Pet) -> Optional[Dict[str, Any]]:
        """Получить следующую главу для прохождения"""
        all_chapters = self.get_all_chapters()
        
        if pet.story_progress == 0:
            return all_chapters[0] if all_chapters else None
        
        for chapter in all_chapters:
            if chapter.get("order") == pet.story_progress + 1:
                return chapter
        
        return None
    
    def check_and_unlock_chapters(self, pet: Pet) -> List[Dict[str, Any]]:
        """Проверить и разблокировать новые главы"""
        newly_unlocked = []
        all_chapters = self.get_all_chapters()
        current_progress = pet.story_progress
        
        for chapter in all_chapters:
            chapter_order = chapter.get("order", 0)
            min_level = chapter.get("min_level", 1)
            
            if chapter_order <= current_progress:
                continue
            
            if pet.level >= min_level and chapter_order == current_progress + 1:
                newly_unlocked.append(chapter)
        
        return newly_unlocked
    
    async def complete_chapter(self, pet: Pet, chapter_id: str) -> Dict[str, Any]:
        """
        Завершить главу и выдать награду
        """
        chapter = self.get_chapter_by_id(chapter_id)
        if not chapter:
            raise ValueError(f"Глава {chapter_id} не найдена")
        
        chapter_order = chapter.get("order", 0)
        
        if pet.story_progress >= chapter_order:
            raise ValueError(f"Глава {chapter_id} уже пройдена")
        
        min_level = chapter.get("min_level", 1)
        if pet.level < min_level:
            raise ValueError(f"Недостаточный уровень для главы {chapter_id}")
        
        rewards = chapter.get("rewards", {})
        coins = rewards.get("coins", 0)
        xp = rewards.get("xp", 0)
        title_name = rewards.get("title")
        
        # ===== ПРИМЕНЯЕМ БОНУС ХАРАКТЕРА =====
        characters = data_loader.get("characters", {})
        character = characters.get(pet.character_id, {})
        bonus = character.get("bonus", {})
        
        if "coins" in bonus:
            old_coins = coins
            coins = int(coins * bonus["coins"])
            logger.info(f"💰 Применён бонус характера к монетам: {old_coins} → {coins} (x{bonus['coins']})")
        
        if "xp" in bonus:
            old_xp = xp
            xp = int(xp * bonus["xp"])
            logger.info(f"⭐ Применён бонус характера к XP: {old_xp} → {xp} (x{bonus['xp']})")
        
        logger.info(f"📖 ЗАВЕРШЕНИЕ ГЛАВЫ: chapter={chapter.get('name')}, coins={coins}, xp={xp}, title_name={title_name}")
        
        user = await self.user_repo.get_by_id(pet.user_id)
        
        if not user:
            logger.error(f"❌ Пользователь не найден для pet_id={pet.id}")
            raise ValueError("Пользователь не найден")
        
        # Начисляем монеты
        if coins > 0:
            user.coins += coins
            logger.info(f"💰 Начислено {coins} монет, теперь {user.coins}")
        
        # Начисляем XP
        if xp > 0:
            level_service = LevelService(self.session)
            old_level = pet.level
            await level_service.add_experience(pet, xp)
            logger.info(f"⭐ Начислено {xp} XP, уровень был {old_level}, стал {pet.level}")
        
        # ===== СОХРАНЯЕМ ТИТУЛ =====
        if title_name:
            titles_data = data_loader.get("titles", {})
            title_id = None
            
            # Ищем ID титула по имени
            for tid, tdata in titles_data.items():
                if tdata.get("name") == title_name:
                    title_id = tid
                    break
            
            if title_id:
                pet.title_id = title_id
                logger.info(f"👑 Назначен титул: {title_name} (ID: {title_id})")
            else:
                logger.warning(f"⚠️ Титул '{title_name}' не найден в titles.json")
                pet.title_id = title_name
        
        # Обновляем прогресс
        pet.story_progress = chapter_order
        logger.info(f"📖 Прогресс сюжета: {chapter_order}")
        
        try:
            await self.session.flush()
            logger.info(f"✅ Изменения сохранены (flush)")
        except Exception as e:
            logger.error(f"❌ Ошибка при сохранении: {e}")
            raise
        
        return {
            "chapter": chapter,
            "coins": coins,
            "xp": xp,
            "title": title_name,
            "new_level": pet.level
        }
    
    def get_chapter_dialogue(self, chapter_id: str) -> List[Dict[str, str]]:
        """Получить диалоги для главы"""
        chapter = self.get_chapter_by_id(chapter_id)
        if not chapter:
            return []
        return chapter.get("dialogues", [])
    
    def get_chapter_choices(self, chapter_id: str) -> List[Dict[str, Any]]:
        """Получить варианты выбора для главы"""
        chapter = self.get_chapter_by_id(chapter_id)
        if not chapter:
            return []
        return chapter.get("choices", [])
    
    def get_chapter_status(self, pet: Pet) -> Dict[str, Any]:
        """Получить статус прогресса по главам"""
        all_chapters = self.get_all_chapters()
        completed = pet.story_progress
        total = len(all_chapters)
        
        chapters_status = []
        for chapter in all_chapters:
            chapter_order = chapter.get("order", 0)
            is_completed = chapter_order <= completed
            is_available = (
                not is_completed and 
                pet.level >= chapter.get("min_level", 1) and
                chapter_order == completed + 1
            )
            is_locked = not is_completed and not is_available
            
            chapters_status.append({
                "chapter": chapter,
                "is_completed": is_completed,
                "is_available": is_available,
                "is_locked": is_locked
            })
        
        return {
            "completed": completed,
            "total": total,
            "percentage": int((completed / total) * 100) if total > 0 else 0,
            "chapters": chapters_status
        }
    
    async def check_adventure_completion(self, pet: Pet, location: str) -> Optional[Dict[str, Any]]:
        """Проверить, есть ли сюжетная глава для локации"""
        chapter = self.get_chapter_by_location(location)
        if not chapter:
            return None
        
        chapter_order = chapter.get("order", 0)
        
        if pet.story_progress >= chapter_order:
            return None
        
        min_level = chapter.get("min_level", 1)
        if pet.level < min_level:
            return None
        
        if chapter_order != pet.story_progress + 1:
            return None
        
        try:
            reward = await self.complete_chapter(pet, chapter.get("id"))
            return {
                "chapter": chapter,
                "reward": reward,
                "message": f"🌟 Глава '{chapter.get('name')}' завершена!"
            }
        except ValueError as e:
            logger.error(f"Ошибка при завершении главы: {e}")
            return None
    
    def get_story_event_for_location(self, location: str, pet: Pet) -> Optional[str]:
        """Получить сюжетное событие для локации"""
        chapter = self.get_chapter_by_location(location)
        if not chapter:
            return None
        
        chapter_order = chapter.get("order", 0)
        
        if pet.story_progress >= chapter_order:
            return None
        
        min_level = chapter.get("min_level", 1)
        if pet.level < min_level:
            return None
        
        if chapter_order != pet.story_progress + 1:
            return None
        
        dialogues = chapter.get("dialogues", [])
        if not dialogues:
            return None
        
        npc_name = "Рич"
        first_dialogue = dialogues[0].get("text", "") if dialogues else ""
        
        npc_dialogues = [d for d in dialogues if d.get("npc") == "rich"]
        if npc_dialogues:
            first_dialogue = npc_dialogues[0].get("text", "")
        
        chapter_name = chapter.get("name", "")
        chapter_emoji = chapter.get("emoji", "📖")
        
        return (
            f"👤 <b>Встреча с Ричем!</b>\n"
            f"{chapter_emoji} Глава: {chapter_name}\n\n"
            f"{first_dialogue}\n\n"
            f"💡 Продолжай приключения, чтобы завершить эту главу!"
        )
    
    def get_npc_appearance_chance(self, location: str, pet: Pet) -> float:
        """Получить шанс появления NPC в локации"""
        chapter = self.get_chapter_by_location(location)
        if not chapter:
            return 0.0
        
        chapter_order = chapter.get("order", 0)
        
        if pet.story_progress >= chapter_order:
            return 0.0
        
        min_level = chapter.get("min_level", 1)
        if pet.level < min_level:
            return 0.0
        
        if chapter_order != pet.story_progress + 1:
            return 0.0
        
        return 0.3