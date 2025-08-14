#!/bin/bash

# Bot Watchdog - Автоматический мониторинг и перезапуск UPAK Bot
# Проверяет работоспособность бота и перезапускает при необходимости

set -e

SCRIPT_DIR="/home/ubuntu/upak-bot"
HEALTH_CHECK_SCRIPT="$SCRIPT_DIR/monitoring/health_check.sh"
LOG_FILE="/var/log/upak-bot-watchdog.log"
SERVICE_NAME="upak-bot"
MAX_RESTART_ATTEMPTS=3
RESTART_COOLDOWN=300  # 5 минут между попытками перезапуска

# Цвета для вывода
COLOR_GREEN='\033[0;32m'
COLOR_RED='\033[0;31m'
COLOR_YELLOW='\033[1;33m'
COLOR_BLUE='\033[0;34m'
COLOR_RESET='\033[0m'

# Функция логирования
log_message() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "[$timestamp] $message" | tee -a "$LOG_FILE"
}

# Функция проверки здоровья бота
check_bot_health() {
    if [ -f "$HEALTH_CHECK_SCRIPT" ]; then
        cd "$SCRIPT_DIR"
        if bash "$HEALTH_CHECK_SCRIPT" >/dev/null 2>&1; then
            return 0  # Бот работает
        else
            return 1  # Бот не работает
        fi
    else
        log_message "${COLOR_RED}❌ Health check скрипт не найден: $HEALTH_CHECK_SCRIPT${COLOR_RESET}"
        return 1
    fi
}

# Функция перезапуска бота
restart_bot() {
    log_message "${COLOR_YELLOW}🔄 Перезапускаем бота...${COLOR_RESET}"
    
    # Останавливаем сервис
    sudo systemctl stop "$SERVICE_NAME" 2>/dev/null || true
    sleep 5
    
    # Запускаем сервис
    if sudo systemctl start "$SERVICE_NAME"; then
        sleep 10  # Даем время боту запуститься
        
        # Проверяем что бот действительно запустился
        if check_bot_health; then
            log_message "${COLOR_GREEN}✅ Бот успешно перезапущен и работает${COLOR_RESET}"
            return 0
        else
            log_message "${COLOR_RED}❌ Бот перезапущен, но health check не прошел${COLOR_RESET}"
            return 1
        fi
    else
        log_message "${COLOR_RED}❌ Ошибка при перезапуске сервиса${COLOR_RESET}"
        return 1
    fi
}

# Основная функция мониторинга
main_monitor() {
    log_message "${COLOR_BLUE}🔍 Запуск мониторинга бота...${COLOR_RESET}"
    
    local restart_attempts=0
    local last_restart_time=0
    
    while true; do
        if check_bot_health; then
            log_message "${COLOR_GREEN}✅ Бот работает нормально${COLOR_RESET}"
            restart_attempts=0  # Сбрасываем счетчик при успешной проверке
        else
            log_message "${COLOR_RED}❌ Бот не отвечает или работает некорректно${COLOR_RESET}"
            
            # Проверяем лимиты перезапуска
            current_time=$(date +%s)
            if [ $restart_attempts -ge $MAX_RESTART_ATTEMPTS ]; then
                if [ $((current_time - last_restart_time)) -lt $RESTART_COOLDOWN ]; then
                    log_message "${COLOR_YELLOW}⏳ Превышен лимит перезапусков. Ожидание ${RESTART_COOLDOWN}с...${COLOR_RESET}"
                    sleep 60
                    continue
                else
                    # Период ожидания прошел, сбрасываем счетчик
                    restart_attempts=0
                fi
            fi
            
            # Пытаемся перезапустить
            if restart_bot; then
                restart_attempts=0
                last_restart_time=$current_time
            else
                restart_attempts=$((restart_attempts + 1))
                last_restart_time=$current_time
                log_message "${COLOR_RED}❌ Попытка перезапуска $restart_attempts из $MAX_RESTART_ATTEMPTS неудачна${COLOR_RESET}"
            fi
        fi
        
        # Ожидание перед следующей проверкой
        sleep 60
    done
}

# Проверяем аргументы командной строки
case "${1:-monitor}" in
    "monitor"|"")
        main_monitor
        ;;
    "check")
        echo "🔍 Однократная проверка здоровья бота..."
        if check_bot_health; then
            echo -e "${COLOR_GREEN}✅ Бот работает${COLOR_RESET}"
            exit 0
        else
            echo -e "${COLOR_RED}❌ Бот не работает${COLOR_RESET}"
            exit 1
        fi
        ;;
    "restart")
        echo "🔄 Принудительный перезапуск бота..."
        if restart_bot; then
            echo -e "${COLOR_GREEN}✅ Перезапуск выполнен${COLOR_RESET}"
            exit 0
        else
            echo -e "${COLOR_RED}❌ Ошибка перезапуска${COLOR_RESET}"
            exit 1
        fi
        ;;
    *)
        echo "UPAK Bot Watchdog"
        echo "Использование: $0 [monitor|check|restart]"
        echo ""
        echo "Команды:"
        echo "  monitor  - Запуск непрерывного мониторинга (по умолчанию)"
        echo "  check    - Однократная проверка здоровья бота"
        echo "  restart  - Принудительный перезапуск бота"
        exit 1
        ;;
esac