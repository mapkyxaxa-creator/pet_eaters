from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from database.repositories.user_repository import UserRepository
from database.repositories.social_repository import SocialRepository
from database.repositories.inventory_repository import InventoryRepository
from database.repositories.pet_repository import PetRepository
from services.data_loader import data_loader
from services.social_service import SocialService
from utils.user_utils import ensure_user
from utils.message_utils import send_or_edit, delete_message
from keyboards.main_menu import get_main_menu_keyboard

router = Router()


@router.callback_query(F.data == "mailbox")
async def show_mailbox(callback: CallbackQuery, session: AsyncSession) -> None:
    """Показать почту (полученные подарки)"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    social_repo = SocialRepository(session)
    gifts = await social_repo.get_received_gifts(user.id, limit=20)
    
    if not gifts:
        await send_or_edit(
            callback,
            text="📬 <b>Моя почта</b>\n\n"
                 "📭 Пока нет подарков.\n"
                 "Отправь подарок другу или подожди, пока кто-то отправит тебе! 🎁",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
                ]
            )
        )
        await callback.answer()
        return
    
    # Подсчитываем непрочитанные
    unread_count = sum(1 for g in gifts if not g.is_read)
    
    text = f"📬 <b>Моя почта</b>"
    if unread_count > 0:
        text += f" 🆕 ({unread_count} новых)"
    text += "\n\n"
    
    # Отмечаем все как прочитанные
    for gift in gifts:
        if not gift.is_read:
            await social_repo.mark_gift_as_read(gift.id)
    
    # Показываем подарки с кнопкой "Получить"
    foods = data_loader.get("foods", {})
    keyboard = []
    
    for gift in gifts[:10]:
        food = foods.get(gift.item_id, {})
        emoji = food.get("emoji", "🎁")
        name = food.get("name", gift.item_id)
        
        # Получаем имя отправителя
        sender = await UserRepository(session).get_by_id(gift.from_user_id)
        sender_name = sender.first_name or sender.username or "Неизвестно"
        
        status = "🆕" if not gift.is_read else "📦"
        claimed_status = " ✅" if gift.is_claimed else ""
        
        text += f"{status} {emoji} <b>{name}</b> x{gift.quantity}{claimed_status}\n"
        text += f"   👤 От: {sender_name}\n"
        if gift.message:
            text += f"   💬 {gift.message}\n"
        text += f"   🕐 {gift.created_at.strftime('%d.%m %H:%M')}\n"
        
        # Кнопка "Получить" только если подарок ещё не получен
        if not gift.is_claimed:
            text += f"\n"
            keyboard.append([
                InlineKeyboardButton(
                    text=f"📥 Получить {emoji} {name}",
                    callback_data=f"claim_gift_{gift.id}"
                )
            ])
        else:
            text += f"   ✅ <i>Получен {gift.claimed_at.strftime('%d.%m %H:%M')}</i>\n"
        
        text += "\n"
    
    if len(gifts) > 10:
        text += f"\n<i>...и еще {len(gifts) - 10} подарков</i>"
    
    # Клавиатура
    keyboard.append([
        InlineKeyboardButton(text="📥 Получить все", callback_data="claim_all_gifts"),
        InlineKeyboardButton(text="🔄 Обновить", callback_data="mailbox"),
    ])
    keyboard.append([
        InlineKeyboardButton(text="🗑️ Очистить", callback_data="mailbox_clear"),
    ])
    keyboard.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"),
    ])
    
    await send_or_edit(
        callback,
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@router.callback_query(F.data == "mailbox_clear")
async def clear_mailbox(callback: CallbackQuery, session: AsyncSession) -> None:
    """Очистить почту (удалить все полученные подарки)"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    social_repo = SocialRepository(session)
    gifts = await social_repo.get_received_gifts(user.id, limit=50)
    
    deleted_count = 0
    for gift in gifts:
        if gift.is_claimed:
            await session.delete(gift)
            deleted_count += 1
    
    if deleted_count == 0:
        await callback.answer("📭 Нет полученных подарков для удаления", show_alert=True)
        return
    
    await session.flush()
    await callback.answer(f"🗑️ Удалено {deleted_count} подарков", show_alert=True)
    
    # Обновляем почту
    await show_mailbox(callback, session)


