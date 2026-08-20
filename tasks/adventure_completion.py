"""
Фоновые задачи для завершения приключений
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import async_session
from database.repositories.adventure_repository import AdventureRepository
from database.repositories.pet_repository import PetRepository
from handlers.common import get_adventure_service
from keyboards.adventure import get_adventure_after_keyboard
from services.data_loader import data_loader

logger = logging.getLogger(__name__)

# Глобальный словарь для хранения активных приключений
_active_adventures: Dict[int, Dict[str, Any]] = {}


async def schedule_adventure_completion(
    bot: Bot,
    user_id: int,
    pet_id: int,
    adventure_id: int,
    location_id: str,
    duration: int,
    chat_id: int,
    message_id: int = None,
    session: AsyncSession = None,
    data: Dict[str, Any] = None
) -> None:
    """Запланировать завершение приключения через duration секунд"""
    if adventure_id in _active_adventures:
        old_task = _active_adventures[adventure_id].get("task")
        if old_task and not old_task.done():
            old_task.cancel()
        del _active_adventures[adventure_id]
    
    task = asyncio.create_task(
        _complete_adventure_after_delay(
            bot=bot,
            user_id=user_id,
            pet_id=pet_id,
            adventure_id=adventure_id,
            location_id=location_id,
            duration=duration,
            chat_id=chat_id,
            message_id=message_id,
            session=session,
            data=data
        )
    )
    
    _active_adventures[adventure_id] = {
        "task": task,
        "chat_id": chat_id,
        "message_id": message_id,
        "started_at": datetime.utcnow()
    }
    
    logger.info(f"⏳ Запланировано приключение {adventure_id} на {duration} секунд для пользователя {user_id}")


async def _complete_adventure_after_delay(
    bot: Bot,
    user_id: int,
    pet_id: int,
    adventure_id: int,
    location_id: str,
    duration: int,
    chat_id: int,
    message_id: int = None,
    session: AsyncSession = None,
    data: Dict[str, Any] = None
) -> None:
    """Внутренняя функция: ждёт duration секунд с обновлениями каждые 10 секунд"""
    current_msg_id = [message_id]
    
    try:
        pet_name = "питомец"
        location_name = "локация"
        try:
            async with async_session() as temp_session:
                pet_repo = PetRepository(temp_session)
                pet = await pet_repo.get_by_id(pet_id)
                if pet:
                    pet_name = pet.name
                
                locations = data_loader.get("locations", {})
                location_data = locations.get(location_id, {})
                location_name = location_data.get("name", location_id)
        except Exception as e:
            logger.warning(f"Не удалось получить данные питомца/локации: {e}")
        
        elapsed = 0
        progress_messages = [
            f"🐾 {pet_name} исследует {location_name}...",
            f"🔍 {pet_name} ищет сокровища в {location_name}...",
            f"⚔️ {pet_name} сражается с монстрами в {location_name}...",
            f"🌿 {pet_name} изучает окрестности {location_name}...",
            f"💫 {pet_name} находит что-то интересное в {location_name}...",
            f"🏃 {pet_name} бежит по тропам {location_name}...",
            f"🎯 {pet_name} приближается к цели в {location_name}...",
            f"✨ {pet_name} чувствует, что приключение почти завершено!"
        ]
        
        while elapsed < duration:
            wait_time = min(10, duration - elapsed)
            await asyncio.sleep(wait_time)
            elapsed += wait_time
            
            if adventure_id not in _active_adventures:
                logger.info(f"❌ Приключение {adventure_id} отменено")
                return
            
            remaining = duration - elapsed
            if remaining > 5:
                progress_idx = min(int(elapsed / 10) % len(progress_messages), len(progress_messages) - 1)
                progress_text = progress_messages[progress_idx]
                
                from keyboards.adventure import get_adventure_status_keyboard
                keyboard = get_adventure_status_keyboard(adventure_id)
                
                adv_data = _active_adventures.get(adventure_id, {})
                message_to_edit = adv_data.get("message_id") or current_msg_id[0]
                
                try:
                    if message_to_edit:
                        try:
                            await bot.edit_message_text(
                                chat_id=chat_id,
                                message_id=message_to_edit,
                                text=f"⏳ <b>Приключение в процессе...</b>\n\n"
                                     f"{progress_text}\n\n"
                                     f"⏱️ Осталось примерно {int(remaining)} сек.",
                                reply_markup=keyboard,
                                parse_mode="HTML"
                            )
                            logger.info(f"✅ Сообщение прогресса отредактировано: {message_to_edit}")
                            current_msg_id[0] = message_to_edit
                            if adventure_id in _active_adventures:
                                _active_adventures[adventure_id]["message_id"] = message_to_edit
                        except Exception as edit_error:
                            logger.warning(f"⚠️ Не удалось отредактировать сообщение {message_to_edit}: {edit_error}")
                            sent_msg = await bot.send_message(
                                chat_id=chat_id,
                                text=f"⏳ <b>Приключение в процессе...</b>\n\n"
                                     f"{progress_text}\n\n"
                                     f"⏱️ Осталось примерно {int(remaining)} сек.",
                                reply_markup=keyboard,
                                parse_mode="HTML"
                            )
                            logger.info(f"✅ Новое сообщение отправлено: {sent_msg.message_id}")
                            current_msg_id[0] = sent_msg.message_id
                            if adventure_id in _active_adventures:
                                _active_adventures[adventure_id]["message_id"] = sent_msg.message_id
                    else:
                        sent_msg = await bot.send_message(
                            chat_id=chat_id,
                            text=f"⏳ <b>Приключение в процессе...</b>\n\n"
                                 f"{progress_text}\n\n"
                                 f"⏱️ Осталось примерно {int(remaining)} сек.",
                            reply_markup=keyboard,
                            parse_mode="HTML"
                        )
                        logger.info(f"✅ Первое сообщение прогресса отправлено: {sent_msg.message_id}")
                        current_msg_id[0] = sent_msg.message_id
                        if adventure_id in _active_adventures:
                            _active_adventures[adventure_id]["message_id"] = sent_msg.message_id
                except Exception as e:
                    logger.warning(f"Не удалось отправить обновление прогресса: {e}")
        
        # Вызываем сервис для завершения приключения
        if session is None:
            async with async_session() as new_session:
                await _complete_adventure_with_service(
                    bot=bot,
                    user_id=user_id,
                    adventure_id=adventure_id,
                    location_id=location_id,
                    chat_id=chat_id,
                    message_id=current_msg_id[0],
                    session=new_session,
                    data=data
                )
        else:
            await _complete_adventure_with_service(
                bot=bot,
                user_id=user_id,
                adventure_id=adventure_id,
                location_id=location_id,
                chat_id=chat_id,
                message_id=current_msg_id[0],
                session=session,
                data=data
            )
        
    except asyncio.CancelledError:
        logger.info(f"❌ Приключение {adventure_id} отменено")
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}", exc_info=True)
        try:
            await bot.send_message(
                chat_id=chat_id,
                text="❌ Произошла ошибка при завершении приключения. Проверь статус вручную."
            )
        except Exception:
            pass
    finally:
        if adventure_id in _active_adventures:
            del _active_adventures[adventure_id]


async def _complete_adventure_with_service(
    bot: Bot,
    user_id: int,
    adventure_id: int,
    location_id: str,
    chat_id: int,
    message_id: int = None,
    session: AsyncSession = None,
    data: Dict[str, Any] = None
) -> None:
    """Завершить приключение через сервис"""
    try:
        # Получаем adventure_service через фабрику
        adv_service = get_adventure_service(session, data or {})
        
        # Проверяем статус приключения через сервис
        status = await adv_service.check_adventure_by_id(adventure_id)
        
        if status.get("completed"):
            # Если уже завершено — показываем результат
            result_text = status.get("message", "✅ Приключение завершено!")
            keyboard = get_adventure_after_keyboard()
            
            if message_id:
                try:
                    await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=result_text, reply_markup=keyboard, parse_mode="HTML")
                except Exception:
                    await bot.send_message(chat_id=chat_id, text=result_text, reply_markup=keyboard, parse_mode="HTML")
            else:
                await bot.send_message(chat_id=chat_id, text=result_text, reply_markup=keyboard, parse_mode="HTML")
            return
        
        # Завершаем приключение через сервис
        result = await adv_service.complete_adventure(adventure_id)
        
        if result.get("success"):
            keyboard = get_adventure_after_keyboard()
            result_text = result.get("message", "✅ Приключение завершено!")
            
            if message_id:
                try:
                    await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=result_text, reply_markup=keyboard, parse_mode="HTML")
                    logger.info(f"✅ Результат отправлен в сообщение {message_id}")
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось отредактировать: {e}")
                    await bot.send_message(chat_id=chat_id, text=result_text, reply_markup=keyboard, parse_mode="HTML")
            else:
                await bot.send_message(chat_id=chat_id, text=result_text, reply_markup=keyboard, parse_mode="HTML")
            
            logger.info(f"✅ Приключение {adventure_id} завершено")
        else:
            await bot.send_message(chat_id=chat_id, text=f"❌ {result.get('message', 'Ошибка завершения')}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}", exc_info=True)
        try:
            await bot.send_message(chat_id=chat_id, text="❌ Произошла ошибка. Проверьте статус.")
        except Exception:
            pass


def cancel_adventure(adventure_id: int) -> bool:
    if adventure_id in _active_adventures:
        task = _active_adventures[adventure_id].get("task")
        if task and not task.done():
            task.cancel()
        del _active_adventures[adventure_id]
        logger.info(f"🔄 Приключение {adventure_id} отменено")
        return True
    return False


def get_active_adventures() -> Dict[int, Dict[str, Any]]:
    return _active_adventures.copy()


async def cleanup_stale_adventures(bot: Bot, max_age_seconds: int = 3600) -> None:
    now = datetime.utcnow()
    stale_ids = []
    
    for adv_id, data in _active_adventures.items():
        started_at = data.get("started_at")
        if started_at:
            age = (now - started_at).total_seconds()
            if age > max_age_seconds:
                stale_ids.append(adv_id)
    
    for adv_id in stale_ids:
        logger.warning(f"⚠️ Зависшее приключение {adv_id}, очищаем")
        cancel_adventure(adv_id)
        chat_id = _active_adventures.get(adv_id, {}).get("chat_id")
        if chat_id:
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text="⏳ Приключение автоматически завершено из-за технической проблемы."
                )
            except Exception:
                pass