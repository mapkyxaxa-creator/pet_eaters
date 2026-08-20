# 🔘 ПРОВЕРКА ВСЕХ КНОПОК И CALLBACK'ОВ
# Проект: Питомцы: Большой Жор

## 🎯 ЗАДАНИЕ ДЛЯ АГЕНТА

Проверь ВСЕ кнопки в проекте и убедись, что каждая из них ведёт к существующему обработчику.

## 📋 МЕТОДИКА ПРОВЕРКИ

1. Найди все клавиатуры в папке `keyboards/`
2. Для каждой кнопки извлеки `callback_data`
3. Найди обработчик в папке `handlers/`
4. Отметь статус: ✅ есть обработчик / ❌ нет обработчика

## 🔍 ЧТО ПРОВЕРЯТЬ

### 1. Главное меню (`keyboards/main_menu.py`)

| Кнопка | callback_data | Обработчик |
|--------|---------------|------------|
| ⚔️ Приключения | `adventures` | `handlers/adventure.py` |
| 🏠 Дом | `house` | `handlers/house.py` |
| 🏆 Соревнования | `competition` | `handlers/competition.py` |
| 📸 Лента | `feed` | `handlers/feed.py` |
| 💬 Чат питомцев | `chat` | `handlers/chat.py` |
| 📬 Почта | `mailbox` | `handlers/mailbox.py` |
| 🎒 Инвентарь | `inventory` | `handlers/inventory.py` |
| 🐾 Профиль | `profile` | `handlers/profile.py` |
| 📅 Ежедневное | `daily` | `handlers/daily.py` |
| 🔔 Уведомления | `notifications` | `handlers/notifications.py` |
| 🏆 Прогресс | `progress` | `handlers/progress.py` |
| ℹ️ Помощь | `help` | `handlers/menu.py` |

### 2. Профиль (`handlers/profile.py`)

| Кнопка | callback_data | Обработчик |
|--------|---------------|------------|
| 📤 Поделиться | `share_{pet_id}` | `handlers/profile.py` |
| 📸 Альбом | `my_photos` | `handlers/photos.py` |
| 👥 Подписчики | `profile_subscribers_{pet_id}` | `handlers/profile.py` |
| 📖 Сюжет | `story_profile` | `handlers/story.py` |
| 🔙 Назад | `main_menu` | `handlers/menu.py` |

### 3. Лента (`handlers/feed.py`)

| Кнопка | callback_data | Обработчик |
|--------|---------------|------------|
| ◀️ Назад | `feed_prev_{index}` | `handlers/feed.py` |
| Вперёд ▶️ | `feed_next_{index}` | `handlers/feed.py` |
| ❤️ Лайк | `feed_like_{post_id}` | `handlers/feed.py` |
| 💬 Коммент | `feed_comment_{post_id}` | `handlers/feed.py` |
| 👁️ Все комменты | `feed_view_comments_{post_id}` | `handlers/feed.py` |
| 💔 Убрать лайк | `feed_unlike_{post_id}` | `handlers/feed.py` |
| 🎁 Подарок | `feed_gift_{pet_id}` | `handlers/feed.py` |
| 📸 Новый пост | `feed_new_post` | `handlers/feed.py` |
| ❤️ Лайк (рандом) | `feed_rand_like_{pet_id}` | `handlers/feed.py` |
| ➕ Следить | `feed_subscribe_{pet_id}` | `handlers/feed.py` |
| ➖ Отписаться | `feed_unsubscribe_{pet_id}` | `handlers/feed.py` |
| 🎁 Подарок (рандом) | `feed_rand_gift_{pet_id}` | `handlers/feed.py` |

### 4. Дом (`handlers/house.py`)

| Кнопка | callback_data | Обработчик |
|--------|---------------|------------|
| 📊 Информация | `house_info` | `handlers/house.py` |
| ⬆️ Улучшить | `house_upgrade` | `handlers/house.py` |
| 🛋️ Мебель | `house_furniture` | `handlers/house.py` |
| 🏠 Комнаты | `house_rooms` | `handlers/house.py` |
| 🏠 Шаблоны | `house_templates` | `handlers/house.py` |
| 👥 Посетить дом | `house_visit` | `handlers/house.py` |
| 🎁 Забрать бонус | `house_bonus` | `handlers/house_bonus.py` |
| 🔙 Назад | `house_main` | `handlers/house.py` |
| 🏠 Комната | `house_room_{room_type}` | `handlers/house.py` |
| 🪑 Мебель в комнате | `house_room_furniture_{room_type}` | `handlers/house.py` |
| 🛒 Купить мебель | `house_buy_furniture_{room_type}` | `handlers/house.py` |
| 🗑️ Убрать мебель | `house_remove_furniture_{room_type}_{id}` | `handlers/house.py` |
| 🏠 Шаблон | `house_template_{template_id}` | `handlers/house.py` |
| 🏠 Посетить дом | `house_visit_pet_{pet_id}` | `handlers/house.py` |
| 🔄 Обновить | `house_visit_refresh` | `handlers/house.py` |
| ⬆️ Улучшить до | `house_upgrade_confirm` | `handlers/house.py` |

