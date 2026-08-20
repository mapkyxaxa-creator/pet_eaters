from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, PreCheckoutQuery
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from services.payment_service import PaymentService
from utils.user_utils import ensure_user, get_user_id
from utils.message_utils import send_or_edit, delete_message

router = Router()

# ==================== РЕЖИМ РАБОТЫ ====================
# "test" — имитация покупки (для разработки)
# "live" — реальные платежи через Telegram Stars
SHOP_MODE = "live"  # Измени на "test" для отладки


# ==================== ГЛАВНОЕ МЕНЮ МАГАЗИНА ЛАПОК ====================

async def show_shop_premium(event: Message | CallbackQuery, session: AsyncSession) -> None:
    """Показать магазин лапок"""
    user = await ensure_user(event, session)
    if not user:
        return

    payment_service = PaymentService(session)
    packages = await payment_service.get_packages()
    balance = await payment_service.get_balance(get_user_id(event))

    text = f"🐾 <b>Магазин лапок</b>\n\n"
    text += f"💰 У тебя: {balance.get('premium_currency', 0)} 🐾 лапок\n\n"
    text += f"<b>Выбери пакет:</b>\n\n"

    keyboard = []

    for package in packages:
        emoji = package.get("emoji", "🐾")
        name = package.get("name", "")
        amount = package.get("amount", 0)
        price = package.get("price", 0)
        bonus = package.get("bonus", 0)
        stars_price = package.get("stars_price", 0)

        text += f"{emoji} <b>{name}</b>\n"
        text += f"   🐾 {amount} лапок"
        if bonus:
            text += f" (+{bonus} бонусных)"
        if SHOP_MODE == "test":
            text += f"\n   🧪 ТЕСТ: {price}$"
        else:
            text += f"\n   ⭐ {stars_price} Stars"
        text += "\n\n"

        keyboard.append([
            InlineKeyboardButton(
                text=f"🐾 Купить {name}",
                callback_data=f"shop_buy_package_{package.get('id')}"
            )
        ])

    # Добавляем индикатор режима
    mode_text = "🧪 ТЕСТОВЫЙ РЕЖИМ" if SHOP_MODE == "test" else "💎 РЕАЛЬНЫЕ ПЛАТЕЖИ"
    keyboard.append([
        InlineKeyboardButton(
            text=f"ℹ️ {mode_text}",
            callback_data="shop_mode_info"
        )
    ])
    keyboard.append([
        InlineKeyboardButton(text="🔙 В меню магазина", callback_data="shop_main")
    ])

    await send_or_edit(event, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))


# ==================== ПОКУПКА ПАКЕТА ====================

@router.callback_query(F.data.startswith("shop_buy_package_"))
async def shop_buy_package(callback: CallbackQuery, session: AsyncSession) -> None:
    """Покупка пакета лапок"""
    user = await ensure_user(callback, session)
    if not user:
        return

    package_id = callback.data.split("_", 3)[3]

    payment_service = PaymentService(session)
    package = await payment_service.get_package(package_id)

    if not package:
        await callback.answer("❌ Пакет не найден", show_alert=True)
        return

    if SHOP_MODE == "test":
        # ===== ТЕСТОВЫЙ РЕЖИМ: имитация покупки =====
        result = await payment_service.create_payment(
            user_id=callback.from_user.id,
            package_id=package_id
        )

        if not result["success"]:
            await callback.answer(f"❌ {result['message']}", show_alert=True)
            return

        await payment_service.complete_payment(result["payment_id"])
        balance = await payment_service.get_balance(callback.from_user.id)

        await callback.answer("✅ ТЕСТ: Покупка успешна!", show_alert=True)

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🐾 Продолжить покупки", callback_data="shop_premium")],
                [InlineKeyboardButton(text="🔙 В меню магазина", callback_data="shop_main")]
            ]
        )

        await send_or_edit(
            callback,
            text=f"🧪 <b>ТЕСТОВАЯ ПОКУПКА</b>\n\n"
                 f"🎁 Пакет: {package.get('emoji')} {package.get('name')}\n"
                 f"🐾 Получено: {package.get('amount') + package.get('bonus', 0)} лапок\n\n"
                 f"💰 Твой баланс: {balance.get('premium_currency', 0)} 🐾 лапок",
            reply_markup=keyboard
        )
        return

    # ===== РЕАЛЬНЫЙ РЕЖИМ: оплата через Telegram Stars =====
    try:
        await callback.bot.send_invoice(
            chat_id=callback.from_user.id,
            title=package.get("name", "Пакет лапок"),
            description=f"{package.get('amount')} лапок для игры «Питомцы: Большой Жор»",
            payload=f"package_{package_id}",
            currency="XTR",
            prices=[
                LabeledPrice(
                    label=f"{package.get('amount')} лапок" + (f" (+{package.get('bonus')} бонусных)" if package.get('bonus') else ""),
                    amount=package.get("stars_price", 50)
                )
            ],
            start_parameter=f"buy_{package_id}",
            provider_token="",  # Для Stars обязательно пустая строка
        )
        await callback.answer()
    except Exception as e:
        await callback.answer(f"❌ Ошибка при создании платежа: {e}", show_alert=True)
        logger.error(f"Ошибка send_invoice: {e}")


