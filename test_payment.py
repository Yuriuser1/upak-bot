#!/usr/bin/env python3
"""
Тест создания платежа через YooKassa API
"""
import asyncio
import os
import base64
import aiohttp
import uuid
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()
YANDEX_CHECKOUT_KEY = os.getenv("YANDEX_CHECKOUT_KEY")
YANDEX_CHECKOUT_SHOP_ID = os.getenv("YANDEX_CHECKOUT_SHOP_ID")

async def test_create_payment():
    """Тестирование создания платежа через YooKassa API"""
    if not (YANDEX_CHECKOUT_KEY and YANDEX_CHECKOUT_SHOP_ID):
        print("❌ Ошибка: не настроены переменные окружения для YooKassa")
        return False
    
    print("🔧 Настройки YooKassa:")
    print(f"Shop ID: {YANDEX_CHECKOUT_SHOP_ID}")
    print(f"API Key: {YANDEX_CHECKOUT_KEY[:20]}...")
    print("")
    
    # Создаем тестовый платеж
    payment_id = str(uuid.uuid4())
    auth_string = base64.b64encode(f"{YANDEX_CHECKOUT_SHOP_ID}:{YANDEX_CHECKOUT_KEY}".encode()).decode()
    
    payload = {
        "amount": {"value": "10.00", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": "https://upak.space/payment-success"},
        "capture": True,
        "description": "Тестовый платеж UPAK Bot",
        "metadata": {"user_id": "test_user", "service": "upak_platform", "tariff": "basic"},
        "receipt": {
            "customer": {
                "email": "test@upak.space"
            },
            "items": [
                {
                    "description": "Тестовая услуга UPAK",
                    "quantity": "1.00",
                    "amount": {
                        "value": "10.00",
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
    
    print("📝 Создаем тестовый платеж...")
    print(f"Сумма: {payload['amount']['value']} {payload['amount']['currency']}")
    print(f"Описание: {payload['description']}")
    print("")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.yookassa.ru/v3/payments",
                json=payload,
                headers=headers
            ) as response:
                
                print(f"📡 Ответ API: {response.status}")
                response_text = await response.text()
                
                if response.status == 200:
                    data = await response.json()
                    print("✅ Платеж создан успешно!")
                    print(f"ID платежа: {data.get('id')}")
                    print(f"Статус: {data.get('status')}")
                    print(f"Сумма: {data.get('amount', {}).get('value')} {data.get('amount', {}).get('currency')}")
                    print(f"Ссылка для оплаты: {data.get('confirmation', {}).get('confirmation_url')}")
                    return True
                else:
                    print(f"❌ Ошибка создания платежа: {response.status}")
                    print(f"Ответ API: {response_text}")
                    return False
                    
    except Exception as e:
        print(f"❌ Исключение при создании платежа: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Запуск теста создания платежа YooKassa")
    print("=" * 50)
    result = asyncio.run(test_create_payment())
    print("=" * 50)
    if result:
        print("✅ ТЕСТ ПРОЙДЕН: Платежная система настроена корректно!")
    else:
        print("❌ ТЕСТ ПРОВАЛЕН: Необходимо проверить настройки платежной системы.")
