import logging
import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# Настройка логов
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Стартовое сообщение
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[
        InlineKeyboardButton("📦 Заказать упаковку", callback_data='order_packaging'),
        InlineKeyboardButton("ℹ️ О проекте UPAK", callback_data='about')
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Добро пожаловать в UPAK! Мы помогаем продавцам на Wildberries и Ozon создавать идеальные карточки товаров с помощью ИИ.", reply_markup=reply_markup)

# Обработка кнопок
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'order_packaging':
        await query.edit_message_text("Пожалуйста, отправьте текстовое описание товара или ссылку на него. Мы подготовим упаковку с помощью нейросети.")
    elif query.data == 'about':
        await query.edit_message_text("UPAK — нейросервис для упаковки карточек товаров. Генерация заголовков, описаний, преимуществ, характеристик и изображений. Подробнее: https://www.upak.space")

# Заглушка генерации от Deep Agent (позже заменить реальным вызовом)
def generate_card_data(product_text: str) -> dict:
    # Здесь будет вызов реального API (например, OpenAI / Deep Agent)
    return {
        "title": f"🔸 Уникальное название для: {product_text}",
        "description": f"💬 Это описание товара, сгенерированное ИИ для: {product_text}",
        "features": ["⚡ Быстрая доставка", "🔒 Гарантия качества", "🌟 Высокий рейтинг"],
        "image_url": "https://via.placeholder.com/512x512.png?text=UPAK"
    }

# Обработка текстов
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    await update.message.reply_text("🧠 Генерируем упаковку... Пожалуйста, подождите 10–15 секунд.")

    data = generate_card_data(user_text)

    caption = f"*{data['title']}*\n\n{data['description']}\n\n" + "\n".join(data['features'])

    await update.message.reply_photo(photo=data['image_url'], caption=caption, parse_mode='Markdown')

# Обработка ошибок
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logging.error(msg="Ошибка при обработке запроса:", exc_info=context.error)

# Получение токена из переменных окружения
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("Не установлена переменная окружения TOKEN")

# Запуск
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
app.add_error_handler(error_handler)

if __name__ == "__main__":
    app.run_polling()
