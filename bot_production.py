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

# Настройка логов для продакшн
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot_production.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
YANDEX_GPT_API_KEY = os.getenv("YANDEX_GPT_API_KEY")
YANDEX_GPT_FOLDER_ID = os.getenv("YANDEX_GPT_FOLDER_ID")
BITRIX24_WEBHOOK = os.getenv("BITRIX24_WEBHOOK")
YANDEX_CHECKOUT_KEY = os.getenv("YANDEX_CHECKOUT_KEY")
YANDEX_CHECKOUT_SHOP_ID = os.getenv("YANDEX_CHECKOUT_SHOP_ID")
YANDEX_METRIKA_ID = os.getenv("YANDEX_METRIKA_ID")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", 8443))

# Проверка критически важных переменных
if not all([TELEGRAM_TOKEN, YANDEX_GPT_API_KEY]):
    logger.error("Критически важные переменные окружения не установлены!")
    raise ValueError("Не установлены критически важные переменные окружения: TELEGRAM_TOKEN, YANDEX_GPT_API_KEY")

# Подключение к Redis (обязательно для продакшн)
try:
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    redis_client.ping()
    logger.info("Успешное подключение к Redis")
except redis.RedisError as e:
    logger.error(f"Критическая ошибка: не удалось подключиться к Redis: {e}")
    # В продакшн режиме Redis обязателен
    raise

# Модель данных для карточки товара
class ProductCard(BaseModel):
    title: str = Field(max_length=100)
    description: str = Field(max_length=1000)
    features: list[str]
    image_url: str

