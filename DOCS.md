# 📖 LexarAnon — Полная Документация

> Анонимный Telegram-чат бот с Django Admin-панелью для управления.

---

## 📋 Содержание

1. [Обзор проекта](#-обзор-проекта)
2. [Технологический стек](#-технологический-стек)
3. [Структура проекта](#-структура-проекта)
4. [Установка и запуск](#-установка-и-запуск)
5. [Переменные окружения (.env)](#-переменные-окружения-env)
6. [База данных — Модели](#-база-данных--модели)
7. [Бот — Команды и кнопки](#-бот--команды-и-кнопки)
8. [Middleware](#-middleware)
9. [Django Admin](#-django-admin)
10. [Деплой на сервер](#-деплой-на-сервер)
11. [Управление сервисами](#-управление-сервисами)
12. [Архитектура системы](#-архитектура-системы)

---

## 🌌 Обзор проекта

**LexarAnon** — это Telegram-бот для анонимного общения. Пользователи подбираются случайным образом и могут переписываться полностью анонимно. Администратор управляет ботом через Django Admin.

### Основные возможности:
- 🔍 Случайный поиск собеседника
- 💬 Полностью анонимный чат (пересылка сообщений)
- 👍/👎 Рейтинг собеседников после чата
- 🔒 Обязательная подписка на каналы
- 🤖 Обязательный запуск ботов-партнёров
- 🔗 Реферальные ссылки для аналитики
- 🚨 Система жалоб
- 👤 Профиль пользователя
- 🛡️ Django Admin для полного управления

---

## 🛠 Технологический стек

| Компонент | Технология |
|---|---|
| Bot Framework | [Aiogram 3.x](https://docs.aiogram.dev/en/stable/) |
| Backend / Admin | [Django 5.x](https://www.djangoproject.com/) |
| Database (prod) | PostgreSQL |
| Database (dev) | SQLite |
| Web Server | Gunicorn + Nginx |
| Storage | S3 / MinIO (опционально) |
| Config | python-decouple |
| Async | asyncio + asgiref |

---

## 📁 Структура проекта

```
LexarAnon/
├── apps/
│   ├── users/              # Пользователи, кампании, каналы, боты
│   │   ├── models.py       # TelegramUser, RequiredChannel, RequiredBot, ReferralCampaign
│   │   ├── admin.py        # Django Admin конфигурация
│   │   └── migrations/     # Миграции БД
│   ├── chat/               # Модели чат-сессий
│   │   └── models.py       # ChatSession
│   └── reports/            # Модели жалоб
│       └── models.py       # Report
│
├── bot/
│   ├── handlers/
│   │   ├── start.py        # /start, профиль, настройки, рейтинг, боты
│   │   ├── search.py       # Поиск собеседника
│   │   ├── chat.py         # Чат (пересылка сообщений, стоп/следующий)
│   │   ├── report.py       # Жалобы
│   │   └── fallback.py     # Catch-all (восстановление меню)
│   ├── middlewares/
│   │   ├── subscription.py # Проверка подписки на каналы и запуска ботов
│   │   └── throttle.py     # Ограничение частоты сообщений
│   ├── services/
│   │   ├── matchmaking.py  # Сервис подбора пар (очередь в памяти)
│   │   ├── user_sync.py    # Синхронизация пользователя с БД
│   │   └── media.py        # Сохранение аватарок
│   ├── config.py           # Конфиг бота (из .env)
│   ├── keyboards.py        # Все клавиатуры (Reply + Inline)
│   ├── texts.py            # Все тексты сообщений
│   └── main.py             # Точка входа бота
│
├── config/
│   └── settings/
│       ├── base.py         # Базовые настройки Django
│       ├── dev.py          # Настройки разработки (SQLite)
│       └── prod.py         # Настройки продакшна (PostgreSQL)
│
├── nginx/
│   └── default.conf        # Nginx конфиг
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── manage.py
```

---

## 🚀 Установка и запуск

### Локально (разработка)

```bash
# 1. Клонировать репозиторий
git clone https://github.com/Dark-dka/LexarAnon.git
cd LexarAnon

# 2. Создать виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Скопировать .env и заполнить
cp .env.example .env
# Отредактируй .env (см. раздел ниже)

# 5. Применить миграции
python manage.py migrate

# 6. Создать суперпользователя (Admin)
python manage.py createsuperuser

# 7. Запустить Django Admin
python manage.py runserver

# 8. Запустить бот (в отдельном терминале)
python -m bot.main
```

### Django Admin
После запуска Django Admin доступен по адресу:
```
http://localhost:8000/admin/
```

---

## 🔐 Переменные окружения (.env)

```ini
# Django
DJANGO_SETTINGS_MODULE=config.settings.dev
SECRET_KEY=your-secret-key-change-in-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Telegram Bot
TELEGRAM_BOT_TOKEN=8637634590:AAE7_TKwsDifn_...  # Токен от @BotFather
BOT_USERNAME=lexaranonbot                          # Username бота без @
WEBHOOK_URL=https://yourdomain.com/webhook/

# PostgreSQL (prod)
DB_NAME=lexar_anon
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432

# Redis (для Celery, если потребуется)
REDIS_URL=redis://localhost:6379/0

# S3 / MinIO (для медиафайлов в prod, опционально)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_STORAGE_BUCKET_NAME=
AWS_S3_ENDPOINT_URL=

# Admin суперпользователь (для автосоздания)
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_PASSWORD=admin
DJANGO_SUPERUSER_EMAIL=admin@example.com
```

---

## 🗄 База данных — Модели

### `TelegramUser`
Основная модель пользователя бота.

| Поле | Тип | Описание |
|---|---|---|
| `telegram_id` | BigInt | Уникальный ID в Telegram |
| `username` | str | @username (может быть пустым) |
| `first_name` | str | Имя |
| `last_name` | str | Фамилия |
| `gender` | choice | `male` / `female` / null |
| `search_gender` | choice | Пол собеседника для поиска (null = любой) |
| `profile_photo` | image | Аватарка (сохраняется локально) |
| `language_code` | str | Язык Telegram |
| `campaign` | FK → ReferralCampaign | Кампания через которую пришёл |
| `bots_confirmed_at` | datetime | Когда подтвердил запуск ботов |
| `is_active` | bool | Активен (default: True) |
| `is_blocked` | bool | Заблокирован (default: False) |
| `created_at` | datetime | Дата регистрации |
| `updated_at` | datetime | Последнее обновление |

### `RequiredChannel`
Обязательные каналы для подписки.

| Поле | Тип | Описание |
|---|---|---|
| `title` | str | Название канала |
| `channel_username` | str | `@username` канала |
| `invite_link` | url | Ссылка для вступления |
| `subscribers_count` | int | Кол-во подписчиков (справочно) |
| `is_active` | bool | Включён ли |
| `created_at` | datetime | Дата добавления |

### `RequiredBot`
Обязательные боты которые нужно запустить.

| Поле | Тип | Описание |
|---|---|---|
| `title` | str | Название бота |
| `bot_username` | str | `@username` бота |
| `invite_link` | url | Ссылка на бота (`t.me/...`) |
| `is_active` | bool | Включён ли |
| `created_at` | datetime | Дата добавления |

### `ReferralCampaign`
Реферальные ссылки для отслеживания источника трафика.

| Поле | Тип | Описание |
|---|---|---|
| `name` | str | Название (напр. "Instagram", "VK") |
| `code` | str | Уникальный код (авто-генерируется UUID) |
| `description` | text | Заметки |
| `is_active` | bool | Активна ли |
| `created_at` | datetime | Дата создания |

> 🔗 **Ссылка:** `https://t.me/lexaranonbot?start=ref_КОД`

### `ChatSession`
Сессия чата между двумя пользователями.

| Поле | Тип | Описание |
|---|---|---|
| `user1` | FK → TelegramUser | Первый пользователь |
| `user2` | FK → TelegramUser | Второй пользователь |
| `status` | choice | `active` / `closed` |
| `started_at` | datetime | Начало чата |
| `ended_at` | datetime | Конец чата |

### `Rating`
Оценки собеседников.

| Поле | Тип | Описание |
|---|---|---|
| `from_user` | FK → TelegramUser | Кто оценил |
| `to_user` | FK → TelegramUser | Кого оценили |
| `is_like` | bool | 👍 (True) или 👎 (False) |
| `chat_session` | FK → ChatSession | За какой чат |

### `Report`
Жалобы пользователей.

| Поле | Тип | Описание |
|---|---|---|
| `reporter` | FK → TelegramUser | Кто жалуется |
| `reported` | FK → TelegramUser | На кого жалоба |
| `chat_session` | FK → ChatSession | За какой чат |
| `created_at` | datetime | Дата жалобы |

---

## 🤖 Бот — Команды и кнопки

### Команды
| Команда | Что делает |
|---|---|
| `/start` | Регистрация / приветствие. Парсит `?start=ref_КОД` для кампаний |
| `/profile` | Профиль пользователя |

### Reply-кнопки (главное меню)
| Кнопка | Действие |
|---|---|
| 🔍 Найти собеседника | Добавляет в очередь поиска |
| 👤 Профиль | Показывает пол и рейтинг (👍/👎) |
| ⚙️ Настройки поиска | Позволяет изменить пол |

### Reply-кнопки (во время чата)
| Кнопка | Действие |
|---|---|
| ⏹ Остановить | Завершить текущий чат |
| ⏭ Следующий | Завершить и начать новый поиск |
| 🚨 Пожаловаться | Отправить жалобу на собеседника |

### Reply-кнопки (в поиске)
| Кнопка | Действие |
|---|---|
| ❌ Отменить поиск | Убрать из очереди |

### Inline-кнопки
| Кнопка | callback_data | Описание |
|---|---|---|
| 👦 Я парень | `gender_male` | Выбор пола |
| 👧 Я девушка | `gender_female` | Выбор пола |
| 🔄 Изменить пол | `change_gender` | Сменить пол в настройках |
| 👍 / 👎 | `rate_like_ID` / `rate_dislike_ID` | Оценка собеседника |
| 📢 Канал | url | Открыть канал |
| ✅ Проверить подписку | `check_subscription` | Проверить все каналы |
| 🤖 Бот | url | Открыть бота |
| ☑️/✅ Запустил | `bot_done_USERNAME` | Подтверждение запуска каждого бота |
| 🎯 Готово | `check_bots` | Завершить подтверждение ботов |

---

## 🛡 Middleware

### `SubscriptionMiddleware`
Проверяет перед каждым запросом:

1. **Подписка на каналы** — делает `getChatMember` запрос в Telegram API для каждого активного `RequiredChannel`. Если не подписан — показывает кнопки каналов.

2. **Запуск обязательных ботов** — сравнивает `user.bots_confirmed_at` с `created_at` последнего добавленного `RequiredBot`. Если пользователь не подтверждал или подтверждал до добавления нового бота — блокирует.

**Всегда пропускает:**
- Callbacks: `check_subscription`, `check_bots`, `bot_done_*`
- Тексты: `❌ Отменить поиск`, `⏹ Остановить`, `⏭ Следующий`, `🚨 Пожаловаться`
- Команды: `/start`, `/help`

### `ThrottleMiddleware`
Ограничение: **30 сообщений / 60 секунд** на пользователя.

---

## 🛠 Django Admin

Доступ: `/admin/` (логин: `admin` / пароль из `.env`)

### Разделы Admin

#### 👥 Пользователи
- Список всех пользователей с фильтрами
- Фильтрация: по полу, наличию аватарки, наличию кампании, дате регистрации
- Поиск по имени, username, Telegram ID
- Просмотр и блокировка пользователей

#### 📢 Обязательные каналы
- Добавить/удалить каналы для обязательной подписки
- Ссылка автоматически отображается в Admin

#### 🤖 Обязательные боты
- Добавить/удалить ботов которых нужно запустить
- После добавления нового бота — все существующие пользователи будут снова запрошены

#### 🔗 Реферальные ссылки
Создаёт реферальные ссылки для отслеживания рекламы:
1. Добавить → указать **Название** (например: "Instagram")
2. Код генерируется автоматически
3. Полная ссылка: `https://t.me/lexaranonbot?start=ref_КОД`
4. В Admin видно сколько пользователей пришло по ссылке

#### 💬 Чат-сессии
- История всех чатов
- Статус (active/closed), время начала/конца

#### ⭐ Рейтинги
- Оценки пользователей

#### 🚨 Жалобы
- Все жалобы от пользователей

---

## 🌐 Деплой на сервер

### Сервер
- **Host:** `nettech.uz`
- **Port SSH:** `2222`
- **User:** `nettech`
- **Папка проекта:** `/home/nettech/LexarAnon`

### Команды деплоя

```bash
# Подключение
ssh nettech@nettech.uz -p 2222

# Обновление кода
cd /home/nettech/LexarAnon
git pull origin main

# Активация окружения
source venv/bin/activate

# Применение миграций
python manage.py migrate --settings=config.settings.dev

# Перезапуск сервисов
sudo systemctl restart lexar-django lexar-bot

# Проверка статуса
systemctl is-active lexar-django
systemctl is-active lexar-bot
```

### Быстрый деплой с локальной машины

```bash
# Git push + авто-деплой:
git add -A && git commit -m "описание" && git push origin main

sshpass -p 'ПАРОЛЬ' ssh -p 2222 -o StrictHostKeyChecking=no nettech@nettech.uz \
  "cd /home/nettech/LexarAnon && git pull && source venv/bin/activate && \
   python manage.py migrate --settings=config.settings.dev && \
   echo 'ПАРОЛЬ' | sudo -S systemctl restart lexar-django lexar-bot && \
   echo 'DEPLOY OK'"
```

---

## ⚙️ Управление сервисами

### systemd-сервисы
| Сервис | Описание |
|---|---|
| `lexar-django` | Django (Gunicorn) — Admin-панель |
| `lexar-bot` | Telegram Bot (Aiogram polling) |

```bash
# Статус
sudo systemctl status lexar-django
sudo systemctl status lexar-bot

# Перезапуск
sudo systemctl restart lexar-django
sudo systemctl restart lexar-bot

# Логи в реальном времени
sudo journalctl -u lexar-bot -f
sudo journalctl -u lexar-django -f

# Последние 100 строк логов
sudo journalctl -u lexar-bot -n 100 --no-pager
```

---

## 🏗 Архитектура системы

```
Пользователь Telegram
        │
        ▼
  Telegram API
        │
        ▼
  [Bot polling loop]
  bot/main.py
        │
        ▼ каждое сообщение/callback
  ThrottleMiddleware ──► (rate limit) ──► 429 stop
        │
        ▼
  SubscriptionMiddleware
  ├── Проверка каналов (getChatMember API)
  └── Проверка ботов (bots_confirmed_at vs DB)
        │
        ▼ (если прошёл)
  Router (aiogram)
  ├── start.router    — /start, профиль, настройки, рейтинг
  ├── search.router   — поиск, отмена
  ├── report.router   — жалобы
  ├── chat.router     — пересылка сообщений, стоп/след
  └── fallback.router — любой неизвестный текст → восстановить меню
        │
        ▼
  MatchmakingService (in-memory singleton)
  ├── _queue: list[telegram_id]
  └── _active_chats: dict[telegram_id → session_id]
        │
        ▼
  Django ORM (asgiref.sync_to_async)
  └── PostgreSQL / SQLite
```

### Поток регистрации пользователя

```
/start
  └── sync_user() — создать/обновить TelegramUser
        └── если новый + campaign_code → привязать к ReferralCampaign
  └── нет gender? → показать выбор пола
  └── есть gender? → показать main_menu
```

### Поток поиска собеседника

```
🔍 Найти собеседника
  └── matchmaking.add_to_queue(telegram_id)
        ├── если очередь пуста → добавить, ждать
        └── если есть кто-то → создать ChatSession
              └── оба получают PARTNER_FOUND + chat_menu

[Общение через прокси]
  └── chat.py получает текст/фото/видео
        └── пересылает партнёру через bot.copy_message()

⏹ Остановить / ⏭ Следующий
  └── matchmaking.end_session()
        └── ChatSession.status = CLOSED
        └── оба получают оценочные кнопки 👍/👎
```

---

## 📝 Заметки для разработчика

- **Порядок роутеров важен!** `fallback.router` должен регистрироваться **последним** в `main.py`, иначе он будет перехватывать все сообщения.
- **Matchmaking in-memory** — при рестарте бота очередь и активные чаты сбрасываются. Пользователи в очереди должны начать поиск заново.
- **bots_confirmed_at** — если нужно сбросить подтверждение ботов для всех пользователей, достаточно добавить нового `RequiredBot` в Admin.
- **Django ORM в async** — используй `sync_to_async()` из `asgiref` для любых DB-операций в handlers/middleware.
- **Lint ошибки (Pyre2)** — ошибки типа "Could not find import of `aiogram`" — это ложные срабатывания статического анализатора, код работает корректно.
