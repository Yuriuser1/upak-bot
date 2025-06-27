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

# Создание платежной ссылки через Yandex.Checkout
async def create_payment_link(user_id: str, service: str, tariff: str, amount: float) -> str:
    if not (YANDEX_CHECKOUT_KEY and YANDEX_CHECKOUT_SHOP_ID):
        logger.warning("Yandex.Checkout не настроен, возвращаем заглушку")
        return "https://upak.space/payment-not-configured"
    payment_id = str(uuid.uuid4())
    payload = {
        "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": "https://upak.space/payment-success"},
        "capture": True,
        "description": f"Оплата тарифа {tariff} для {service} (ID: {user_id})",
        "metadata": {"user_id": user_id, "service": service, "tariff": tariff}
    }
    headers = {
        "Idempotency-Key": payment_id,
        "Authorization": f"Bearer {YANDEX_CHECKOUT_KEY}"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"https://api.yookassa.ru/v3/payments",
            json=payload,
            headers=headers
        ) as response:
            if response.status == 200:
                data = await response.json()
                return data["confirmation"]["confirmation_url"]
            else:
                logger.error(f"Ошибка Yandex.Checkout: {response.status}")
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
            InlineKeyboardButton("📦 Упаковка карточек", callback_data='order_packaging'),
            InlineKeyboardButton("🤖 ИИ-ассистенты", callback_data='ai_assistants')
        ],
        [
            InlineKeyboardButton("📝 Контент-маркетинг", callback_data='content_automation'),
            InlineKeyboardButton("📊 Аналитика", callback_data='predictive_analytics')
        ],
        [
            InlineKeyboardButton("💬 Чат-боты", callback_data='chatbots'),
            InlineKeyboardButton("ℹ️ О UPAK", callback_data='about')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    welcome_text = (
        "Добро пожаловать в UPAK! 🚀\n"
        "Мы автоматизируем продвижение на Wildberries и Ozon с помощью ИИ.\n"
        "Выберите услугу ниже или отправьте описание товара для создания карточки."
    )
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

# Обработка кнопок
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    username = query.from_user.username or "Unknown"
    await query.answer()

    tariffs = {
        "order_packaging": {"basic": 15000, "premium": 35000},
        "ai_assistants": {"basic": 25000, "premium": 50000},
        "content_automation": {"startup": 30000, "agency": 100000},
        "predictive_analytics": {"small_store": 50000, "large_store": 150000},
        "chatbots": {"standard": 40000, "corporate": 120000}
    }

    service_descriptions = {
        "order_packaging": (
            "📦 *Упаковка карточек*\n"
            "Создаем SEO-оптимизированные карточки товаров для WB и Ozon.\n"
            "- Базовый (15,000 ₽/мес): Заголовок, описание, изображения.\n"
            "- Премиум (35,000 ₽/мес): Дополнительно A/B-тестирование и аналитика.\n"
            "Выберите тариф:"
        ),
        "ai_assistants": (
            "🤖 *ИИ-ассистенты*\n"
            "Автоматизация рутинных задач: ответы клиентам, отчеты.\n"
            "- Базовый (25,000 ₽/мес): Основные функции.\n"
            "- Премиум (50,000 ₽/мес): Глубокая интеграция с CRM.\n"
            "Выберите тариф:"
        ),
        "content_automation": (
            "📝 *Автоматизация контент-маркетинга*\n"
            "Генерация постов, статей, описаний.\n"
            "- Стартап (30,000 ₽/мес): Базовый контент.\n"
            "- Агентство (100,000 ₽/мес): Полная автоматизация и планирование.\n"
            "Выберите тариф:"
        ),
        "predictive_analytics": (
            "📊 *Предиктивная аналитика*\n"
            "Прогноз спроса, динамическое ценообразование.\n"
            "- Малый магазин (50,000 ₽/мес): Базовые прогнозы.\n"
            "- Крупный магазин (150,000 ₽/мес): Персонализация и аналитика.\n"
            "Выберите тариф:"
        ),
        "chatbots": (
            "💬 *ИИ-чатботы для продаж*\n"
            "Квалификация лидов, продажи 24/7.\n"
            "- Стандарт (40,000 ₽/мес): Базовый чатбот.\n"
            "- Корпоративный (120,000 ₽/мес): Омниканальность, CRM.\n"
            "Выберите тариф:"
        ),
        "about": (
            "ℹ️ *О UPAK*\n"
            "Мы — нейросервис для автоматизации бизнеса на WB и Ozon. Генерируем карточки, контент, аналитику и чатботы с помощью ИИ.\n"
            "Подробнее: https://upak.space\n"
            "Свяжитесь с нами: support@upak.space"
        )
    }

    if query.data in tariffs:
        await add_lead_to_bitrix24(user_id, username, query.data)
        await track_event(user_id, f"select_service_{query.data}")
        keyboard = [
            [InlineKeyboardButton("Базовый" if query.data != "content_automation" else "Стартап", callback_data=f"{query.data}_basic")],
            [InlineKeyboardButton("Премиум" if query.data not in ["content_automation", "predictive_analytics", "chatbots"] else "Агентство" if query.data == "content_automation" else "Крупный магазин" if query.data == "predictive_analytics" else "Корпоративный", callback_data=f"{query.data}_premium")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(service_descriptions[query.data], reply_markup=reply_markup, parse_mode='Markdown')
    elif query.data == 'about':
        await query.edit_message_text(service_descriptions['about'], parse_mode='Markdown')
    elif query.data.endswith('_basic') or query.data.endswith('_premium'):
        service, tariff = query.data.rsplit('_', 1)
        amount = tariffs[service][tariff]
        payment_url = await create_payment_link(user_id, service, tariff, amount)
        await add_lead_to_bitrix24(user_id, username, f"{service}_{tariff}_payment")
        await track_event(user_id, f"payment_initiated_{service}_{tariff}")
        keyboard = [[InlineKeyboardButton("Оплатить", url=payment_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"Вы выбрали тариф *{tariff.capitalize()}* для услуги *{service}*. Стоимость: {amount:,} ₽/мес.\nПерейдите для оплаты:", reply_markup=reply_markup, parse_mode='Markdown')
    elif query.data == 'demo':
        if redis_client:
            redis_client.setex(f"demo_{user_id}", 3600, json.dumps({"status": "active", "timestamp": datetime.utcnow().isoformat()}))
        else:
            logger.warning("Redis недоступен, демо-режим не сохранен")
        await query.edit_message_text("Запустите демо, отправив описание товара или выбрав услугу.")

# Обработка текстовых сообщений
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "Unknown"
    user_text = update.message.text
    await track_event(user_id, "text_input")

    demo_status = redis_client.get(f"demo_{user_id}") if redis_client else None
    if demo_status and json.loads(demo_status).get("status") == "active":
        await update.message.reply_text("🧠 Генерируем демо-карточку... Пожалуйста, подождите 10–15 секунд.")
        card = await generate_card_data(user_text, user_id)
        caption = f"*{card.title}*\n\n{card.description}\n\n" + "\n".join(card.features)
        await update.message.reply_photo(photo=card.image_url, caption=caption, parse_mode='Markdown')
        keyboard = [[InlineKeyboardButton("Оформить подписку", callback_data='order_packaging')]]
        await update.message.reply_text("Понравилась карточка? Выберите тариф для продолжения!", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text("Отправьте описание товара для демо или выберите услугу через /start.")

# Обработка ошибок
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="Ошибка:", exc_info=context.error)
    if update and hasattr(update, 'effective_user'):
        await track_event(str(update.effective_user.id), "error")
        await update.message.reply_text("Произошла ошибка. Попробуйте снова или свяжитесь с нами: support@upak.space")

# Запуск бота
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
app.add_handler(CommandHandler("demo", button_handler, filters=filters.Regex('^demo$')))
app.add_error_handler(error_handler)

if __name__ == "__main__":
    app.run_polling()