### 5. Еда / Инвентарь (`handlers/food.py`, `handlers/inventory.py`, `handlers/shop.py`)

| Кнопка | callback_data | Обработчик |
|--------|---------------|------------|
| 🍽️ Съесть | `eat_confirm_{food_id}` | `handlers/food.py` |
| 🔙 Назад (еда) | `eat_back` | `handlers/food.py` |
| 🛒 Купить (магазин) | `shop_buy_{food_id}` | `handlers/shop.py` |
| Количество (магазин) | `shop_quantity_{qty}_{food_id}` | `handlers/shop.py` |
| 📦 Детали предмета | `inv_item_{item_id}` | `handlers/inventory.py` |
| 🍽️ Съесть (инвентарь) | `inv_eat_{item_id}` | `handlers/inventory.py` |
| 💰 Продать | `sell_{item_id}` | `handlers/inventory.py` |
| 🔙 Назад (инвентарь) | `inv_back` | `handlers/inventory.py` |
| 🏪 Магазин (главная) | `shop` | `handlers/shop.py` |
| 🔙 В меню магазина | `shop_main` | `handlers/shop.py` |
| 🍕 Еда | `shop_tab_food` | `handlers/shop.py` |
| 🔒 Лапки | `shop_tab_premium_currency` | `handlers/shop.py` |
| 🔒 Косметика | `shop_tab_cosmetics` | `handlers/shop.py` |
| 🔒 Premium | `shop_tab_premium` | `handlers/shop.py` |
| 🐾 Купить пакет | `shop_buy_package_{package_id}` | `handlers/payment.py` |
| ℹ️ Режим магазина | `shop_mode_info` | `handlers/payment.py` |
| 🐾 Продолжить покупки | `shop_premium` | `handlers/payment.py` |

### 6. Приключения (`handlers/adventure.py`)

| Кнопка | callback_data | Обработчик |
|--------|---------------|------------|
| Локация | `adv_location_{location_id}` | `handlers/adventure.py` |
| 🔒 Заблокировано | `adv_locked` | `handlers/adventure.py` |
| ✅ Отправить | `adv_confirm_{location_id}` | `handlers/adventure.py` |
| 🔙 Назад (приключения) | `adv_back` | `handlers/adventure.py` |
| 🔄 Обновить статус | `adv_status_{adventure_id}` | `handlers/adventure.py` |
| ⚔️ Новое приключение | `adventure_new` | `handlers/adventure.py` |

### 7. Социальное (`handlers/social.py`)

| Кнопка | callback_data | Обработчик |
|--------|---------------|------------|
| ❤️ Лайк | `like_{pet_id}` | `handlers/social.py` |
| 💔 Убрать лайк | `unlike_{pet_id}` | `handlers/social.py` |
| ➕ Подписаться | `subscribe_{pet_id}` | `handlers/social.py` |
| ➖ Отписаться | `unsubscribe_{pet_id}` | `handlers/social.py` |
| 🎁 Подарок | `gift_{pet_id}` | `handlers/social.py` |
| Выбор предмета | `gift_item_{item_id}` | `handlers/social.py` |
| Количество | `gift_qty_{qty}` | `handlers/social.py` |
| Без сообщения | `gift_msg_none` | `handlers/social.py` |
| 🔙 Назад (подарок) | `gift_back` | `handlers/social.py` |
| 🔙 Назад (количество) | `gift_back_qty` | `handlers/social.py` |
| ✅ Отправить | `gift_confirm` | `handlers/social.py` |
| ❌ Отмена | `gift_cancel` | `handlers/social.py` |

### 8. Почта (`handlers/mailbox.py`)

| Кнопка | callback_data | Обработчик |
|--------|---------------|------------|
| 📥 Получить все | `claim_all_gifts` | `handlers/mailbox.py` |
| 🔄 Обновить | `mailbox` | `handlers/mailbox.py` |
| 🗑️ Очистить | `mailbox_clear` | `handlers/mailbox.py` |
| 📥 Получить подарок | `claim_gift_{gift_id}` | `handlers/mailbox.py` |

