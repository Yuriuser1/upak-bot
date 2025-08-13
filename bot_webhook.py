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
from flask import Flask, request

# Загружаем основной код бота
exec(open('bot.py').read().replace('if __name__ == "__main__":', 'if False:').replace('app.run_polling()', '# polling disabled'))

# Flask приложение для webhook
flask_app = Flask(__name__)

@flask_app.route('/webhook', methods=['POST'])
def webhook():
    """Обработка webhook от Telegram"""
    try:
        json_str = request.get_data().decode('UTF-8')
        update = Update.de_json(json.loads(json_str), app.bot)
        app.update_queue.put_nowait(update)
        return 'OK'
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return 'ERROR', 500

@flask_app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return {'status': 'ok', 'bot': 'UPAK-SellEasyBot', 'timestamp': datetime.now().isoformat()}

if __name__ == "__main__":
    # Для локального тестирования - запускаем Flask
    print("🚀 Starting UPAK Bot with webhook support...")
    print("📱 Bot: @SellEasyBot")
    print("🔧 Mode: Webhook (production ready)")
    print("🌐 Health check: http://localhost:5000/health")
    flask_app.run(host='0.0.0.0', port=5000, debug=False)
