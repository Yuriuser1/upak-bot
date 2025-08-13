import logging
import os
from datetime import datetime
import requests
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import json
import redis
import uuid

# Настройка логов
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
YANDEX_GPT_API_KEY = os.getenv("YANDEX_GPT_API_KEY")
BITRIX24_WEBHOOK = os.getenv("BITRIX24_WEBHOOK")
YANDEX_CHECKOUT_KEY = os.getenv("YANDEX_CHECKOUT_KEY")
YANDEX_CHECKOUT_SHOP_ID = os.getenv("YANDEX_CHECKOUT_SHOP_ID")
YANDEX_METRIKA_ID = os.getenv("YANDEX_METRIKA_ID")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Проверка критически важных переменных
if not all([TELEGRAM_TOKEN, YANDEX_GPT_API_KEY]):
    raise ValueError("Не установлены критически важные переменные окружения: TELEGRAM_TOKEN, YANDEX_GPT_API_KEY")

# Подключение к Redis (с fallback, если REDIS_URL не настроен)
try:
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    redis_client.ping()
except redis.RedisError as e:
    logger.warning(f"Не удалось подключиться к Redis: {e}. Используется локальная память.")
    redis_client = None

# Модель данных для карточки товара
class ProductCard(BaseModel):
    title: str = Field(max_length=100)
    description: str = Field(max_length=1000)
    features: list[str]
    image_url: str

