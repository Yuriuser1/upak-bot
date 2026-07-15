import html
import logging
import os
from typing import Any

import aiohttp
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)


load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_BASE_URL = os.getenv("UPAK_API_BASE_URL", "https://api.upak.space").rstrip("/")
SITE_URL = os.getenv("UPAK_SITE_URL", "https://www.upak.space").rstrip("/")
SUPPORT_URL = os.getenv("UPAK_SUPPORT_URL", "https://t.me/SellEasyBot")

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN is required")

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=os.getenv("LOG_LEVEL", "INFO"),
)
logger = logging.getLogger("upak-bot")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)

PACKAGES: dict[str, dict[str, Any]] = {
    "start": {
        "name": "Start",
        "price": "349 руб.",
        "cards": "1 карточка",
        "description": "SEO-описание, преимущества, характеристики и ТЗ для визуала.",
    },
    "pro": {
        "name": "Pro 10",
        "price": "2 490 руб.",
        "cards": "10 карточек",
        "description": "Основной пакет для селлеров, которым нужно быстро обновить линейку SKU.",
    },
    "business30": {
        "name": "Business 30",
        "price": "5 990 руб.",
        "cards": "30 карточек",
        "description": "Пакет для менеджеров маркетплейсов, фотостудий и регулярного потока товаров.",
    },
    "expert1": {
        "name": "Проверка специалистом",
        "price": "790 руб.",
        "cards": "1 карточка",
        "description": "Ручная проверка SEO, преимуществ, структуры и рекомендаций по визуалу.",
    },
    "expert10": {
        "name": "Проверка 10 карточек",
        "price": "4 990 руб.",
        "cards": "10 карточек",
        "description": "Ручная проверка пакета карточек перед публикацией или обновлением.",
    },
}

MARKETPLACES = ("Wildberries", "Ozon", "WB + Ozon", "Другая площадка")


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=False)


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Получить бесплатный preview", callback_data="preview")],
            [InlineKeyboardButton("Тарифы и оплата", callback_data="pricing")],
            [InlineKeyboardButton("Как это работает", callback_data="how"), InlineKeyboardButton("Сайт", url=SITE_URL)],
        ]
    )


def pricing_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Start - 349 руб.", callback_data="buy:start")],
            [InlineKeyboardButton("Pro 10 - 2 490 руб.", callback_data="buy:pro")],
            [InlineKeyboardButton("Business 30 - 5 990 руб.", callback_data="buy:business30")],
            [InlineKeyboardButton("Проверка - 790 руб.", callback_data="buy:expert1")],
            [InlineKeyboardButton("Проверка 10 - 4 990 руб.", callback_data="buy:expert10")],
            [InlineKeyboardButton("Бесплатный preview", callback_data="preview")],
        ]
    )


async def api_post(path: str, payload: dict[str, Any], params: dict[str, str] | None = None) -> dict[str, Any]:
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(f"{API_BASE_URL}{path}", json=payload, params=params) as response:
            data = await response.json(content_type=None)
            if response.status >= 400:
                raise RuntimeError(f"API error {response.status}: {data}")
            return data


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    text = (
        "<b>UPAK для карточек WB/Ozon</b>\n\n"
        "Помогаю быстро получить черновик карточки товара: название, SEO-фрагмент, преимущества "
        "и структуру для дальнейшей работы.\n\n"
        "<b>Воронка:</b>\n"
        "1. Бесплатный preview.\n"
        "2. Start за 349 руб.\n"
        "3. Pro 10, Business 30 или ручная проверка.\n\n"
        "Без обещаний топа и гарантированного роста продаж: даем понятную структуру и экономим время."
    )
    if update.message:
        await update.message.reply_html(text, reply_markup=main_keyboard())
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=main_keyboard(), parse_mode="HTML")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "<b>Команды UPAK</b>\n\n"
        "/start - главное меню\n"
        "/preview - бесплатный preview\n"
        "/pricing - тарифы и оплата\n\n"
        "Для preview достаточно описать товар: что это, для какой площадки, основные характеристики."
    )
    await update.message.reply_html(text, reply_markup=main_keyboard())


async def preview_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await begin_preview(update, context)


async def pricing_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await show_pricing(update, context)


async def begin_preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    context.user_data["flow"] = "preview_product"
    text = (
        "<b>Бесплатный preview</b>\n\n"
        "Пришлите описание товара одним сообщением. Например:\n"
        "<i>Женская демисезонная куртка, экокожа, размеры 42-50, для Wildberries.</i>\n\n"
        "Я верну короткий пример: название, 3 преимущества и фрагмент описания."
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="HTML")
    else:
        await update.message.reply_html(text)


async def show_pricing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lines = ["<b>Тарифы UPAK</b>", ""]
    for key in ("start", "pro", "business30", "expert1", "expert10"):
        item = PACKAGES[key]
        lines.append(f"<b>{esc(item['name'])}</b> - {esc(item['price'])}, {esc(item['cards'])}")
        lines.append(esc(item["description"]))
        lines.append("")
    lines.append("Для оплаты выберите тариф. Нужен email для чека YooKassa.")
    text = "\n".join(lines)
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=pricing_keyboard(), parse_mode="HTML")
    else:
        await update.message.reply_html(text, reply_markup=pricing_keyboard())