@router.callback_query(F.data.startswith("claim_gift_"))
async def claim_gift(callback: CallbackQuery, session: AsyncSession) -> None:
    """Забрать подарок из почты"""
    gift_id = int(callback.data.split("_")[2])
    
    user = await ensure_user(callback, session)
    if not user:
        return
    
    social_repo = SocialRepository(session)
    gift = await social_repo.get_gift_by_id(gift_id)
    
    if not gift or gift.to_user_id != user.id:
        await callback.answer("❌ Подарок не найден", show_alert=True)
        return
    
    if gift.is_claimed:
        await callback.answer("❌ Подарок уже получен", show_alert=True)
        return
    
    # ===== ОБРАБОТКА В ЗАВИСИМОСТИ ОТ ТИПА =====
    foods = data_loader.get("foods", {})
    food = foods.get(gift.item_id, {})
    food_name = food.get("name", gift.item_id)
    food_emoji = food.get("emoji", "🍽️")
    result_text = ""
    success = False
    
    if gift.item_type == "food":
        # Добавляем еду в инвентарь
        inventory_repo = InventoryRepository(session)
        await inventory_repo.add_item(user.id, gift.item_id, gift.quantity)
        result_text = f"{food_emoji} {food_name} x{gift.quantity} добавлено в инвентарь!"
        success = True
    
    elif gift.item_type == "cosmetic":
        # В БУДУЩЕМ: добавляем косметику
        result_text = "🎨 Косметика будет доступна в следующем обновлении!"
        success = True
    
    elif gift.item_type == "frame":
        # В БУДУЩЕМ: добавляем рамку
        result_text = "🖼️ Рамка будет доступна в следующем обновлении!"
        success = True
    
    elif gift.item_type == "title":
        # В БУДУЩЕМ: добавляем титул
        result_text = "👑 Титул будет доступен в следующем обновлении!"
        success = True
    
    else:
        await callback.answer("❌ Неизвестный тип подарка", show_alert=True)
        return
    
    if not success:
        await callback.answer("❌ Ошибка получения подарка", show_alert=True)
        return
    
    # Отмечаем как полученный
    gift.is_claimed = True
    gift.claimed_at = datetime.utcnow()
    await session.flush()
    
    # Показываем результат
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📬 Почта", callback_data="mailbox")],
            [InlineKeyboardButton(text="🔙 В меню", callback_data="main_menu")]
        ]
    )
    
    await callback.message.edit_text(
        f"✅ <b>Подарок получен!</b>\n\n{result_text}",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "claim_all_gifts")
async def claim_all_gifts(callback: CallbackQuery, session: AsyncSession) -> None:
    """Забрать все подарки из почты"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    social_repo = SocialRepository(session)
    gifts = await social_repo.get_received_gifts(user.id, limit=50)
    
    unclaimed = [g for g in gifts if not g.is_claimed]
    if not unclaimed:
        await callback.answer("❌ Нет подарков для получения", show_alert=True)
        return
    
    inventory_repo = InventoryRepository(session)
    claimed_count = 0
    
    for gift in unclaimed:
        # Проверяем тип подарка
        if gift.item_type == "food":
            await inventory_repo.add_item(user.id, gift.item_id, gift.quantity)
            gift.is_claimed = True
            gift.claimed_at = datetime.utcnow()
            claimed_count += 1
        elif gift.item_type in ["cosmetic", "frame", "title"]:
            # Временно отмечаем как полученные (для будущих обновлений)
            gift.is_claimed = True
            gift.claimed_at = datetime.utcnow()
            claimed_count += 1
    
    await session.flush()
    await callback.answer(f"✅ Получено {claimed_count} подарков!", show_alert=True)
    
    # Обновляем почту
    await show_mailbox(callback, session)
