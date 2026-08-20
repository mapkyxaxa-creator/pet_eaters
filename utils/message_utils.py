from typing import Union, Optional, Dict, Any
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup


async def send_or_edit(
    event: Union[Message, CallbackQuery],
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: str = "HTML",
    photo: Optional[str] = None,
    caption: Optional[str] = None,
    **kwargs
) -> None:
    """
    Универсальная отправка/редактирование сообщения
    
    Args:
        event: Message или CallbackQuery
        text: Текст сообщения
        reply_markup: Клавиатура
        parse_mode: Режим парсинга
        photo: ID фото (если нужно отправить фото)
        caption: Подпись к фото
        **kwargs: Дополнительные параметры
    """
    if isinstance(event, Message):
        # Для сообщений - всегда отправляем новое
        if photo:
            await event.answer_photo(
                photo=photo,
                caption=caption or text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                **kwargs
            )
        else:
            await event.answer(
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                **kwargs
            )
    
    elif isinstance(event, CallbackQuery):
        # Для callback - пробуем редактировать, если не получается - отправляем новое
        try:
            if photo:
                # Для фото нельзя edit, удаляем и отправляем новое
                await event.message.delete()
                await event.message.answer_photo(
                    photo=photo,
                    caption=caption or text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                    **kwargs
                )
            else:
                await event.message.edit_text(
                    text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                    **kwargs
                )
        except Exception:
            # Если редактировать не получилось (сообщение удалено или нет текста)
            try:
                await event.message.delete()
            except Exception:
                pass
            await event.message.answer(
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                **kwargs
            )
        
        await event.answer()


async def delete_message(event: Union[Message, CallbackQuery]) -> None:
    """
    Универсальное удаление сообщения
    
    Args:
        event: Message или CallbackQuery
    """
    if isinstance(event, Message):
        try:
            await event.delete()
        except Exception:
            pass
    elif isinstance(event, CallbackQuery):
        try:
            await event.message.delete()
        except Exception:
            pass