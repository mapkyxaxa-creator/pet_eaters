from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories.user_repository import UserRepository
from database.repositories.pet_repository import PetRepository
from services.data_loader import data_loader
from services.achievement_service import AchievementService
from services.photo_service import PhotoService
from services.payment_service import PaymentService
from services.feed_service import FeedService
from utils.formatting import format_pet_profile
from utils.user_utils import ensure_user, ensure_pet
from utils.message_utils import send_or_edit, delete_message
from keyboards.main_menu import get_main_menu_keyboard_sync

router = Router()


@router.message(Command("profile"))
async def cmd_profile(message: Message, session: AsyncSession) -> None:
    """Команда /profile - просмотр профиля"""
    await show_my_profile(message, session)


async def show_my_profile(message: Message, session: AsyncSession) -> None:
    """Показать свой профиль"""
    user = await ensure_user(message, session)
    if not user:
        return
    
    pet = await ensure_pet(message, session, user)
    if not pet:
        return
    
    photo_service = PhotoService(session)
    main_photo = await photo_service.get_main_photo(pet.id)
    photo_to_show = main_photo.telegram_file_id if main_photo else pet.photo_file_id
    
    characters = data_loader.get("characters", {})
    character = characters.get(pet.character_id, {})
    
    payment_service = PaymentService(session)
    balance = await payment_service.get_balance(message.from_user.id)
    premium_balance = balance.get("premium_currency", 0) if balance.get("success") else 0
    
    # ===== ПОЛУЧАЕМ ТИТУЛ =====
    titles_data = data_loader.get("titles", {})
    current_title = titles_data.get(pet.title_id, {})
    
    if not current_title and pet.title_id:
        for tid, tdata in titles_data.items():
            if tdata.get("name") == pet.title_id:
                current_title = tdata
                pet.title_id = tid
                await session.flush()
                break
    
    title_text = f"{current_title.get('emoji', '')} {current_title.get('name', 'Нет титула')}" if pet.title_id else "🐣 Новичок"
    
    # ===== ПОДПИСКИ =====
    feed_service = FeedService(session)
    subscribers_count = await feed_service.get_subscribers_count(pet.id)
    subscriptions_count = await feed_service.get_subscriptions_count(pet.id)
    
    hunger_percent = pet.get_hunger_percent()
    hunger_emoji = "😊"
    if hunger_percent >= 150:
        hunger_emoji = "💀"
    elif hunger_percent >= 120:
        hunger_emoji = "🤢"
    elif hunger_percent >= 100:
        hunger_emoji = "😋"
    
    achievement_service = AchievementService(session)
    unlocked = await achievement_service.get_unlocked_achievements(pet.id)
    
    profile_text = (
        f"🐾 <b>{pet.name}</b>\n"
        f"{character.get('emoji', '')} <b>Характер:</b> {character.get('name', 'Неизвестно')}\n\n"
        f"💰 <b>Монет:</b> {user.coins} 🪙\n"
        f"🐾 <b>Лапок:</b> {premium_balance}\n"
        f"📊 <b>Уровень:</b> {pet.level} ({pet.experience}/... XP)\n"
        f"❤️ <b>Счастье:</b> {pet.happiness}/100\n"
        f"⚡ <b>Энергия:</b> {pet.energy}/100\n"
        f"{hunger_emoji} <b>Сытость:</b> {pet.hunger}/{pet.stomach_capacity} ({hunger_percent:.0f}%)\n\n"
        f"🍀 <b>Удача:</b> {pet.luck*100:.1f}%\n"
        f"👃 <b>Нюх:</b> {pet.smell}\n"
        f"🍽️ <b>Скорость еды:</b> {pet.eating_speed}\n"
        f"\n🆔 <b>ID питомца:</b> <code>{pet.game_id}</code>\n"
        f"👑 <b>Титул:</b> {title_text}\n"
        f"👥 <b>Подписчиков:</b> {subscribers_count}  🤝 <b>Подписок:</b> {subscriptions_count}\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"🍽️ Съедено: {pet.total_eaten}\n"
        f"🗺️ Приключений: {pet.total_adventures}\n"
        f"🏆 Побед: {pet.competition_wins}\n"
        f"❤️ Лайков: {pet.total_likes}\n"
        f"🏅 Достижений: {len(unlocked)}/{len(achievement_service.achievements_data)}\n"
    )
    
    if pet.cosmetic_id:
        cosmetics_data = data_loader.get("cosmetics", {}).get("cosmetics", [])
        for c in cosmetics_data:
            if c.get("id") == pet.cosmetic_id:
                profile_text += f"🎨 Косметика: {c.get('emoji')} {c.get('name')}\n"
                break
    
    if pet.frame_id:
        frames_data = data_loader.get("frames", {}).get("frames", [])
        for f in frames_data:
            if f.get("id") == pet.frame_id:
                profile_text += f"🖼️ Рамка: {f.get('emoji')} {f.get('name')}\n"
                break
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📤 Поделиться", callback_data=f"share_{pet.id}"),
                InlineKeyboardButton(text="📸 Альбом", callback_data="my_photos"),
            ],
            [
                InlineKeyboardButton(text="👥 Подписчики", callback_data=f"profile_subscribers_{pet.id}"),
                InlineKeyboardButton(text="📖 Сюжет", callback_data="story_profile"),
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")
            ]
        ]
    )
    
    await message.answer_photo(
        photo=photo_to_show,
        caption=profile_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )


