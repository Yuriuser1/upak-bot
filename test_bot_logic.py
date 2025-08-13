#!/usr/bin/env python3
"""
Тестовый скрипт для проверки основной логики бота UPAK
Проверяет корректность функций без подключения к Telegram API
"""

import sys
import os
import asyncio
import json
from unittest.mock import Mock, AsyncMock
from dotenv import load_dotenv

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Настраиваем тестовое окружение
os.environ["TELEGRAM_TOKEN"] = "test_token_123456"
os.environ["YANDEX_GPT_API_KEY"] = "test_yandex_key"
load_dotenv()

# Импортируем функции из основного бота
try:
    from bot import generate_card_data, ProductCard, add_lead_to_bitrix24, create_payment_link, track_event
    print("✅ Импорт модулей успешен")
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    sys.exit(1)

async def test_product_card_model():
    """Тестируем модель данных ProductCard"""
    print("\n🧪 Тестируем модель ProductCard...")
    
    try:
        # Тест корректных данных
        card = ProductCard(
            title="Тестовый товар",
            description="Описание тестового товара" * 10,  # Длинное описание
            features=["Преимущество 1", "Преимущество 2", "Преимущество 3"],
            image_url="https://cdn.dribbble.com/userupload/43069729/file/original-40e331a12ec6a78feb8d653ab7eadfca.png?resize=400x0"
        )
        print("✅ Создание ProductCard с корректными данными")
        
        # Тест слишком длинного заголовка
        try:
            long_title = "x" * 150  # Превышает лимит в 100 символов
            ProductCard(
                title=long_title,
                description="Описание",
                features=["Преимущество"],
                image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/b/b5/Russian_playing_card_deck_%28face_cards%29_Russian_style_1911_original.jpg/960px-Russian_playing_card_deck_%28face_cards%29_Russian_style_1911_original.jpg"
            )
            print("❌ Валидация длины заголовка не работает")
        except:
            print("✅ Валидация длины заголовка работает")
            
    except Exception as e:
        print(f"❌ Ошибка тестирования ProductCard: {e}")

async def test_generate_card_data():
    """Тестируем функцию генерации карточки"""
    print("\n🧪 Тестируем generate_card_data...")
    
    try:
        # Поскольку у нас нет реального API ключа, функция должна вернуть fallback
        card = await generate_card_data("Тестовый товар для проверки", "test_user_123")
        
        print(f"✅ Функция generate_card_data работает")
        print(f"   - Title: {card.title}")
        print(f"   - Description length: {len(card.description)} символов")
        print(f"   - Features count: {len(card.features)}")
        print(f"   - Image URL: {card.image_url}")
        
        # Проверяем, что возвращается fallback (ошибка генерации)
        if card.title == "Ошибка генерации":
            print("✅ Fallback для ошибки API работает корректно")
        
    except Exception as e:
        print(f"❌ Ошибка в generate_card_data: {e}")

async def test_bitrix_integration():
    """Тестируем интеграцию с Bitrix24"""
    print("\n🧪 Тестируем add_lead_to_bitrix24...")
    
    try:
        # Функция должна работать без ошибок даже без реального webhook
        await add_lead_to_bitrix24("test_user_123", "test_username", "test_service")
        print("✅ add_lead_to_bitrix24 работает (без webhook это нормально)")
    except Exception as e:
        print(f"❌ Ошибка в add_lead_to_bitrix24: {e}")

async def test_payment_integration():
    """Тестируем интеграцию с платежной системой"""
    print("\n🧪 Тестируем create_payment_link...")
    
    try:
        payment_url = await create_payment_link("test_user_123", "upak_platform", "basic", 990.0)
        print(f"✅ create_payment_link работает: {payment_url}")
        
        # Без настроенного Yandex.Checkout должна вернуться заглушка
        if "payment-not-configured" in payment_url:
            print("✅ Fallback для отсутствующей платежной системы работает")
            
    except Exception as e:
        print(f"❌ Ошибка в create_payment_link: {e}")

async def test_analytics_integration():
    """Тестируем интеграцию с аналитикой"""
    print("\n🧪 Тестируем track_event...")
    
    try:
        await track_event("test_user_123", "test_event")
        print("✅ track_event работает (без Yandex Metrika это нормально)")
    except Exception as e:
        print(f"❌ Ошибка в track_event: {e}")

def test_environment_variables():
    """Тестируем загрузку переменных окружения"""
    print("\n🧪 Тестируем переменные окружения...")
    
    required_vars = ["TELEGRAM_TOKEN", "YANDEX_GPT_API_KEY"]
    optional_vars = ["BITRIX24_WEBHOOK", "YANDEX_CHECKOUT_KEY", "YANDEX_METRIKA_ID", "REDIS_URL"]
    
    for var in required_vars:
        if os.getenv(var):
            print(f"✅ {var} установлена")
        else:
            print(f"❌ {var} не установлена (обязательная)")
    
    for var in optional_vars:
        if os.getenv(var):
            print(f"✅ {var} установлена")
        else:
            print(f"ℹ️  {var} не установлена (опциональная)")

async def main():
    """Главная функция тестирования"""
    print("🚀 Запуск тестов бота UPAK")
    print("=" * 50)
    
    # Тестируем переменные окружения
    test_environment_variables()
    
    # Тестируем модели данных
    await test_product_card_model()
    
    # Тестируем основные функции
    await test_generate_card_data()
    await test_bitrix_integration()
    await test_payment_integration()
    await test_analytics_integration()
    
    print("\n" + "=" * 50)
    print("🏁 Тестирование завершено")
    print("\n📋 Следующие шаги для продакшн:")
    print("1. Получить реальный TELEGRAM_TOKEN от @BotFather")
    print("2. Получить YANDEX_GPT_API_KEY для ИИ-генерации")
    print("3. Настроить дополнительные интеграции (опционально)")
    print("4. Запустить бота с реальными токенами")

if __name__ == "__main__":
    asyncio.run(main())
