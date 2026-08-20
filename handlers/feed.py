"""
Хендлер для социальной ленты питомцев
"""
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.repositories.pet_repository import PetRepository
from database.repositories.post_repository import PostRepository
from database.models import Pet, Comment, Post
from utils.user_utils import ensure_user, ensure_pet
from utils.message_utils import send_or_edit, delete_message
from keyboards.main_menu import get_main_menu_keyboard_sync
from services.feed_service import FeedService
from services.social_service import SocialService
from services.photo_service import PhotoService

logger = logging.getLogger(__name__)
router = Router()


class FeedStates(StatesGroup):
    """Состояния для ленты"""
    viewing = State()
    commenting = State()
    viewing_comments = State()


@router.message(Command("feed"))
async def cmd_feed(message: Message, session: AsyncSession, state: FSMContext) -> None:
    """Команда /feed - показать ленту"""
    await show_feed(message, session, state)


@router.callback_query(F.data == "feed")
async def feed_callback(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Кнопка ленты"""
    user = await ensure_user(callback, session)
    if not user:
        return

    await delete_message(callback)
    await show_feed(callback, session, state)
    await callback.answer()


async def show_feed(event: Message | CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    """Показать ленту"""
    user = await ensure_user(event, session)
    if not user:
        return

    pet = await ensure_pet(event, session, user)
    if not pet:
        return

    feed_service = FeedService(session)
    feed_data = await feed_service.get_feed(pet.id, limit=5)

    if not feed_data["items"]:
        text = (
            "📸 <b>Лента питомцев</b>\n\n"
            "Пока здесь пусто!\n\n"
            "Что можно сделать:\n"
            "📷 Опубликовать фото в альбоме\n"
            "👀 Посмотреть случайных питомцев\n"
            "🤝 Подписаться на друзей\n"
            "✍️ Написать пост с фото"
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📸 Новый пост", callback_data="feed_new_post")],
                [InlineKeyboardButton(text="🔙 В меню", callback_data="main_menu")]
            ]
        )
        await send_or_edit(event, text, reply_markup=keyboard)
        return

    await show_feed_item(event, session, state, feed_data, 0)


async def show_feed_item(
    event: Message | CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    feed_data: dict,
    index: int
) -> None:
    """Показать конкретный элемент ленты"""
    items = feed_data["items"]
    if index >= len(items):
        await send_or_edit(event, "📸 <b>Лента</b>\n\nЭто все посты!", reply_markup=get_main_menu_keyboard_sync())
        return

    item = items[index]
    total = len(items)

    await state.update_data(feed_index=index, feed_items=items)
    await state.set_state(FeedStates.viewing)

    feed_service = FeedService(session)

    text = f"📸 <b>Лента питомцев</b>  ({index + 1}/{total})\n\n"

    if item["type"] == "post":
        text += await feed_service.format_post(item["data"])
        photo_file_id = item["data"].get("photo_file_id")
    else:  # random_pet
        text += await feed_service.format_random_pet(item["data"])
        photo_file_id = item["data"].get("photo_file_id")

    user = await ensure_user(event, session)
    if not user:
        return

    pet = await ensure_pet(event, session, user)
    if not pet:
        return

    is_subscribed = False
    if item["type"] == "random_pet":
        is_subscribed = await feed_service.is_subscribed(pet.id, item["data"]["id"])

    keyboard = get_feed_keyboard(index, total, item, is_subscribed)

    if photo_file_id:
        if isinstance(event, Message):
            await event.answer_photo(
                photo=photo_file_id,
                caption=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        elif isinstance(event, CallbackQuery):
            try:
                await event.message.delete()
            except Exception:
                pass
            await event.message.answer_photo(
                photo=photo_file_id,
                caption=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            await event.answer()
    else:
        if isinstance(event, Message):
            await event.answer(text, reply_markup=keyboard, parse_mode="HTML")
        elif isinstance(event, CallbackQuery):
            await send_or_edit(event, text, reply_markup=keyboard)


def get_feed_keyboard(index: int, total: int, item: dict, is_subscribed: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура для ленты"""
    keyboard = []

    nav_buttons = []
    if index > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"feed_prev_{index}"))
    if index < total - 1:
        nav_buttons.append(InlineKeyboardButton(text="Вперёд ▶️", callback_data=f"feed_next_{index}"))
    if nav_buttons:
        keyboard.append(nav_buttons)

    if item["type"] == "post":
        post = item["data"]
        keyboard.append([
            InlineKeyboardButton(text="❤️ Лайк", callback_data=f"feed_like_{post['id']}"),
            InlineKeyboardButton(text="💬 Коммент", callback_data=f"feed_comment_{post['id']}"),
            InlineKeyboardButton(text="👁️ Все комменты", callback_data=f"feed_view_comments_{post['id']}")
        ])
        keyboard.append([
            InlineKeyboardButton(text="🎁 Подарок", callback_data=f"feed_gift_{post['pet_id']}")
        ])
        if post.get("has_liked"):
            keyboard.append([
                InlineKeyboardButton(text="💔 Убрать лайк", callback_data=f"feed_unlike_{post['id']}")
            ])

    elif item["type"] == "random_pet":
        pet_data = item["data"]

        row = [
            InlineKeyboardButton(text="❤️ Лайк", callback_data=f"feed_rand_like_{pet_data['id']}"),
            InlineKeyboardButton(text="🎁 Подарок", callback_data=f"feed_rand_gift_{pet_data['id']}")
        ]

        if is_subscribed:
            row.insert(1, InlineKeyboardButton(text="➖ Отписаться", callback_data=f"feed_unsubscribe_{pet_data['id']}"))
        else:
            row.insert(1, InlineKeyboardButton(text="➕ Следить", callback_data=f"feed_subscribe_{pet_data['id']}"))

        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton(text="📸 Новый пост", callback_data="feed_new_post"),
        InlineKeyboardButton(text="🔙 В меню", callback_data="main_menu")
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@router.callback_query(FeedStates.viewing, F.data.startswith("feed_prev_"))
async def feed_prev(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    current = data.get("feed_index", 0)
    items = data.get("feed_items", [])
    try:
        await callback.message.delete()
    except Exception:
        pass
    await show_feed_item(callback, session, state, {"items": items}, current - 1)
    await callback.answer()


@router.callback_query(FeedStates.viewing, F.data.startswith("feed_next_"))
async def feed_next(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    current = data.get("feed_index", 0)
    items = data.get("feed_items", [])
    try:
        await callback.message.delete()
    except Exception:
        pass
    await show_feed_item(callback, session, state, {"items": items}, current + 1)
    await callback.answer()


# ============================================================
# ЛАЙКИ ПОСТОВ
# ============================================================

@router.callback_query(FeedStates.viewing, F.data.startswith("feed_like_"))
async def feed_like_post(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    post_id = int(callback.data.split("_")[2])

    user = await ensure_user(callback, session)
    if not user:
        return

    feed_service = FeedService(session)
    result = await feed_service.like_post(user.id, post_id)

    await callback.answer(result["message"], show_alert=False)

    # ===== ОБНОВЛЯЕМ ЛЕНТУ =====
    pet = await ensure_pet(callback, session, user)
    if pet:
        await show_feed(callback, session, state)
    else:
        await callback.answer("❌ Ошибка обновления ленты", show_alert=True)


@router.callback_query(FeedStates.viewing, F.data.startswith("feed_unlike_"))
async def feed_unlike_post(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    post_id = int(callback.data.split("_")[2])

    user = await ensure_user(callback, session)
    if not user:
        return

    feed_service = FeedService(session)
    result = await feed_service.unlike_post(user.id, post_id)

    await callback.answer(result["message"], show_alert=False)

    # ===== ОБНОВЛЯЕМ ЛЕНТУ =====
    pet = await ensure_pet(callback, session, user)
    if pet:
        await show_feed(callback, session, state)
    else:
        await callback.answer("❌ Ошибка обновления ленты", show_alert=True)


# ============================================================
# КОММЕНТАРИИ
# ============================================================

@router.callback_query(FeedStates.viewing, F.data.startswith("feed_comment_"))
async def feed_comment_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    post_id = int(callback.data.split("_")[2])
    await state.update_data(commenting_post_id=post_id)
    await state.set_state(FeedStates.commenting)

    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.message.answer(
        "💬 <b>Напиши комментарий</b>\n\n"
        "Отправь сообщение (до 200 символов)\n"
        "Или нажми 'Отмена'",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="feed_comment_cancel")]
            ]
        ),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(FeedStates.commenting)
async def feed_comment_send(message: Message, state: FSMContext, session: AsyncSession) -> None:
    text = message.text.strip()
    if len(text) > 200:
        await message.answer("❌ Комментарий не должен превышать 200 символов")
        return

    data = await state.get_data()
    post_id = data.get("commenting_post_id")
    if not post_id:
        await state.clear()
        await message.answer("❌ Ошибка: пост не найден")
        return

    user = await ensure_user(message, session)
    if not user:
        return

    feed_service = FeedService(session)
    result = await feed_service.add_comment(user.id, post_id, text)

    await state.clear()

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📸 Лента", callback_data="feed")],
            [InlineKeyboardButton(text="🔙 В меню", callback_data="main_menu")]
        ]
    )

    if result["success"]:
        await message.answer("💬 Комментарий добавлен! ✅", reply_markup=keyboard)
    else:
        await message.answer(f"❌ {result['message']}")