# Расширенная генерация карточки товара через Yandex GPT
async def generate_card_data(product_text: str, user_id: str) -> ProductCard:
    """Продакшн версия генерации карточки с расширенными возможностями"""
    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": f"Bearer {YANDEX_GPT_API_KEY}",
            "x-folder-id": YANDEX_GPT_FOLDER_ID
        }
        
        # Улучшенный промпт для продакшн
        system_prompt = (
            "Ты эксперт по созданию продающих карточек товаров для маркетплейсов Wildberries и Ozon. "
            "Создай привлекательную карточку товара, учитывая SEO-оптимизацию и психологию покупателя. "
            "Ответ должен быть в формате JSON с полями: title, description, features, image_url. "
            "title - до 100 символов, цепляющий заголовок. "
            "description - до 1000 символов, подробное описание с эмоциональными триггерами. "
            "features - массив из 3-5 ключевых преимуществ. "
            "image_url - используй подходящее изображение из Unsplash API."
        )
        
        payload = {
            "modelUri": f"gpt://{YANDEX_GPT_FOLDER_ID}/yandexgpt/latest",
            "completionOptions": {
                "stream": False,
                "temperature": 0.7,
                "maxTokens": "2000"
            },
            "messages": [
                {"role": "system", "text": system_prompt},
                {"role": "user", "text": f"Создай продающую карточку для товара: {product_text}"}
            ]
        }
        
        try:
            async with session.post(
                "https://llm.api.cloud.yandex.net/foundationModels/v1/completion", 
                json=payload, 
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    result_text = data["result"]["alternatives"][0]["message"]["text"]
                    
                    try:
                        card_data = json.loads(result_text)
                        
                        # Валидация и fallback для изображения
                        if not card_data.get("image_url") or "placeholder" in card_data.get("image_url", ""):
                            card_data["image_url"] = f"https://source.unsplash.com/800x600/?{product_text.split()[0]},product"
                        
                        return ProductCard(**card_data)
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.error(f"Ошибка парсинга ответа GPT: {e}")
                        return _get_fallback_card(product_text)
                else:
                    logger.error(f"Ошибка Yandex GPT API: {response.status}")
                    error_text = await response.text()
                    logger.error(f"Детали ошибки: {error_text}")
                    return _get_fallback_card(product_text)
        except Exception as e:
            logger.error(f"Исключение при вызове Yandex GPT: {e}")
            return _get_fallback_card(product_text)

def _get_fallback_card(product_text: str) -> ProductCard:
    """Fallback карточка при ошибке API"""
    return ProductCard(
        title=f"Качественный {product_text[:50]}...",
        description=f"Отличный продукт '{product_text}' с высоким качеством и доступной ценой. Быстрая доставка, гарантия качества, положительные отзывы покупателей.",
        features=["Высокое качество", "Быстрая доставка", "Гарантия", "Положительные отзывы"],
        image_url="https://source.unsplash.com/800x600/?product,quality"
    )

# Интеграция с Bitrix24 для добавления лида
async def add_lead_to_bitrix24(user_id: str, username: str, service: str):
    """Продакшн версия интеграции с Bitrix24"""
    if not BITRIX24_WEBHOOK:
        logger.warning("Bitrix24 webhook не настроен, пропускаем добавление лида")
        return False
    
    payload = {
        "fields": {
            "TITLE": f"Лид от UPAK Telegram: {username or 'Unknown'}",
            "SOURCE_ID": "TELEGRAM",
            "ASSIGNED_BY_ID": 1,
            "STATUS_ID": "NEW",
            "COMMENTS": f"Пользователь ID: {user_id}\nИнтерес: {service}\nДата: {datetime.now().isoformat()}",
            "PHONE": [{"VALUE": f"+7-telegram-{user_id}", "VALUE_TYPE": "WORK"}],
            "UF_CRM_TELEGRAM_ID": user_id,
            "UF_CRM_SERVICE_TYPE": service
        }
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{BITRIX24_WEBHOOK}/crm.lead.add.json", json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"Лид добавлен успешно: ID {result.get('result')}, пользователь: {username}, услуга: {service}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Ошибка Bitrix24 API: {response.status}, {error_text}")
                    return False
    except Exception as e:
        logger.error(f"Исключение при работе с Bitrix24: {e}")
        return False

# Создание платежной ссылки через YooKassa (ЮKassa) - ИСПРАВЛЕННАЯ ВЕРСИЯ
async def create_payment_link(user_id: str, service: str, tariff: str, amount: float) -> str:
    """Создание реального платежа через YooKassa API"""
    if not (YANDEX_CHECKOUT_KEY and YANDEX_CHECKOUT_SHOP_ID):
        logger.warning("YooKassa не настроена полностью")
        logger.info(f"YANDEX_CHECKOUT_KEY установлен: {'Да' if YANDEX_CHECKOUT_KEY else 'Нет'}")
        logger.info(f"YANDEX_CHECKOUT_SHOP_ID установлен: {'Да' if YANDEX_CHECKOUT_SHOP_ID else 'Нет'}")
        return "https://upak.space/payment-not-configured"
    
    import base64
    payment_id = str(uuid.uuid4())
    
    # ИСПРАВЛЕНО: правильная авторизация для YooKassa API
    auth_string = base64.b64encode(f"{YANDEX_CHECKOUT_SHOP_ID}:{YANDEX_CHECKOUT_KEY}".encode()).decode()
    
    payload = {
        "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
        "confirmation": {
            "type": "redirect", 
            "return_url": "https://upak.space/payment-success"
        },
        "capture": True,
        "description": f"Оплата тарифа {tariff.upper()} платформы UPAK (ID: {user_id})",
        "metadata": {
            "user_id": user_id, 
            "service": service, 
            "tariff": tariff,
            "timestamp": datetime.utcnow().isoformat()
        },
        "receipt": {
            "customer": {
                "email": f"user_{user_id}@upak.space"
            },
            "items": [
                {
                    "description": f"Подписка UPAK {tariff.upper()}",
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
    
    logger.info(f"Создание платежа: пользователь {user_id}, тариф {tariff}, сумма {amount}₽")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.yookassa.ru/v3/payments",
                json=payload,
                headers=headers
            ) as response:
                
                response_text = await response.text()
                
                if response.status == 200:
                    data = json.loads(response_text)
                    payment_url = data["confirmation"]["confirmation_url"]
                    
                    logger.info(f"Платеж создан успешно: {data.get('id')}")
                    logger.info(f"Ссылка для оплаты: {payment_url}")
                    
                    # Сохраняем информацию о платеже в Redis
                    if redis_client:
                        redis_client.setex(
                            f"payment_{payment_id}",
                            3600 * 24,  # 24 часа
                            json.dumps({
                                "user_id": user_id,
                                "tariff": tariff,
                                "amount": amount,
                                "status": "pending",
                                "created": datetime.utcnow().isoformat(),
                                "yookassa_id": data.get('id')
                            })
                        )
                    
                    return payment_url
                    
                else:
                    logger.error(f"Ошибка YooKassa API: {response.status}")
                    logger.error(f"Ответ сервера: {response_text}")
                    return f"https://upak.space/payment-error?code={response.status}"
                    
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON ответа YooKassa: {e}")
        return "https://upak.space/payment-error?code=json_error"
    except Exception as e:
        logger.error(f"Исключение при создании платежа: {e}")
        return "https://upak.space/payment-error?code=exception"

# Улучшенное отслеживание событий в Yandex Metrika
async def track_event(user_id: str, event: str, additional_params: dict = None):
    """Продакшн версия трекинга событий"""
    if not YANDEX_METRIKA_ID:
        logger.debug("Yandex Metrika не настроена, пропускаем трекинг")
        return
    
    params = {
        "counter": YANDEX_METRIKA_ID,
        "event": event,
        "user_id": user_id,
        "timestamp": int(datetime.utcnow().timestamp())
    }
    
    if additional_params:
        params.update(additional_params)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://mc.yandex.ru/metrika/tag.js",
                params=params,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    logger.debug(f"Событие отправлено в Metrika: {event}")
                else:
                    logger.warning(f"Ошибка Metrika: {response.status}")
    except Exception as e:
        logger.error(f"Ошибка отправки в Yandex Metrika: {e}")

# Стартовое сообщение (аналогично основной версии)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "Unknown"
    first_name = update.effective_user.first_name or "Пользователь"
    
    logger.info(f"Новый пользователь: {user_id} (@{username}) - {first_name}")
    
    await track_event(user_id, "start_command", {"username": username, "first_name": first_name})
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
        f"Добро пожаловать в UPAK, {first_name}! 🚀\n\n"
        "🎯 *Создавай, Автоматизируй, Проверяй*\n\n"
        "Платформа для создания продающих карточек на Wildberries и Ozon:\n"
        "• 🎨 Конструктор карточек с ИИ\n"
        "• 🤖 Автогенерация контента\n"
        "• 📊 A/B-тестирование\n"
        "• 📈 Аналитика эффективности\n\n"
        "Начните с бесплатного тарифа или выберите подходящий план!"
    )
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

# Основная логика обработки кнопок (аналогично базовой версии, но с улучшенным логированием)
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    username = query.from_user.username or "Unknown"
    await query.answer()
    
    logger.info(f"Пользователь {user_id} (@{username}) нажал кнопку: {query.data}")

    # Новые тарифы согласно бизнес-плану
    tariff_plans = {
        "free": {"price": 0, "name": "Free"},
        "basic": {"price": 990, "name": "Basic"},
        "pro": {"price": 4990, "name": "Pro"},
        "enterprise": {"price": "custom", "name": "Enterprise"}
    }

    if query.data == 'free_demo':
        await add_lead_to_bitrix24(user_id, username, "free_demo_activation")
        await track_event(user_id, "free_demo_activated")
        
        # Активация демо-режима в Redis
        demo_data = {
            "status": "active", 
            "plan": "free",
            "timestamp": datetime.utcnow().isoformat(),
            "activations_left": 5  # Лимит на демо-карточки
        }
        redis_client.setex(f"demo_{user_id}", 3600 * 24, json.dumps(demo_data))
        logger.info(f"Активирован демо-режим для пользователя {user_id}")
        
        demo_text = (
            "🆓 *Бесплатный тариф активирован!*\n\n"
            "✅ *Что доступно:*\n"
            "• До 5 демо-карточек\n"
            "• Базовые шаблоны карточек\n"
            "• ИИ-генерация с ограничениями\n"
            "• Создание карточек с водяными знаками\n\n"
            "🚀 *Попробуйте прямо сейчас:*\n"
            "Отправьте описание вашего товара, и я создам для вас демо-карточку!"
        )
        
        keyboard = [
            [InlineKeyboardButton("💎 Улучшить до Basic (990₽)", callback_data='upgrade_basic')],
            [InlineKeyboardButton("🔥 Улучшить до Pro (4,990₽)", callback_data='upgrade_pro')],
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
            "• До 5 демо-карточек\n"
            "• Базовые шаблоны\n"
            "• Ограниченные ИИ-генерации\n"
            "• Водяные знаки на карточках\n\n"
            "⭐ *Basic* — 990 ₽/мес\n"
            "• Для ИП и фрилансеров\n"
            "• Неограниченные карточки\n"
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
                "Для получения персонального предложения:\n\n"
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
            
            logger.info(f"Пользователь {user_id} выбрал тариф {plan_name} за {amount}₽")
            
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
        logger.info(f"Пользователь {user_id} хочет апгрейд до {plan_type}")
        query.data = f'select_{plan_type}'
        await button_handler(update, context)
        return

    # ... остальные обработчики аналогично базовой версии
    # (about, how_it_works, create_another, view_analytics)
    
    else:
        logger.warning(f"Неизвестная команда кнопки: {query.data}")
        await query.edit_message_text("❌ Неизвестная команда. Попробуйте начать заново с /start")

# Обработка текстовых сообщений (улучшенная версия)
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "Unknown"
    user_text = update.message.text
    
    logger.info(f"Пользователь {user_id} отправил текст: {user_text[:50]}...")
    await track_event(user_id, "text_input", {"text_length": len(user_text)})

    # Проверяем статус пользователя (демо или активная подписка)
    demo_status = redis_client.get(f"demo_{user_id}")
    
    if demo_status:
        demo_data = json.loads(demo_status)
        
        if demo_data.get("status") == "active":
            user_plan = demo_data.get("plan", "free")
            activations_left = demo_data.get("activations_left", 0)
            
            if user_plan == "free" and activations_left <= 0:
                # Превышен лимит демо-карточек
                limit_text = (
                    "🚫 *Лимит демо-карточек исчерпан*\n\n"
                    "Вы создали максимальное количество бесплатных карточек.\n"
                    "Чтобы продолжить, выберите подходящий тариф:\n"
                )
                
                keyboard = [
                    [InlineKeyboardButton("⭐ Basic (990₽)", callback_data='select_basic')],
                    [InlineKeyboardButton("🔥 Pro (4,990₽)", callback_data='select_pro')],
                    [InlineKeyboardButton("📋 Все тарифы", callback_data='choose_plan')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(limit_text, reply_markup=reply_markup, parse_mode='Markdown')
                return
            
            # Генерация карточки
            await update.message.reply_text(
                "🧠 Генерируем карточку товара...\n"
                f"📊 Тариф: {user_plan.capitalize()}\n"
                f"🎫 Осталось демо-карточек: {activations_left if user_plan == 'free' else '∞'}\n"
                "⏳ Пожалуйста, подождите 15-20 секунд."
            )
            
            # Генерируем карточку
            card = await generate_card_data(user_text, user_id)
            
            # Формируем заголовок с учетом тарифа
            if user_plan == "free":
                caption = f"🆓 *ДЕМО-КАРТОЧКА* 🆓\n\n*{card.title}*\n\n{card.description}\n\n"
                caption += "\n".join([f"• {feature}" for feature in card.features])
                caption += "\n\n⚠️ *Это демо-версия с водяными знаками*"
                
                # Уменьшаем счетчик активаций
                demo_data["activations_left"] = max(0, activations_left - 1)
                redis_client.setex(f"demo_{user_id}", 3600 * 24, json.dumps(demo_data))
                
            else:
                caption = f"✨ *ПРЕМИУМ КАРТОЧКА* ✨\n\n*{card.title}*\n\n{card.description}\n\n"
                caption += "\n".join([f"• {feature}" for feature in card.features])
                caption += "\n\n🎯 *Готово к публикации на маркетплейсе*"
            
            try:
                await update.message.reply_photo(photo=card.image_url, caption=caption, parse_mode='Markdown')
                logger.info(f"Карточка создана для пользователя {user_id}, тариф: {user_plan}")
            except Exception as e:
                logger.error(f"Ошибка отправки карточки: {e}")
                await update.message.reply_text(f"Карточка готова!\n\n{caption}", parse_mode='Markdown')
            
            # Показываем кнопки в зависимости от тарифа
            if user_plan == "free":
                remaining = demo_data.get("activations_left", 0)
                keyboard = [
                    [InlineKeyboardButton(f"💎 Улучшить до Basic (990₽)", callback_data='upgrade_basic')],
                    [InlineKeyboardButton(f"🔥 Улучшить до Pro (4,990₽)", callback_data='upgrade_pro')],
                ]
                if remaining > 0:
                    keyboard.append([InlineKeyboardButton(f"🔄 Создать еще ({remaining} осталось)", callback_data='create_another')])
                keyboard.append([InlineKeyboardButton("📋 Все тарифы", callback_data='choose_plan')])
                
                follow_up_text = (
                    "✨ *Понравилась карточка?*\n\n"
                    "🎯 С платными тарифами вы получите:\n"
                    "• Карточки без водяных знаков\n"
                    "• Неограниченные генерации\n"
                    "• Расширенные шаблоны\n"
                    "• A/B-тестирование\n\n"
                    f"Демо-карточек осталось: {remaining}"
                )
            else:
                keyboard = [
                    [InlineKeyboardButton("🔄 Создать еще одну", callback_data='create_another')],
                    [InlineKeyboardButton("📊 Аналитика", callback_data='view_analytics')]
                ]
                follow_up_text = "✅ Премиум карточка готова! Что дальше?"
                
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(follow_up_text, reply_markup=reply_markup, parse_mode='Markdown')
            
        else:
            await _prompt_activation(update)
    else:
        await _prompt_activation(update)

async def _prompt_activation(update: Update):
    """Предложение активировать тариф"""
    keyboard = [
        [InlineKeyboardButton("🆓 Активировать бесплатный тариф", callback_data='free_demo')],
        [InlineKeyboardButton("💎 Выбрать тариф", callback_data='choose_plan')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_back_text = (
        "👋 Привет! Я вижу вы хотите создать карточку товара.\n\n"
        "Для начала работы активируйте бесплатный тариф или выберите подходящий план.\n"
        "🎁 В бесплатном тарифе доступно создание 5 демо-карточек!"
    )
    
    await update.message.reply_text(welcome_back_text, reply_markup=reply_markup, parse_mode='Markdown')

# Команда демо
async def demo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "Unknown"
    
    logger.info(f"Команда /demo от пользователя {user_id}")
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
        "• До 5 демо-карточек\n"
        "• Создание карточек с ИИ\n"
        "• Базовые шаблоны\n"
        "• Водяные знаки на карточках\n\n"
        "Активируйте бесплатный тариф для начала:"
    )
    
    await update.message.reply_text(demo_text, reply_markup=reply_markup, parse_mode='Markdown')

# Улучшенный обработчик ошибок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Продакшн обработчик ошибок с детальным логированием"""
    logger.error(f"Исключение при обработке обновления {update}: {context.error}", exc_info=context.error)
    
    # Отправляем пользователю дружественное сообщение об ошибке
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "😓 Произошла техническая ошибка. Попробуйте позже или напишите в поддержку @upak_support"
            )
        except Exception:
            pass  # Избегаем цикла ошибок

# Webhook обработчик для продакшн
from telegram.ext import Updater
from aiohttp import web
import ssl

async def webhook_handler(request):
    """Обработчик webhook для продакшн развертывания"""
    try:
        data = await request.json()
        update = Update.de_json(data, context.bot)
        await context.process_update(update)
        return web.Response(status=200)
    except Exception as e:
        logger.error(f"Ошибка webhook: {e}")
        return web.Response(status=500)

# Главная функция для продакшн
def main():
    logger.info("Запуск UPAK бота в продакшн режиме")
    
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Добавление обработчиков команд
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("demo", demo))
    
    # Добавление обработчиков кнопок и сообщений
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Обработчик ошибок
    app.add_error_handler(error_handler)
    
    if WEBHOOK_URL:
        # Webhook режим для продакшн
        logger.info(f"Настройка webhook: {WEBHOOK_URL}")
        app.run_webhook(
            listen="0.0.0.0",
            port=WEBHOOK_PORT,
            url_path=TELEGRAM_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}"
        )
    else:
        # Polling режим
        logger.info("Запуск в режиме polling")
        app.run_polling()

if __name__ == "__main__":
    main()