# Генерация карточки товара через Yandex GPT
async def generate_card_data(product_text: str, user_id: str) -> ProductCard:
    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bearer {YANDEX_GPT_API_KEY}"}
        payload = {
            "model": "yandexgpt",
            "messages": [
                {"role": "system", "content": "Ты эксперт по созданию карточек товаров для Wildberries и Ozon. Сгенерируй заголовок (до 100 символов), описание (до 1000 символов), список преимуществ (3-5 пунктов) и URL изображения (используй Canva API)."},
                {"role": "user", "content": f"Создай карточку для: {product_text}"}
            ]
        }
        try:
            async with session.post("https://api.yandex.cloud/gpt/v1/completions", json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    card_data = json.loads(data["choices"][0]["message"]["content"])
                    return ProductCard(**card_data)
                else:
                    logger.error(f"Ошибка Yandex GPT API: {response.status}")
                    return ProductCard(
                        title="Ошибка генерации",
                        description="Не удалось сгенерировать карточку. Попробуйте позже.",
                        features=["Попробуйте снова"],
                        image_url="https://via.placeholder.com/512x512.png?text=Error"
                    )
        except Exception as e:
            logger.error(f"Ошибка при вызове Yandex GPT: {e}")
            return ProductCard(
                title="Ошибка генерации",
                description="Не удалось сгенерировать карточку. Попробуйте позже.",
                features=["Попробуйте снова"],
                image_url="https://via.placeholder.com/512x512.png?text=Error"
            )

# Интеграция с Bitrix24 для добавления лида
async def add_lead_to_bitrix24(user_id: str, username: str, service: str):
    if not BITRIX24_WEBHOOK:
        logger.warning("Bitrix24 webhook не настроен, пропускаем добавление лида")
        return
    payload = {
        "fields": {
            "TITLE": f"Лид от Telegram: {username}",
            "SOURCE_ID": "TELEGRAM",
            "ASSIGNED_BY_ID": 1,
            "COMMENTS": f"Заинтересован в услуге: {service}",
            "UF_CRM_1634567890": user_id
        }
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{BITRIX24_WEBHOOK}/crm.lead.add.json", json=payload) as response:
                if response.status == 200:
                    logger.info(f"Лид добавлен для {username}, услуга: {service}")
                else:
                    logger.error(f"Ошибка Bitrix24: {response.status}")
    except Exception as e:
        logger.error(f"Ошибка интеграции с Bitrix24: {e}")

# Создание платежной ссылки через YooKassa (ЮKassa)
async def create_payment_link(user_id: str, service: str, tariff: str, amount: float) -> str:
    if not (YANDEX_CHECKOUT_KEY and YANDEX_CHECKOUT_SHOP_ID):
        logger.warning("YooKassa не настроена, возвращаем заглушку")
        return "https://upak.space/payment-not-configured"
    
    import base64
    payment_id = str(uuid.uuid4())
    
    # Правильная авторизация для YooKassa API - Basic Auth
    auth_string = base64.b64encode(f"{YANDEX_CHECKOUT_SHOP_ID}:{YANDEX_CHECKOUT_KEY}".encode()).decode()
    
    payload = {
        "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": "https://upak.space/payment-success"},
        "capture": True,
        "description": f"Оплата тарифа {tariff} для {service} (ID: {user_id})",
        "metadata": {"user_id": user_id, "service": service, "tariff": tariff},
        "receipt": {
            "customer": {
                "email": f"user_{user_id}@upak.space"
            },
            "items": [
                {
                    "description": f"Тариф {tariff.upper()} платформы UPAK",
                    "quantity": "1.00",
                    "amount": {
                        "value": f"{amount:.2f}",
                        "currency": "RUB"
                    },
                    "vat_code": "1",
                    "payment_mode": "full_payment",
                    "payment_subject": "service"
                }
            ]
        }
    }
    
    headers = {
        "Idempotence-Key": payment_id,
        "Authorization": f"Basic {auth_string}",
        "Content-Type": "application/json"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.yookassa.ru/v3/payments",
                json=payload,
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Платеж создан успешно: {data.get('id')}")
                    return data["confirmation"]["confirmation_url"]
                else:
                    response_text = await response.text()
                    logger.error(f"Ошибка YooKassa: {response.status}, Response: {response_text}")
                    return "https://upak.space/payment-error"
    except Exception as e:
        logger.error(f"Исключение при создании платежа: {e}")
        return "https://upak.space/payment-error"

# Отправка события в Yandex Metrika
async def track_event(user_id: str, event: str):
    if not YANDEX_METRIKA_ID:
        logger.warning("Yandex Metrika не настроена, пропускаем трекинг")
        return
    async with aiohttp.ClientSession() as session:
        try:
            await session.get(
                f"https://mc.yandex.ru/metrika/tag.js?counter={YANDEX_METRIKA_ID}&event={event}&user_id={user_id}"
            )
        except Exception as e:
            logger.error(f"Ошибка Yandex Metrika: {e}")

# Стартовое сообщение
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "Unknown"
    await track_event(user_id, "start_command")
    await add_lead_to_bitrix24(user_id, username, "Начало взаимодействия")

    keyboard = [
        [
            InlineKeyboardButton("🆓 Попробовать бесплатно", callback_data='free_demo'),
            InlineKeyboardButton("💎 Выбрать тариф", callback_data='choose_plan')
        ],
        [
            InlineKeyboardButton("ℹ️ О UPAK", callback_data='about'),
            InlineKeyboardButton("💡 Как это работает", callback_data='how_it_works')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    welcome_text = (
        "Добро пожаловать в UPAK! 🚀\n\n"
        "🎯 *Создавай, Автоматизируй, Проверяй*\n\n"
        "Платформа для создания продающих карточек на Wildberries и Ozon:\n"
        "• 🎨 Конструктор карточек с ИИ\n"
        "• 🤖 Автогенерация контента\n"
        "• 📊 A/B-тестирование\n"
        "• 📈 Аналитика эффективности\n\n"
        "Начните с бесплатного тарифа или выберите подходящий план!"
    )
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

# Обработка кнопок
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    username = query.from_user.username or "Unknown"
    await query.answer()

    # Новые тарифы согласно бизнес-плану
    tariff_plans = {
        "free": {"price": 0, "name": "Free"},
        "basic": {"price": 990, "name": "Basic"},
        "pro": {"price": 4990, "name": "Pro"},
        "enterprise": {"price": "custom", "name": "Enterprise"}
    }

    if query.data == 'free_demo':
        await add_lead_to_bitrix24(user_id, username, "free_demo_start")
        await track_event(user_id, "free_demo_activated")
        
        # Активация демо-режима
        if redis_client:
            redis_client.setex(f"demo_{user_id}", 3600, json.dumps({
                "status": "active", 
                "plan": "free",
                "timestamp": datetime.utcnow().isoformat()
            }))
        
        demo_text = (
            "🆓 *Бесплатный тариф активирован!*\n\n"
            "✅ *Что доступно:*\n"
            "• 1-2 проекта\n"
            "• Базовые шаблоны карточек\n"
            "• Ограниченное количество ИИ-генераций\n"
            "• Создание карточек с водяными знаками\n\n"
            "🚀 *Попробуйте прямо сейчас:*\n"
            "Отправьте описание вашего товара, и я создам для вас демо-карточку!"
        )
        
        keyboard = [
            [InlineKeyboardButton("💎 Улучшить до Basic", callback_data='upgrade_basic')],
            [InlineKeyboardButton("📋 Все тарифы", callback_data='choose_plan')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(demo_text, reply_markup=reply_markup, parse_mode='Markdown')

    elif query.data == 'choose_plan':
        await add_lead_to_bitrix24(user_id, username, "view_pricing")
        await track_event(user_id, "view_pricing_plans")
        
        pricing_text = (
            "💎 *Тарифные планы UPAK*\n\n"
            "🆓 *Free* — 0 ₽/мес\n"
            "• 1-2 проекта\n"
            "• Базовые шаблоны\n"
            "• Ограниченные ИИ-генерации\n"
            "• Водяные знаки на карточках\n\n"
            "⭐ *Basic* — 990 ₽/мес\n"
            "• Для ИП и фрилансеров\n"
            "• Расширенные лимиты\n"
            "• Без водяных знаков\n"
            "• Полная библиотека шаблонов\n\n"
            "🔥 *Pro* — 4,990 ₽/мес\n"
            "• Для малого бизнеса и агентств\n"
            "• Командная работа\n"
            "• API для интеграций\n"
            "• Расширенная аналитика\n\n"
            "🏢 *Enterprise* — индивидуально\n"
            "• Для крупных брендов\n"
            "• Неограниченное использование\n"
            "• Персональный менеджер\n"
            "• Кастомные интеграции\n\n"
            "Выберите подходящий тариф:"
        )
        
        keyboard = [
            [InlineKeyboardButton("🆓 Free", callback_data='select_free')],
            [InlineKeyboardButton("⭐ Basic (990₽)", callback_data='select_basic')],
            [InlineKeyboardButton("🔥 Pro (4,990₽)", callback_data='select_pro')],
            [InlineKeyboardButton("🏢 Enterprise", callback_data='select_enterprise')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(pricing_text, reply_markup=reply_markup, parse_mode='Markdown')

    elif query.data.startswith('select_'):
        plan_type = query.data.replace('select_', '')
        await add_lead_to_bitrix24(user_id, username, f"select_plan_{plan_type}")
        await track_event(user_id, f"plan_selected_{plan_type}")
        
        if plan_type == 'free':
            # Перенаправляем на активацию бесплатного тарифа
            query.data = 'free_demo'
            await button_handler(update, context)
            return
            
        elif plan_type == 'enterprise':
            contact_text = (
                "🏢 *Enterprise план*\n\n"
                "Для получения персонального предложения и обсуждения ваших потребностей:\n\n"
                "📧 Email: enterprise@upak.space\n"
                "💬 Telegram: @upak_support\n"
                "📞 Телефон: +7 (999) 123-45-67\n\n"
                "Наш менеджер свяжется с вами в течение 24 часов."
            )
            
            keyboard = [
                [InlineKeyboardButton("💬 Написать в поддержку", url="https://t.me/upak_support")],
                [InlineKeyboardButton("📋 Все тарифы", callback_data='choose_plan')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(contact_text, reply_markup=reply_markup, parse_mode='Markdown')
            
        else:
            # Basic или Pro план
            plan_info = tariff_plans[plan_type]
            amount = plan_info["price"]
            plan_name = plan_info["name"]
            
            payment_url = await create_payment_link(user_id, "upak_platform", plan_type, amount)
            
            payment_text = (
                f"💎 *Тариф {plan_name}*\n\n"
                f"Стоимость: {amount:,} ₽/месяц\n\n"
                f"После оплаты вы получите:\n"
            )
            
            if plan_type == 'basic':
                payment_text += (
                    "• Неограниченные проекты\n"
                    "• Без водяных знаков\n"
                    "• Полная библиотека шаблонов\n"
                    "• Приоритетная поддержка\n"
                )
            elif plan_type == 'pro':
                payment_text += (
                    "• Все возможности Basic\n"
                    "• Командная работа\n"
                    "• API для интеграций\n"
                    "• Расширенная аналитика\n"
                    "• A/B тестирование\n"
                )
            
            keyboard = [
                [InlineKeyboardButton("💳 Оплатить", url=payment_url)],
                [InlineKeyboardButton("📋 Все тарифы", callback_data='choose_plan')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(payment_text, reply_markup=reply_markup, parse_mode='Markdown')

    elif query.data.startswith('upgrade_'):
        # Логика апгрейда с бесплатного тарифа
        plan_type = query.data.replace('upgrade_', '')
        query.data = f'select_{plan_type}'
        await button_handler(update, context)
        return

    elif query.data == 'about':
        about_text = (
            "ℹ️ *О платформе UPAK*\n\n"
            "🎯 *Наша миссия:* Создавай, Автоматизируй, Проверяй\n\n"
            "UPAK — это комплексная платформа для создания продающих карточек товаров на Wildberries и Ozon с использованием искусственного интеллекта.\n\n"
            "🔥 *Ключевые возможности:*\n"
            "• Конструктор карточек с ИИ\n"
            "• Автогенерация контента\n"
            "• A/B-тестирование эффективности\n"
            "• Аналитика и оптимизация\n"
            "• Интеграция с маркетплейсами\n\n"
            "🌐 Сайт: https://upak.space\n"
            "✉️ Поддержка: support@upak.space\n"
            "💬 Telegram: @upak_support"
        )
        
        keyboard = [
            [InlineKeyboardButton("🚀 Начать работу", callback_data='choose_plan')],
            [InlineKeyboardButton("🆓 Попробовать бесплатно", callback_data='free_demo')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(about_text, reply_markup=reply_markup, parse_mode='Markdown')

    elif query.data == 'how_it_works':
        how_it_works_text = (
            "💡 *Как работает UPAK*\n\n"
            "1️⃣ *Создание*\n"
            "Используйте конструктор или опишите товар — ИИ создаст карточку\n\n"
            "2️⃣ *Автоматизация*\n"
            "Генерация текстов, изображений и SEO-оптимизация через нейросети\n\n"
            "3️⃣ *Проверка*\n"
            "A/B-тестирование показывает, какая карточка продает лучше\n\n"
            "4️⃣ *Результат*\n"
            "Получите карточку, которая реально увеличивает продажи\n\n"
            "🎯 *Результаты наших клиентов:*\n"
            "• +30% к конверсии в среднем\n"
            "• Экономия 70% времени на создание\n"
            "• Рост продаж до +50%"
        )
        
        keyboard = [
            [InlineKeyboardButton("🆓 Попробовать сейчас", callback_data='free_demo')],
            [InlineKeyboardButton("💎 Выбрать тариф", callback_data='choose_plan')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(how_it_works_text, reply_markup=reply_markup, parse_mode='Markdown')

    elif query.data == 'create_another':
        await track_event(user_id, "create_another_card")
        create_text = (
            "🎨 *Создание новой карточки*\n\n"
            "Отправьте описание вашего товара, и я создам для вас новую карточку!\n\n"
            "💡 *Совет:* Чем подробнее описание, тем лучше получится карточка."
        )
        
        keyboard = [
            [InlineKeyboardButton("📋 Мои тарифы", callback_data='choose_plan')],
            [InlineKeyboardButton("ℹ️ Помощь", callback_data='about')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(create_text, reply_markup=reply_markup, parse_mode='Markdown')

    elif query.data == 'view_analytics':
        await track_event(user_id, "view_analytics_request")
        analytics_text = (
            "📊 *Аналитика и статистика*\n\n"
            "🚀 *Скоро доступно!*\n"
            "В ближайших обновлениях вы сможете:\n\n"
            "• 📈 Просматривать статистику по карточкам\n"
            "• 🎯 Анализировать эффективность A/B тестов\n"
            "• 📋 Получать рекомендации по улучшению\n"
            "• 💰 Отслеживать ROI от карточек\n\n"
            "Уведомим вас о запуске!"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔄 Создать новую карточку", callback_data='create_another')],
            [InlineKeyboardButton("💎 Улучшить тариф", callback_data='choose_plan')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(analytics_text, reply_markup=reply_markup, parse_mode='Markdown')

# Обработка текстовых сообщений
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "Unknown"
    user_text = update.message.text
    await track_event(user_id, "text_input")

    # Проверяем статус пользователя (демо или активная подписка)
    demo_status = redis_client.get(f"demo_{user_id}") if redis_client else None
    
    if demo_status and json.loads(demo_status).get("status") == "active":
        user_plan = json.loads(demo_status).get("plan", "free")
        
        await update.message.reply_text(
            "🧠 Генерируем карточку товара...\n"
            f"📊 Тариф: {user_plan.capitalize()}\n"
            "⏳ Пожалуйста, подождите 10-15 секунд."
        )
        
        # Генерируем карточку
        card = await generate_card_data(user_text, user_id)
        
        # Формируем заголовок с учетом тарифа
        if user_plan == "free":
            caption = f"🆓 *ДЕМО-КАРТОЧКА* 🆓\n\n*{card.title}*\n\n{card.description}\n\n"
            caption += "\n".join([f"• {feature}" for feature in card.features])
            caption += "\n\n⚠️ *Это демо-версия с водяными знаками*"
        else:
            caption = f"*{card.title}*\n\n{card.description}\n\n"
            caption += "\n".join([f"• {feature}" for feature in card.features])
        
        await update.message.reply_photo(photo=card.image_url, caption=caption, parse_mode='Markdown')
        
        # Показываем кнопки в зависимости от тарифа
        if user_plan == "free":
            keyboard = [
                [InlineKeyboardButton("💎 Улучшить до Basic (990₽)", callback_data='upgrade_basic')],
                [InlineKeyboardButton("🔥 Улучшить до Pro (4,990₽)", callback_data='upgrade_pro')],
                [InlineKeyboardButton("📋 Все тарифы", callback_data='choose_plan')]
            ]
            follow_up_text = (
                "✨ *Понравилась карточка?*\n\n"
                "🎯 С платными тарифами вы получите:\n"
                "• Карточки без водяных знаков\n"
                "• Больше ИИ-генераций\n"
                "• Расширенные шаблоны\n"
                "• A/B-тестирование\n\n"
                "Выберите план для продолжения:"
            )
        else:
            keyboard = [
                [InlineKeyboardButton("🔄 Создать еще одну", callback_data='create_another')],
                [InlineKeyboardButton("📊 Аналитика", callback_data='view_analytics')]
            ]
            follow_up_text = "✅ Карточка готова! Что дальше?"
            
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(follow_up_text, reply_markup=reply_markup, parse_mode='Markdown')
        
    else:
        # Пользователь не активировал демо или подписку
        keyboard = [
            [InlineKeyboardButton("🆓 Активировать бесплатный тариф", callback_data='free_demo')],
            [InlineKeyboardButton("💎 Выбрать тариф", callback_data='choose_plan')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_back_text = (
            "👋 Привет! Я вижу вы хотите создать карточку товара.\n\n"
            "Для начала работы активируйте бесплатный тариф или выберите подходящий план.\n"
            "🎁 В бесплатном тарифе доступно создание демо-карточек!"
        )
        
        await update.message.reply_text(welcome_back_text, reply_markup=reply_markup, parse_mode='Markdown')

# Команда демо
async def demo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "Unknown"
    await track_event(user_id, "demo_command")
    await add_lead_to_bitrix24(user_id, username, "demo_command_used")

    keyboard = [
        [InlineKeyboardButton("🆓 Активировать бесплатный тариф", callback_data='free_demo')],
        [InlineKeyboardButton("💎 Посмотреть все тарифы", callback_data='choose_plan')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    demo_text = (
        "🎯 *Демо-режим UPAK*\n\n"
        "Попробуйте создание карточек бесплатно!\n\n"
        "В демо-режиме доступно:\n"
        "• Создание карточек с ИИ\n"
        "• Базовые шаблоны\n"
        "• Ограниченные генерации\n\n"
        "Активируйте бесплатный тариф для начала:"
    )
    
    await update.message.reply_text(demo_text, reply_markup=reply_markup, parse_mode='Markdown')

# Обработка ошибок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)

# Главная функция
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Добавление обработчиков команд
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("demo", demo))
    
    # Добавление обработчиков кнопок и сообщений
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Обработчик ошибок
    app.add_error_handler(error_handler)
    
    logger.info("Бот UPAK запущен и готов к работе!")
    app.run_polling()

if __name__ == "__main__":
    main()