@router.callback_query(FeedStates.commenting, F.data == "feed_comment_cancel")
async def feed_comment_cancel(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer("❌ Комментирование отменено")
    await callback.answer()


# ============================================================
# ПРОСМОТР ВСЕХ КОММЕНТАРИЕВ К ПОСТУ
# ============================================================

@router.callback_query(FeedStates.viewing, F.data.startswith("feed_view_comments_"))
async def feed_view_comments(callback: CallbackQuery, session: AsyncSession) -> None:
    """Просмотр всех комментариев к посту"""
    post_id = int(callback.data.split("_")[3])

    user = await ensure_user(callback, session)
    if not user:
        return

    post_repo = PostRepository(session)
    comments = await post_repo.get_comments(post_id, limit=20)

    if not comments:
        await callback.answer("💬 Комментариев пока нет", show_alert=True)
        return

    text = "💬 <b>Комментарии к посту</b>\n\n"

    for i, comment in enumerate(comments, 1):
        pet_repo = PetRepository(session)
        pet = await pet_repo.get_by_id(comment.get("pet_id"))
        pet_name = pet.name if pet else "Питомец"
        text += f"{i}. <b>{pet_name}</b>: {comment.get('text', '')}\n"
        created_at = comment.get('created_at', '')
        if created_at:
            if isinstance(created_at, str):
                created_at = created_at[:16].replace('T', ' ')
            text += f"   🕐 {created_at}\n\n"
        else:
            text += "   🕐 Неизвестно\n\n"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💬 Написать комментарий", callback_data=f"feed_comment_{post_id}")],
            [InlineKeyboardButton(text="🗑️ Удалить свой комментарий", callback_data=f"feed_delete_comment_improved_{post_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="feed")]
        ]
    )

    await send_or_edit(callback, text, reply_markup=keyboard)
    await callback.answer()


# ============================================================
# УДАЛЕНИЕ КОММЕНТАРИЯ (УЛУЧШЕННОЕ)
# ============================================================

@router.callback_query(F.data.startswith("feed_delete_specific_"))
async def feed_delete_specific_comment(callback: CallbackQuery, session: AsyncSession) -> None:
    """Удалить конкретный комментарий по ID"""
    parts = callback.data.split("_")
    post_id = int(parts[3])
    comment_id = int(parts[4])

    user = await ensure_user(callback, session)
    if not user:
        return

    comment = await session.get(Comment, comment_id)

    if not comment or comment.user_id != user.id:
        await callback.answer("❌ Комментарий не найден или не принадлежит тебе", show_alert=True)
        return

    post_repo = PostRepository(session)
    await post_repo.delete_comment(comment_id)
    await session.flush()

    await callback.answer("🗑️ Комментарий удалён!", show_alert=True)
    await feed_view_comments(callback, session)


@router.callback_query(F.data.startswith("feed_delete_comment_improved_"))
async def feed_delete_comment_improved(callback: CallbackQuery, session: AsyncSession) -> None:
    """Удалить комментарий - показывает список комментариев пользователя для выбора"""
    parts = callback.data.split("_")
    post_id = int(parts[4])

    user = await ensure_user(callback, session)
    if not user:
        return

    pet = await ensure_pet(callback, session, user)
    if not pet:
        return

    post_repo = PostRepository(session)
    comments = await post_repo.get_comments(post_id, limit=50)

    user_comments = [c for c in comments if c.get("user_id") == user.id]

    if not user_comments:
        await callback.answer("❌ У тебя нет комментариев к этому посту", show_alert=True)
        return

    if len(user_comments) == 1:
        await post_repo.delete_comment(user_comments[0]["id"])
        await session.flush()
        await callback.answer("🗑️ Комментарий удалён!", show_alert=True)
        await feed_view_comments(callback, session)
        return

    keyboard = []
    for i, comment in enumerate(user_comments[:10]):
        preview = comment.get("text", "")[:30] + ("..." if len(comment.get("text", "")) > 30 else "")
        keyboard.append([
            InlineKeyboardButton(
                text=f"🗑️ {i+1}. {preview}",
                callback_data=f"feed_delete_specific_{post_id}_{comment['id']}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data=f"feed_view_comments_{post_id}")
    ])

    await send_or_edit(
        callback,
        text=f"🗑️ <b>Выбери комментарий для удаления</b>\n\n"
             f"Всего твоих комментариев: {len(user_comments)}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML"
    )
    await callback.answer()


# ============================================================
# ПОДПИСКИ В ЛЕНТЕ
# ============================================================

@router.callback_query(F.data.startswith("feed_subscribe_"))
async def feed_subscribe(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Подписаться на питомца из ленты"""
    target_pet_id = int(callback.data.split("_")[2])

    user = await ensure_user(callback, session)
    if not user:
        return

    pet = await ensure_pet(callback, session, user)
    if not pet:
        return

    if pet.id == target_pet_id:
        await callback.answer("❌ Нельзя подписаться на себя", show_alert=True)
        return

    feed_service = FeedService(session)
    result = await feed_service.subscribe(pet.id, target_pet_id)

    await callback.answer(result["message"], show_alert=False)

    try:
        await callback.message.delete()
    except Exception:
        pass

    await show_feed(callback, session, state)


@router.callback_query(F.data.startswith("feed_unsubscribe_"))
async def feed_unsubscribe(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Отписаться от питомца из ленты"""
    target_pet_id = int(callback.data.split("_")[2])

    user = await ensure_user(callback, session)
    if not user:
        return

    pet = await ensure_pet(callback, session, user)
    if not pet:
        return

    feed_service = FeedService(session)
    result = await feed_service.unsubscribe(pet.id, target_pet_id)

    await callback.answer(result["message"], show_alert=False)

    try:
        await callback.message.delete()
    except Exception:
        pass

    await show_feed(callback, session, state)


# ============================================================
# ПОДАРКИ ИЗ ЛЕНТЫ
# ============================================================

@router.callback_query(FeedStates.viewing, F.data.startswith("feed_gift_"))
async def feed_gift_from_post(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    pet_id = int(callback.data.split("_")[2])

    pet_repo = PetRepository(session)
    pet = await pet_repo.get_by_id(pet_id)
    if not pet:
        await callback.answer("❌ Питомец не найден", show_alert=True)
        return

    await state.update_data(to_user_id=pet.user_id, to_pet_name=pet.name)

    user = await ensure_user(callback, session)
    if not user:
        return

    from handlers.social import show_gift_item_selection
    await show_gift_item_selection(callback, state, session, user, pet.name)


@router.callback_query(F.data.startswith("feed_rand_gift_"))
async def feed_rand_gift(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    pet_id = int(callback.data.split("_")[3])

    pet_repo = PetRepository(session)
    pet = await pet_repo.get_by_id(pet_id)
    if not pet:
        await callback.answer("❌ Питомец не найден", show_alert=True)
        return

    await state.update_data(to_user_id=pet.user_id, to_pet_name=pet.name)

    user = await ensure_user(callback, session)
    if not user:
        return

    from handlers.social import show_gift_item_selection
    await show_gift_item_selection(callback, state, session, user, pet.name)


@router.callback_query(F.data.startswith("feed_rand_like_"))
async def feed_rand_like(callback: CallbackQuery, session: AsyncSession) -> None:
    pet_id = int(callback.data.split("_")[3])

    user = await ensure_user(callback, session)
    if not user:
        return

    social_service = SocialService(session)
    result = await social_service.like_pet(user.id, pet_id)

    await callback.answer(result.get("message", "❤️ Лайк поставлен!"), show_alert=False)


# ============================================================
# НОВЫЙ ПОСТ
# ============================================================

@router.callback_query(F.data == "feed_new_post")
async def feed_new_post(callback: CallbackQuery, session: AsyncSession) -> None:
    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.message.answer(
        "📸 <b>Новый пост</b>\n\n"
        "Отправь новое фото с подписью\n\n"
        "Или выбери фото из альбома:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📸 Выбрать из альбома", callback_data="album_select_for_post")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="feed")]
            ]
        ),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(F.photo)
async def feed_photo_handler(message: Message, session: AsyncSession) -> None:
    user = await ensure_user(message, session)
    if not user:
        return

    pet = await ensure_pet(message, session, user)
    if not pet:
        return

    photo_service = PhotoService(session)

    file_id = message.photo[-1].file_id
    caption = message.caption or ""

    photo = await photo_service.add_photo(pet.id, file_id, caption)

    if not photo:
        await message.answer("❌ Ошибка при сохранении фото")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📸 Опубликовать в ленте", callback_data=f"feed_publish_{photo.id}"),
                InlineKeyboardButton(text="❌ Нет", callback_data="feed_cancel_publish")
            ]
        ]
    )

    await message.answer(
        "📸 Фото добавлено в альбом!\n\n"
        "Хочешь опубликовать его в ленте?",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("feed_publish_"))
