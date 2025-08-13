import requests
import json
import time

# Константы
TOKEN = "TEST_TOKEN"  # Заменить на реальный токен
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
CHAT_ID = "TEST_CHAT_ID"  # Заменить на реальный chat_id

def get_updates():
    """Получение обновлений от Telegram"""
    response = requests.get(f"{BASE_URL}/getUpdates")
    return response.json()

def send_message(chat_id, text):
    """Отправка текстового сообщения"""
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    response = requests.post(f"{BASE_URL}/sendMessage", json=payload)
    return response.json()

def test_bot_connectivity():
    """Тестирование подключения к боту"""
    try:
        response = requests.get(f"{BASE_URL}/getMe")
        data = response.json()
        if data.get('ok'):
            bot_info = data['result']
            print(f"✅ Бот подключен: {bot_info.get('first_name')} (@{bot_info.get('username')})")
            return True
        else:
            print(f"❌ Ошибка подключения: {data}")
            return False
    except Exception as e:
        print(f"❌ Исключение при подключении: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Тестирование функций бота UPAK")
    print("=" * 40)
    
    # Тестируем подключение
    if test_bot_connectivity():
        print("✅ Основные функции работают")
    else:
        print("❌ Проверьте настройки бота")
