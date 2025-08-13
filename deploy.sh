
#!/bin/bash

# Скрипт автоматического деплоя UPAK Telegram Bot
# Версия: 1.0
# Дата: 11.08.2025

set -e

COLOR_GREEN='\033[0;32m'
COLOR_RED='\033[0;31m'
COLOR_YELLOW='\033[1;33m'
COLOR_BLUE='\033[0;34m'
COLOR_RESET='\033[0m'

echo -e "${COLOR_BLUE}🚀 UPAK Bot Production Deployment Script${COLOR_RESET}"
echo "================================================"

# Функция логирования
log() {
    echo -e "${COLOR_GREEN}[INFO]${COLOR_RESET} $1"
}

warn() {
    echo -e "${COLOR_YELLOW}[WARN]${COLOR_RESET} $1"
}

error() {
    echo -e "${COLOR_RED}[ERROR]${COLOR_RESET} $1"
    exit 1
}

# Проверка текущей директории
if [ ! -f "bot.py" ]; then
    error "bot.py не найден! Запустите скрипт из директории проекта."
fi

# Проверка .env файла
log "Проверяем конфигурацию..."
if [ ! -f .env ]; then
    error "Файл .env не найден! Создайте его по образцу."
fi

# Проверка обязательных токенов
if ! grep -q "TELEGRAM_TOKEN=.*[^[:space:]]" .env; then
    error "TELEGRAM_TOKEN не настроен в .env!"
fi

if ! grep -q "YANDEX_GPT_API_KEY=.*[^[:space:]]" .env; then
    error "YANDEX_GPT_API_KEY не настроен в .env!"
fi

log "✅ Конфигурация проверена"

# Выбор метода деплоя
echo
echo "Выберите метод деплоя:"
echo "1) Docker Compose (рекомендуется)"
echo "2) Systemd Service"
echo "3) Прямой запуск (для тестирования)"
echo -n "Ваш выбор (1-3): "
read choice

case $choice in
    1)
        log "🐳 Используем Docker Compose..."
        
        if ! command -v docker &> /dev/null || ! command -v docker-compose &> /dev/null; then
            error "Docker или Docker Compose не установлены!"
        fi
        
        # Остановка предыдущих контейнеров
        docker-compose down 2>/dev/null || true
        
        # Создание директории для логов
        mkdir -p logs
        
        # Сборка и запуск
        log "Собираем и запускаем контейнеры..."
        docker-compose up -d --build
        
        # Проверка статуса
        sleep 5
        if docker-compose ps | grep -q "Up"; then
            log "✅ Контейнеры запущены успешно!"
            log "Проверить статус: docker-compose ps"
            log "Просмотр логов: docker-compose logs -f upak-bot"
        else
            error "Контейнеры не запустились. Проверьте логи: docker-compose logs"
        fi
        ;;
        
    2)
        log "🔧 Используем Systemd..."
        
        # Проверка виртуального окружения
        if [ ! -d "venv" ]; then
            log "Создаем виртуальное окружение..."
            python3 -m venv venv
        fi
        
        # Активация и установка зависимостей
        log "Устанавливаем зависимости..."
        source venv/bin/activate
        pip install -r requirements.txt
        
        # Установка systemd сервиса
        log "Устанавливаем systemd сервис..."
        sudo cp upak-bot.service /etc/systemd/system/
        sudo systemctl daemon-reload
        
        # Остановка предыдущего сервиса
        sudo systemctl stop upak-bot 2>/dev/null || true
        
        # Запуск сервиса
        sudo systemctl enable upak-bot
        sudo systemctl start upak-bot
        
        # Проверка статуса
        sleep 3
        if systemctl is-active --quiet upak-bot; then
            log "✅ Сервис запущен успешно!"
            log "Проверить статус: sudo systemctl status upak-bot"
            log "Просмотр логов: sudo journalctl -u upak-bot -f"
        else
            error "Сервис не запустился. Проверьте логи: sudo journalctl -u upak-bot"
        fi
        ;;
        
    3)
        log "🧪 Прямой запуск для тестирования..."
        
        # Проверка виртуального окружения
        if [ ! -d "venv" ]; then
            log "Создаем виртуальное окружение..."
            python3 -m venv venv
        fi
        
        # Активация и установка зависимостей
        log "Устанавливаем зависимости..."
        source venv/bin/activate
        pip install -r requirements.txt
        
        # Запуск бота
        log "🤖 Запускаем бота..."
        log "Для остановки используйте Ctrl+C"
        python bot.py
        ;;
        
    *)
        error "Неверный выбор!"
        ;;
esac

echo
log "🎉 Деплой завершен успешно!"
log "Бот UPAK запущен и готов к работе!"

# Показать health check
echo
log "🔍 Проверка работоспособности..."
sleep 2

BOT_TOKEN=$(grep TELEGRAM_TOKEN .env | cut -d'=' -f2)
if [ -n "$BOT_TOKEN" ]; then
    RESPONSE=$(curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getMe" || echo "")
    if echo "$RESPONSE" | grep -q '"ok":true'; then
        log "✅ Бот отвечает корректно!"
        BOT_USERNAME=$(echo "$RESPONSE" | grep -o '"username":"[^"]*"' | cut -d'"' -f4)
        log "🤖 Username бота: @${BOT_USERNAME}"
        log "🔗 Ссылка на бота: https://t.me/${BOT_USERNAME}"
    else
        warn "⚠️  Бот может быть еще не готов или есть проблемы с токеном"
        warn "Проверьте логи через несколько минут"
    fi
fi

echo
log "📊 Полезные команды:"
if [ "$choice" = "1" ]; then
    echo "  docker-compose ps              - статус контейнеров"
    echo "  docker-compose logs -f upak-bot - логи бота"
    echo "  docker-compose restart upak-bot - перезапуск"
    echo "  docker-compose down            - остановка"
elif [ "$choice" = "2" ]; then
    echo "  sudo systemctl status upak-bot   - статус сервиса"
    echo "  sudo journalctl -u upak-bot -f  - логи сервиса"
    echo "  sudo systemctl restart upak-bot - перезапуск"
    echo "  sudo systemctl stop upak-bot    - остановка"
fi

log "📖 Подробная документация в файлах SETUP_INSTRUCTIONS.md и PRODUCTION_DEPLOY.md"
