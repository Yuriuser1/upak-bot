#!/bin/bash

# Health Check скрипт для UPAK Telegram Bot
# Проверяет работоспособность бота через Telegram API

set -e

COLOR_GREEN='\033[0;32m'
COLOR_RED='\033[0;31m'
COLOR_YELLOW='\033[1;33m'
COLOR_RESET='\033[0m'

# Загружаем токен из .env
if [ -f .env ]; then
    BOT_TOKEN=$(grep TELEGRAM_TOKEN .env | cut -d'=' -f2 | tr -d '"' | tr -d ' ')
else
    echo -e "${COLOR_RED}❌ .env файл не найден${COLOR_RESET}"
    exit 1
fi

if [ -z "$BOT_TOKEN" ]; then
    echo -e "${COLOR_RED}❌ TELEGRAM_TOKEN не настроен${COLOR_RESET}"
    exit 1
fi

# Проверяем ответ Telegram API
echo "🔍 Проверяем работоспособность бота..."

RESPONSE=$(curl -s -w "HTTPSTATUS:%{http_code}" "https://api.telegram.org/bot${BOT_TOKEN}/getMe")
HTTP_STATUS=$(echo $RESPONSE | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')
BODY=$(echo $RESPONSE | sed -e 's/HTTPSTATUS\:.*/g')

if [ "$HTTP_STATUS" -eq 200 ]; then
    if echo "$BODY" | grep -q '"ok":true'; then
        BOT_USERNAME=$(echo "$BODY" | grep -o '"username":"[^"]*"' | cut -d'"' -f4)
        BOT_FIRST_NAME=$(echo "$BODY" | grep -o '"first_name":"[^"]*"' | cut -d'"' -f4)
        
        echo -e "${COLOR_GREEN}✅ Бот работает корректно!${COLOR_RESET}"
        echo "🤖 Имя: $BOT_FIRST_NAME"
        echo "👤 Username: @$BOT_USERNAME"
        echo "🔗 Ссылка: https://t.me/$BOT_USERNAME"
        exit 0
    else
        echo -e "${COLOR_RED}❌ API вернул ошибку${COLOR_RESET}"
        echo "Ответ: $BODY"
        exit 1
    fi
else
    echo -e "${COLOR_RED}❌ HTTP ошибка: $HTTP_STATUS${COLOR_RESET}"
    echo "Ответ: $BODY"
    exit 1
fi