# 🤖 UPAK Telegram Bot

**Создавай, Автоматизируй, Проверяй** — платформа для создания продающих карточек товаров на маркетплейсах Wildberries и Ozon с использованием искусственного интеллекта.

## 🚀 Возможности

- **🎨 Конструктор карточек с ИИ** — автоматическое создание привлекательных карточек товаров
- **🤖 Автогенерация контента** — использование Yandex GPT для создания текстов и описаний
- **📊 A/B-тестирование** — проверка эффективности различных вариантов карточек
- **📈 Аналитика эффективности** — отслеживание результатов через Yandex Metrika
- **💳 Система подписок** — интеграция с YooKassa для приема платежей
- **🔗 CRM интеграция** — автоматическое добавление лидов в Bitrix24

## 💎 Тарифные планы

### 🆓 Free — 0 ₽/мес
- До 5 демо-карточек
- Базовые шаблоны
- ИИ-генерация с ограничениями
- Водяные знаки на карточках

### ⭐ Basic — 990 ₽/мес
- Для ИП и фрилансеров
- Неограниченные карточки
- Без водяных знаков
- Полная библиотека шаблонов
- Приоритетная поддержка

### 🔥 Pro — 4,990 ₽/мес
- Для малого бизнеса и агентств
- Все возможности Basic
- Командная работа
- API для интеграций
- Расширенная аналитика
- A/B тестирование

### 🏢 Enterprise — индивидуально
- Для крупных брендов
- Неограниченное использование
- Персональный менеджер
- Кастомные интеграции

## 🛠️ Установка и настройка

### 1. Клонирование репозитория

```bash
git clone https://github.com/Yuriuser1/upak-bot.git
cd upak-bot
```

### 2. Создание виртуального окружения

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Настройка переменных окружения

Скопируйте `.env.example` в `.env` и заполните необходимые переменные:

```bash
cp .env.example .env
nano .env
```

#### Обязательные переменные:
- `TELEGRAM_TOKEN` — токен вашего Telegram бота (получите у [@BotFather](https://t.me/BotFather))
- `YANDEX_GPT_API_KEY` — API ключ для Yandex GPT
- `YANDEX_GPT_FOLDER_ID` — ID папки в Yandex Cloud

#### Опциональные переменные:
- `BITRIX24_WEBHOOK` — webhook URL для интеграции с Bitrix24
- `YANDEX_CHECKOUT_KEY` — секретный ключ YooKassa
- `YANDEX_CHECKOUT_SHOP_ID` — ID магазина в YooKassa
- `YANDEX_METRIKA_ID` — ID счетчика Yandex Metrika
- `REDIS_URL` — URL подключения к Redis (по умолчанию: redis://localhost:6379)

### 5. Запуск бота

#### Локальное тестирование:
```bash
python bot.py
```

#### Продакшн режим:
```bash
python bot_production.py
```

## 🐳 Docker развертывание

### Быстрый запуск с Docker Compose:

```bash
docker-compose up -d
```

### Ручная сборка Docker образа:

```bash
docker build -t upak-bot .
docker run -d --env-file .env --name upak-bot upak-bot
```

## 📊 Системные требования

- Python 3.11+
- Redis (для кэширования сессий)
- Минимум 512 МБ RAM
- Подключение к интернету

## 🔧 Управление ботом

Используйте скрипт управления:

```bash
# Запуск
./bot_manager.sh start

# Остановка
./bot_manager.sh stop

# Перезапуск
./bot_manager.sh restart

# Просмотр статуса
./bot_manager.sh status

# Просмотр логов
./bot_manager.sh logs

# Тестирование подключения
./bot_manager.sh test
```

## 🧪 Тестирование

### Запуск тестов логики бота:
```bash
python test_bot_logic.py
```

### Тестирование платежной системы:
```bash
python test_payment.py
```

### Тестирование функций бота:
```bash
python test_bot_functions.py
```

## 📁 Структура проекта

```
upak-bot/
├── bot.py                 # Основной файл бота
├── bot_production.py      # Продакшн версия бота
├── bot_webhook.py         # Webhook обработчик
├── requirements.txt       # Зависимости Python
├── .env.example          # Пример файла окружения
├── Dockerfile            # Docker конфигурация
├── docker-compose.yml    # Docker Compose конфигурация
├── bot_manager.sh        # Скрипт управления ботом
├── deploy.sh            # Скрипт развертывания
├── health_check.sh      # Проверка работоспособности
├── upak-bot.service     # Systemd service файл
├── test_*.py           # Тестовые скрипты
├── logs/               # Директория логов
└── README.md           # Документация
```

## 🔄 Интеграции

### Yandex GPT
Используется для генерации названий товаров, описаний и ключевых особенностей.

### YooKassa (ЮKassa)
Платежная система для приема подписок и разовых платежей.

### Bitrix24
Автоматическое создание лидов в CRM системе.

### Yandex Metrika
Отслеживание действий пользователей и аналитика.

### Redis
Кэширование пользовательских сессий и временных данных.

## 🚀 Деплой в продакшн

### 1. Настройка сервера
```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Docker
sudo apt install docker.io docker-compose -y

# Установка Redis
sudo apt install redis-server -y
```

### 2. Клонирование и настройка
```bash
git clone https://github.com/Yuriuser1/upak-bot.git
cd upak-bot
cp .env.example .env
# Заполните .env файл реальными токенами
```

### 3. Запуск через Docker Compose
```bash
docker-compose up -d
```

### 4. Настройка systemd service (опционально)
```bash
sudo cp upak-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable upak-bot
sudo systemctl start upak-bot
```

## 📝 Логирование

- **Локальные логи**: `bot.log`, `bot_production.log`
- **Директория логов**: `logs/`
- **Systemd логи**: `journalctl -u upak-bot -f`

## 🔒 Безопасность

- Все секретные ключи хранятся в переменных окружения
- Файл `.env` исключен из Git репозитория
- Используется `.env.example` для документирования необходимых переменных
- Docker контейнер работает от непривилегированного пользователя

## 🤝 Поддержка

- **Telegram**: [@upak_support](https://t.me/upak_support)
- **Email**: support@upak.space
- **Сайт**: https://upak.space

## 📈 Статистика проекта

- **Версия**: 2.0
- **Язык**: Python 3.11
- **Архитектура**: Микросервисная
- **Развертывание**: Docker + systemd
- **База данных**: Redis

## 🔮 Планы развития

- [ ] Веб-интерфейс для управления карточками
- [ ] Мобильное приложение
- [ ] Интеграция с дополнительными маркетплейсами
- [ ] Расширенная аналитика и отчетность
- [ ] API для сторонних разработчиков
- [ ] Система партнерских программ

---

💡 **UPAK** — создавай продающие карточки быстро и эффективно!

*Создавай, Автоматизируй, Проверяй* 🚀