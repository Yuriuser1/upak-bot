# ===== bot.py =====
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters

TOKEN = os.getenv("TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Сделать заказ", callback_data="order")],
        [InlineKeyboardButton("Цены", callback_data="pricing")],
        [InlineKeyboardButton("Как работает", callback_data="how")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Привет! Я помогу тебе упаковать карточку для Wildberries/Ozon.", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "order":
        await query.edit_message_text("Пришли ссылку на товар или краткое описание.")
        context.user_data['expecting_order'] = True
    elif query.data == "pricing":
        await query.edit_message_text("Цены:\nСтарт — 2 990 руб.\nСтандарт — 4 990 руб.\nПремиум — 7 990 руб.")
    elif query.data == "how":
        await query.edit_message_text("1. Отправь ссылку или описание товара\n2. Мы запускаем AI\n3. Через 48 часов ты получаешь готовую карточку")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('expecting_order'):
        text = update.message.text
        context.user_data['expecting_order'] = False
        await update.message.reply_text(f"Ваш заказ принят:\n{text}\nРезультат будет в течение 48 часов.")

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

if __name__ == '__main__':
    app.run_polling()

# ===== requirements.txt =====
python-telegram-bot==20.3

# ===== Procfile =====
worker: python bot.py