async def show_profile_from_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Показать профиль из callback"""
    user = await ensure_user(callback, session)
    if not user:
        return
    
    await delete_message(callback)
    
    pet = await ensure_pet(callback, session, user)
    if not pet:
        return
    
    photo_service = PhotoService(session)
    main_photo = await photo_service.get_main_photo(pet.id)
    photo_to_show = main_photo.telegram_file_id if main_photo else pet.photo_file_id
    
    characters = data_loader.get("characters", {})
    character = characters.get(pet.character_id, {})
    
    payment_service = PaymentService(session)
    balance = await payment_service.get_balance(callback.from_user.id)
    premium_balance = balance.get("premium_currency", 0) if balance.get("success") else 0
    
    titles_data = data_loader.get("titles", {})
    current_title = titles_data.get(pet.title_id, {})
    
    if not current_title and pet.title_id:
        for tid, tdata in titles_data.items():
            if tdata.get("name") == pet.title_id:
                current_title = tdata
                pet.title_id = tid
                await session.flush()
                break
    
    title_text = f"{current_title.get('emoji', '')} {current_title.get('name', 'Нет титула')}" if pet.title_id else "🐣 Новичок"
    
    feed_service = FeedService(session)
    subscribers_count = await feed_service.get_subscribers_count(pet.id)
    subscriptions_count = await feed_service.get_subscriptions_count(pet.id)
    
    hunger_percent = pet.get_hunger_percent()
    hunger_emoji = "😊"
    if hunger_percent >= 150:
        hunger_emoji = "💀"
    elif hunger_percent >= 120:
        hunger_emoji = "🤢"
    elif hunger_percent >= 100:
        hunger_emoji = "😋"
    
    achievement_service = AchievementService(session)
    unlocked = await achievement_service.get_unlocked_achievements(pet.id)
    
    profile_text = (
        f"🐾 <b>{pet.name}</b>\n"
        f"{character.get('emoji', '')} <b>Характер:</b> {character.get('name', 'Неизвестно')}\n\n"
        f"💰 <b>Монет:</b> {user.coins} 🪙\n"
        f"🐾 <b>Лапок:</b> {premium_balance}\n"
        f"📊 <b>Уровень:</b> {pet.level} ({pet.experience}/... XP)\n"
        f"❤️ <b>Счастье:</b> {pet.happiness}/100\n"
        f"⚡ <b>Энергия:</b> {pet.energy}/100\n"
        f"{hunger_emoji} <b>Сытость:</b> {pet.hunger}/{pet.stomach_capacity} ({hunger_percent:.0f}%)\n\n"
        f"🍀 <b>Удача:</b> {pet.luck*100:.1f}%\n"
        f"👃 <b>Нюх:</b> {pet.smell}\n"
        f"🍽️ <b>Скорость еды:</b> {pet.eating_speed}\n"
        f"\n🆔 <b>ID питомца:</b> <code>{pet.game_id}</code>\n"
        f"👑 <b>Титул:</b> {title_text}\n"
        f"👥 <b>Подписчиков:</b> {subscribers_count}  🤝 <b>Подписок:</b> {subscriptions_count}\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"🍽️ Съедено: {pet.total_eaten}\n"
        f"🗺️ Приключений: {pet.total_adventures}\n"
        f"🏆 Побед: {pet.competition_wins}\n"
        f"❤️ Лайков: {pet.total_likes}\n"
        f"🏅 Достижений: {len(unlocked)}/{len(achievement_service.achievements_data)}\n"
    )
    
    if pet.cosmetic_id:
        cosmetics_data = data_loader.get("cosmetics", {}).get("cosmetics", [])
        for c in cosmetics_data:
            if c.get("id") == pet.cosmetic_id:
                profile_text += f"🎨 Косметика: {c.get('emoji')} {c.get('name')}\n"
                break
    
    if pet.frame_id:
        frames_data = data_loader.get("frames", {}).get("frames", [])
        for f in frames_data:
            if f.get("id") == pet.frame_id:
                profile_text += f"🖼️ Рамка: {f.get('emoji')} {f.get('name')}\n"
                break
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📤 Поделиться", callback_data=f"share_{pet.id}"),
                InlineKeyboardButton(text="📸 Альбом", callback_data="my_photos"),
            ],
            [
                InlineKeyboardButton(text="👥 Подписчики", callback_data=f"profile_subscribers_{pet.id}"),
                InlineKeyboardButton(text="📖 Сюжет", callback_data="story_profile"),
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")
            ]
        ]
    )
    
    await callback.message.answer_photo(
        photo=photo_to_show,
        caption=profile_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("profile_subscribers_"))
async def profile_subscribers(callback: CallbackQuery, session: AsyncSession) -> None:
    """Показать список подписчиков"""
    pet_id = int(callback.data.split("_")[2])
    
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet or pet.id != pet_id:
        await callback.answer("❌ Это не твой питомец", show_alert=True)
        return
    
    feed_service = FeedService(session)
    
    # Получаем подписчиков (питомцев, которые подписаны на этого)
    subscribers = await feed_service.get_subscribers_list(pet.id, limit=20)
    
    if not subscribers:
        text = "👥 <b>Подписчики</b>\n\n"
        text += "📭 У тебя пока нет подписчиков."
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="profile")]
            ]
        )
        
        await send_or_edit(callback, text, reply_markup=keyboard)
        return
    
    text = "👥 <b>Подписчики</b>\n\n"
    
    for i, sub in enumerate(subscribers, 1):
        text += f"{i}. {sub.get('emoji', '🐾')} <b>{sub.get('name', 'Питомец')}</b>\n"
        text += f"   📊 Уровень: {sub.get('level', 1)} | 🆔 {sub.get('game_id', '')}\n"
        text += f"   👤 Владелец: {sub.get('owner_name', 'Неизвестно')}\n\n"
    
    if len(subscribers) > 20:
        text += f"\n<i>...и еще {len(subscribers) - 20} подписчиков</i>"
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="profile")]
        ]
    )
    
    await send_or_edit(callback, text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("share_"))
async def share_profile(callback: CallbackQuery, session: AsyncSession) -> None:
    """Поделиться профилем питомца"""
    pet_id = int(callback.data.split("_")[1])
    
    user = await ensure_user(callback, session)
    if not user:
        return
    
    pet = await ensure_pet(callback, session, user)
    if not pet or pet.id != pet_id:
        await callback.answer("❌ Это не твой питомец", show_alert=True)
        return
    
    bot_username = (await callback.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start=pet_{pet.game_id}"
    
    text = (
        f"📤 <b>Поделиться профилем</b>\n\n"
        f"🐶 Это мой питомец <b>{pet.name}</b>!\n"
        f"Заходи посмотреть 👇\n\n"
        f"<code>{link}</code>\n\n"
        f"🆔 ID питомца: <code>{pet.game_id}</code>\n\n"
        f"<i>Отправь эту ссылку друзьям, чтобы они могли посмотреть на твоего питомца!</i>"
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="📋 Скопировать ссылку",
                callback_data=f"copy_link_{pet.id}"
            )],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="profile")]
        ]
    )
    
    await send_or_edit(callback, text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "story_profile")
async def story_profile_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Переход к сюжету из профиля"""
    from handlers.story import show_story_from_callback
    await delete_message(callback)
    await show_story_from_callback(callback, session)
    await callback.answer()


@router.callback_query(F.data == "profile")
async def profile_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Callback для кнопки 'Профиль'"""
    await show_profile_from_callback(callback, session)