### 9. Достижения / Прогресс (`handlers/achievements.py`, `handlers/progress.py`)

| Кнопка | callback_data | Обработчик |
|--------|---------------|------------|
| 👑 Мои титулы | `titles` | `handlers/achievements.py` |
| 🔙 Назад (достижения) | `achievements_back` | `handlers/achievements.py` |
| 🏆 Достижения | `achievements` | `handlers/achievements.py` |
| Установить титул | `set_title_{title_id}` | `handlers/achievements.py` |
| 🏆 Достижения (прогресс) | `progress_achievements` | `handlers/progress.py` |
| 📊 Рейтинг (прогресс) | `progress_rating` | `handlers/progress.py` |
| 📊 По уровню | `progress_rating_level` | `handlers/progress.py` |
| ❤️ По лайкам | `progress_rating_likes` | `handlers/progress.py` |
| 👑 Мои титулы (прогресс) | `progress_titles` | `handlers/progress.py` |
| Установить титул (прогресс) | `progress_set_title_{title_id}` | `handlers/progress.py` |

### 10. Ежедневное (`handlers/daily.py`)

| Кнопка | callback_data | Обработчик |
|--------|---------------|------------|
| 🎁 Награда | `daily_tab_reward` | `handlers/daily.py` |
| 📋 Задания | `daily_tab_quests` | `handlers/daily.py` |
| 🎁 Получить награду | `daily_claim_reward` | `handlers/daily.py` |
| 🎁 Забрать награду (задание) | `daily_claim_quest_{quest_id}` | `handlers/daily.py` |

### 11. Сюжет (`handlers/story.py`)

| Кнопка | callback_data | Обработчик |
|--------|---------------|------------|
| 📖 Подробнее о главе | `story_detail` | `handlers/story.py` |
| 📜 Диалоги главы | `story_dialogue_{chapter_id}` | `handlers/story.py` |
| Выбор в диалоге | `story_choice_{chapter_id}_{choice_id}` | `handlers/story.py` |
| 🔙 Назад (сюжет) | `story_back` | `handlers/story.py` |

### 12. Соревнования (`handlers/competition.py`)

| Кнопка | callback_data | Обработчик |
|--------|---------------|------------|
| 🎯 Участвовать | `competition_join` | `handlers/competition.py` |
| 📋 Мои результаты | `competition_my_results` | `handlers/competition.py` |
| 👥 Топ участников | `competition_top` | `handlers/competition.py` |
| 🎁 Забрать награды | `competition_claim` | `handlers/competition.py` |
| 🔄 Обновить | `competition` | `handlers/competition.py` |

### 13. Фотоальбом (`handlers/photos.py`)

| Кнопка | callback_data | Обработчик |
|--------|---------------|------------|
| ⬅️ (назад фото) | `photo_prev_{photo_id}` | `handlers/photos.py` |
| ➡️ (вперёд фото) | `photo_next_{photo_id}` | `handlers/photos.py` |
| 📸 Добавить фото | `photo_add` | `handlers/photos.py` |
| 🗑️ Удалить фото | `photo_delete_{photo_id}` | `handlers/photos.py` |
| ⭐ Сделать главным | `photo_main_{photo_id}` | `handlers/photos.py` |
| 📸 Инфо фото | `photo_info` | `handlers/photos.py` |
| ⏭️ Пропустить подпись | `photo_skip_caption` | `handlers/photos.py` |
| 📸 Опубликовать | `feed_publish_{photo_id}` | `handlers/feed.py` |
| ❌ Нет (публикация) | `feed_cancel_publish` | `handlers/feed.py` |

### 14. Уведомления (`handlers/notifications.py`)

| Кнопка | callback_data | Обработчик |
|--------|---------------|------------|
| 🔄 Обновить | `notifications` | `handlers/notifications.py` |

## 🚀 КОМАНДА ДЛЯ АГЕНТА
Прочитай PROJECT_CONTEXT_BUTTONS.md и проверь все кнопки в проекте.
Для каждой кнопки найди обработчик в папке handlers/.
Выдай список:

✅ кнопки, которые работают

❌ кнопки, у которых нет обработчика

⚠️ кнопки, у которых обработчик есть, но он может не работать

text

## 📝 ФОРМАТ ОТВЕТА

### ✅ РАБОТАЮТ
- `callback_data` → `файл.py:строка`

### ❌ НЕТ ОБРАБОТЧИКА
- `callback_data` → описание проблемы

### ⚠️ ТРЕБУЮТ ВНИМАНИЯ
- `callback_data` → описание проблемы