async def show_how(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "<b>Как работает UPAK</b>\n\n"
        "1. Вы отправляете товар и площадку.\n"
        "2. Получаете бесплатный preview.\n"
        "3. Если структура подходит, оплачиваете Start или пакет.\n"
        "4. Для сложных товаров можно заказать ручную проверку специалистом.\n\n"
        "Важно: результат помогает подготовить карточку, но продажи зависят также от цены, фото, отзывов, рекламы и конкуренции."
    )
    await update.callback_query.edit_message_text(text, reply_markup=main_keyboard(), parse_mode="HTML")


async def begin_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, package: str) -> None:
    item = PACKAGES[package]
    context.user_data.clear()
    context.user_data["flow"] = "payment_email"
    context.user_data["package"] = package
    text = (
        f"<b>{esc(item['name'])}</b>\n"
        f"Цена: <b>{esc(item['price'])}</b>\n"
        f"Объем: {esc(item['cards'])}\n\n"
        f"{esc(item['description'])}\n\n"
        "Пришлите email для онлайн-чека и ссылки на оплату."
    )
    await update.callback_query.edit_message_text(text, parse_mode="HTML")


async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    if data == "preview":
        await begin_preview(update, context)
    elif data == "pricing":
        await show_pricing(update, context)
    elif data == "how":
        await show_how(update, context)
    elif data.startswith("buy:"):
        package = data.split(":", 1)[1]
        if package not in PACKAGES:
            await query.edit_message_text("Тариф не найден. Откройте список тарифов заново.", reply_markup=main_keyboard())
            return
        await begin_payment(update, context, package)
    elif data == "menu":
        await start(update, context)


async def create_preview(update: Update, context: ContextTypes.DEFAULT_TYPE, product: str) -> None:
    user = update.effective_user
    telegram_contact = f"@{user.username}" if user and user.username else str(user.id if user else "")
    payload = {
        "product": product,
        "marketplace": "WB/Ozon",
        "telegram": telegram_contact,
    }

    await update.message.reply_text("Готовлю preview...")
    data = await api_post("/v2/preview", payload)

    advantages = data.get("advantages") or []
    advantages_text = "\n".join(f"- {esc(item)}" for item in advantages)
    text = (
        "<b>Ваш бесплатный preview</b>\n\n"
        f"<b>{esc(data.get('title'))}</b>\n\n"
        f"{advantages_text}\n\n"
        f"{esc(data.get('description_fragment'))}\n\n"
        f"<b>Следующий шаг:</b> {esc(data.get('next_step'))}"
    )
    await update.message.reply_html(text, reply_markup=pricing_keyboard())
    context.user_data.clear()


async def create_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, email: str) -> None:
    package = context.user_data.get("package")
    if package not in PACKAGES:
        context.user_data.clear()
        await update.message.reply_text("Не вижу выбранный тариф. Откройте тарифы заново.", reply_markup=pricing_keyboard())
        return

    user = update.effective_user
    telegram_contact = f"@{user.username}" if user and user.username else str(user.id if user else "")
    payload = {"email": email, "telegram": telegram_contact}

    await update.message.reply_text("Создаю ссылку на оплату YooKassa...")
    data = await api_post("/v2/payments/create-payment", payload, params={"subscription_type": package})
    payment_url = data.get("payment_url") or data.get("confirmation_url")
    item = PACKAGES[package]

    if not payment_url:
        raise RuntimeError("Payment URL is empty")

    text = (
        f"<b>Оплата {esc(item['name'])}</b>\n\n"
        f"Сумма: <b>{esc(item['price'])}</b>\n"
        f"Order ID: <code>{esc(data.get('order_id'))}</code>\n\n"
        "После оплаты вернитесь на сайт или напишите сюда: поможем довести карточку до результата."
    )
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Оплатить YooKassa", url=payment_url)],
            [InlineKeyboardButton("Получить еще preview", callback_data="preview")],
        ]
    )
    await update.message.reply_html(text, reply_markup=keyboard)
    context.user_data.clear()


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()
    flow = context.user_data.get("flow")

    try:
        if flow == "preview_product":
            if len(text) < 8:
                await update.message.reply_text("Опишите товар чуть подробнее: тип, характеристики и площадку.")
                return
            await create_preview(update, context, text)
            return

        if flow == "payment_email":
            if "@" not in text or "." not in text:
                await update.message.reply_text("Пришлите корректный email для онлайн-чека.")
                return
            await create_payment(update, context, text)
            return

        await update.message.reply_html(
            "Могу сделать бесплатный preview или показать тарифы. Выберите действие:",
            reply_markup=main_keyboard(),
        )
    except Exception as exc:
        logger.exception("Failed to process message")
        context.user_data.clear()
        await update.message.reply_html(
            "Сейчас не получилось выполнить действие автоматически. Попробуйте еще раз или откройте сайт.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("Открыть сайт", url=SITE_URL)],
                    [InlineKeyboardButton("Главное меню", callback_data="menu")],
                ]
            ),
        )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled bot error: %s", context.error)


def main() -> None:
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("preview", preview_command))
    app.add_handler(CommandHandler("pricing", pricing_command))
    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(error_handler)
    logger.info("UPAK Telegram bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