# ==================== ПОДТВЕРЖДЕНИЕ ПЛАТЕЖА ====================

@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery, session: AsyncSession) -> None:
    """
    Подтверждение платежа (обязательно для Telegram Stars)
    """
    # Проверяем, что пакет существует
    payment_service = PaymentService(session)
    payload = query.invoice_payload
    package_id = payload.replace("package_", "")

    package = await payment_service.get_package(package_id)

    if not package:
        await query.answer(ok=False, error_message="❌ Пакет не найден. Попробуйте снова.")
        return

    # Всё хорошо — подтверждаем
    await query.answer(ok=True)


# ==================== УСПЕШНАЯ ОПЛАТА ====================

@router.message(F.successful_payment)
async def process_successful_payment(message: Message, session: AsyncSession) -> None:
    """
    Обработка успешной оплаты — начисляем лапки
    """
    user = await ensure_user(message, session)
    if not user:
        return

    payload = message.successful_payment.invoice_payload
    package_id = payload.replace("package_", "")

    payment_service = PaymentService(session)
    package = await payment_service.get_package(package_id)

    if not package:
        await message.answer("❌ Ошибка: пакет не найден. Обратитесь в поддержку.")
        return

    # Проверяем, не обработан ли уже этот платёж
    # (Telegram может прислать дубликат)
    transaction_id = message.successful_payment.telegram_payment_charge_id
    existing = await payment_service.payment_repo.get_by_transaction_id(transaction_id)
    if existing and existing.status == "success":
        await message.answer("✅ Этот платёж уже был обработан.")
        return

    # Создаём запись о платеже
    result = await payment_service.create_payment(
        user_id=message.from_user.id,
        package_id=package_id,
        transaction_id=transaction_id
    )

    if not result["success"]:
        await message.answer(f"❌ {result['message']}. Обратитесь в поддержку.")
        return

    # Начисляем лапки
    await payment_service.complete_payment(result["payment_id"])
    balance = await payment_service.get_balance(message.from_user.id)

    total_amount = package.get("amount", 0) + package.get("bonus", 0)

    await message.answer(
        f"✅ <b>Оплата прошла успешно!</b>\n\n"
        f"🎁 Пакет: {package.get('emoji', '🐾')} {package.get('name', '')}\n"
        f"🐾 Получено: {total_amount} лапок\n\n"
        f"💰 Твой баланс: {balance.get('premium_currency', 0)} 🐾 лапок",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🐾 Продолжить покупки", callback_data="shop_premium")],
                [InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")]
            ]
        ),
        parse_mode="HTML"
    )


# ==================== НЕУСПЕШНАЯ ОПЛАТА ====================

@router.message(F.failed_payment)
async def process_failed_payment(message: Message) -> None:
    """
    Обработка неуспешной оплаты
    """
    await message.answer(
        "❌ <b>Оплата не прошла</b>\n\n"
        "Попробуйте ещё раз позже или выберите другой способ оплаты.\n"
        "Если проблема повторяется — обратитесь в поддержку.",
        parse_mode="HTML"
    )


# ==================== ИНФОРМАЦИЯ О РЕЖИМЕ ====================

@router.callback_query(F.data == "shop_mode_info")
async def shop_mode_info(callback: CallbackQuery) -> None:
    """Показать информацию о режиме магазина"""
    if SHOP_MODE == "test":
        text = (
            "🧪 <b>ТЕСТОВЫЙ РЕЖИМ</b>\n\n"
            "В этом режиме лапки начисляются бесплатно.\n"
            "Реальные деньги не списываются.\n\n"
            "✅ Используй для тестирования и отладки.\n"
            "❌ Платежи не проходят, звёзды не тратятся."
        )
    else:
        text = (
            "💎 <b>РЕАЛЬНЫЕ ПЛАТЕЖИ</b>\n\n"
            "В этом режиме лапки покупаются за Telegram Stars.\n\n"
            "⭐ 1 Star ≈ $0.014-0.020 (в зависимости от платформы)\n"
            "💰 Telegram удерживает ~30% комиссии\n\n"
            "✅ После оплаты лапки начисляются автоматически.\n"
            "❌ Возврат средств невозможен."
        )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="shop_premium")]
        ]
    )

    await send_or_edit(callback, text, reply_markup=keyboard)


# ==================== КОМАНДЫ ====================

@router.message(Command("shop_premium"))
async def cmd_shop_premium(message: Message, session: AsyncSession) -> None:
    """Команда /shop_premium — магазин лапок"""
    await show_shop_premium(message, session)


@router.callback_query(F.data == "shop_premium")
async def shop_premium_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Callback для кнопки 'Лапки' в магазине"""
    await show_shop_premium(callback, session)