async def feed_publish(callback: CallbackQuery, session: AsyncSession) -> None:
    photo_id = int(callback.data.split("_")[2])

    user = await ensure_user(callback, session)
    if not user:
        return

    pet = await ensure_pet(callback, session, user)
    if not pet:
        return

    photo_service = PhotoService(session)
    photo = await photo_service.get_by_id(photo_id)

    if not photo:
        await callback.answer("❌ Фото не найдено", show_alert=True)
        return

    # ===== ПРОВЕРЯЕМ, НЕ СОЗДАН ЛИ УЖЕ ПОСТ =====
    result = await session.execute(
        select(Post).where(Post.photo_id == photo_id)
    )
    existing_post = result.scalar_one_or_none()
    
    if existing_post:
        await callback.answer("⚠️ Пост для этого фото уже опубликован!", show_alert=True)
        return

    feed_service = FeedService(session)
    result = await feed_service.create_post(
        pet_id=pet.id,
        photo_id=photo.id,
        caption=photo.caption,
        is_published=True
    )

    if result["success"]:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📸 Лента", callback_data="feed")],
                [InlineKeyboardButton(text="🔙 В меню", callback_data="main_menu")]
            ]
        )
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(
            "📸 Пост опубликован в ленте! ✅",
            reply_markup=keyboard
        )
    else:
        await callback.message.edit_text(f"❌ {result['message']}")
    await callback.answer()


