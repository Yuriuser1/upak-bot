"""
Главный модуль бота UPAK
"""
import asyncio
import logging
import signal
import sys
from typing import Optional
import systemd_watchdog
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from bot.config import config
from bot.database import db
from bot.ai_services import ai_manager
from bot.integrations import integration_manager
from bot.handlers import handlers
from bot.health import health_checker

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, config.LOG_LEVEL),
    handlers=[
        logging.FileHandler('/home/ubuntu/upak-bot/logs/bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class UPAKBot:
    """Основной класс бота UPAK"""
    
    def __init__(self):
        self.application: Optional[Application] = None
        self.watchdog: Optional[systemd_watchdog.watchdog] = None
        self.running = False
    
    async def initialize(self) -> None:
        """Инициализация бота и всех компонентов"""
        try:
            logger.info("Инициализация бота UPAK...")
            
            # Валидация конфигурации
            config.validate()
            
            # Инициализация базы данных
            await db.initialize()
            
            # Инициализация AI сервисов
            await ai_manager.initialize()
            
            # Инициализация интеграций
            await integration_manager.initialize()
            
            # Создание Telegram приложения
            self.application = Application.builder().token(config.TELEGRAM_TOKEN).build()
            
            # Регистрация обработчиков
            self.application.add_handler(CommandHandler("start", handlers.start_command))
            self.application.add_handler(CallbackQueryHandler(handlers.button_handler))
            self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.message_handler))
            
            # Инициализация systemd watchdog
            self.watchdog = systemd_watchdog.watchdog()
            if self.watchdog.enabled():
                logger.info("Systemd watchdog активирован")
            
            # Запуск health check сервера
            await health_checker.start_server(8080)
            
            logger.info("Бот UPAK успешно инициализирован")
            
        except Exception as e:
            logger.error(f"Ошибка инициализации бота: {e}")
            raise
    
    async def start(self) -> None:
        """Запуск бота"""
        try:
            await self.initialize()
            
            # Уведомление systemd о готовности
            if self.watchdog and self.watchdog.enabled():
                self.watchdog.ready()
                self.watchdog.status("Bot started and running")
            
            # Запуск бота
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=["message", "callback_query"]
            )
            
            self.running = True
            logger.info("Бот UPAK запущен и готов к работе")
            
            # Основной цикл с watchdog
            await self._main_loop()
            
        except Exception as e:
            logger.error(f"Ошибка запуска бота: {e}")
            raise
    
    async def _main_loop(self) -> None:
        """Основной цикл работы бота"""
        try:
            while self.running:
                # Отправка watchdog ping
                if self.watchdog and self.watchdog.enabled():
                    self.watchdog.ping()
                
                # Ожидание перед следующей итерацией
                await asyncio.sleep(10)
                
        except asyncio.CancelledError:
            logger.info("Основной цикл бота прерван")
        except Exception as e:
            logger.error(f"Ошибка в основном цикле: {e}")
            raise
    
    async def stop(self) -> None:
        """Остановка бота"""
        try:
            logger.info("Остановка бота UPAK...")
            self.running = False
            
            # Уведомление systemd об остановке
            if self.watchdog and self.watchdog.enabled():
                self.watchdog.status("Bot stopping...")
            
            # Остановка Telegram приложения
            if self.application:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
            
            # Остановка health check сервера
            await health_checker.stop_server()
            
            # Закрытие соединений
            await ai_manager.close()
            await integration_manager.close()
            await db.close()
            
            logger.info("Бот UPAK успешно остановлен")
            
        except Exception as e:
            logger.error(f"Ошибка остановки бота: {e}")
    
    def setup_signal_handlers(self) -> None:
        """Настройка обработчиков сигналов"""
        def signal_handler(signum, frame):
            logger.info(f"Получен сигнал {signum}, начинаем graceful shutdown...")
            asyncio.create_task(self.stop())
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

async def main():
    """Главная функция"""
    bot = UPAKBot()
    bot.setup_signal_handlers()
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)
    finally:
        await bot.stop()

if __name__ == "__main__":
    # Создание директории для логов
    import os
    os.makedirs("/home/ubuntu/upak-bot/logs", exist_ok=True)
    
    # Запуск бота
    asyncio.run(main())