@router.callback_query(F.data == "feed_cancel_publish")
async def feed_cancel_publish(callback: CallbackQuery, session: AsyncSession) -> None:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📸 Лента", callback_data="feed")],
            [InlineKeyboardButton(text="🔙 В меню", callback_data="main_menu")]
        ]
    )
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer("📸 Фото сохранено в альбоме", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "album_select_for_post")
async def album_select_for_post(callback: CallbackQuery, session: AsyncSession) -> None:
    """Показать фото из альбома для публикации"""
    user = await ensure_user(callback, session)
    if not user:
        return

    pet = await ensure_pet(callback, session, user)
    if not pet:
        return

    photo_service = PhotoService(session)
    photos = await photo_service.get_photos(pet.id, limit=10)

    if not photos:
        await callback.answer("📸 У питомца пока нет фото в альбоме", show_alert=True)
        return

    keyboard = []
    for photo in photos[:5]:
        preview = photo.caption[:20] + "..." if photo.caption and len(photo.caption) > 20 else (photo.caption or "Без подписи")
        keyboard.append([
            InlineKeyboardButton(
                text=f"📸 {preview}",
                callback_data=f"feed_publish_{photo.id}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="feed_new_post")
    ])

    await callback.message.edit_text(
        f"📸 <b>Выбери фото для публикации</b>\n\n"
        f"Всего фото: {len(photos)}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML"
    )
    await callback.answer()


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ КНОПКИ
# ============================================================

@router.callback_query(F.data == "feed_back")
async def feed_back(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    await show_feed(callback, session, state)
    await callback.answer()