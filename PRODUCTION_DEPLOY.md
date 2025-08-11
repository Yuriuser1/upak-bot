
# 🚀 Продакшн деплой UPAK Telegram Bot

## 📋 Предварительные требования

- Ubuntu 20.04+ или аналогичная Linux система
- Docker и Docker Compose (для контейнерного запуска)
- Python 3.11+ (для нативного запуска)
- Доступ к интернету
- Настроенные токены в .env файле

## 🐳 Деплой через Docker (рекомендуется)

### Подготовка
```bash
# 1. Убедитесь, что .env заполнен реальными токенами
cd /home/ubuntu/upak_repos/upak-bot
nano .env

# 2. Создайте директорию для логов
mkdir -p logs
```

### Сборка и запуск
```bash
# Сборка и запуск всех сервисов
docker-compose up -d --build

# Проверка статуса
docker-compose ps

# Просмотр логов
docker-compose logs -f upak-bot
```

### Управление
```bash
# Остановка
docker-compose down

# Перезапуск после изменений
docker-compose restart upak-bot

# Обновление кода
git pull
docker-compose up -d --build

# Просмотр логов конкретного сервиса
docker-compose logs -f upak-bot
docker-compose logs -f redis
```

## 🔧 Нативный деплой через systemd

### Установка как системный сервис
```bash
# 1. Копирование файла сервиса
sudo cp upak-bot.service /etc/systemd/system/

# 2. Перезагрузка systemd
sudo systemctl daemon-reload

# 3. Включение автозапуска
sudo systemctl enable upak-bot

# 4. Запуск сервиса
sudo systemctl start upak-bot
```

### Управление сервисом
```bash
# Статус сервиса
sudo systemctl status upak-bot

# Просмотр логов
sudo journalctl -u upak-bot -f

# Перезапуск
sudo systemctl restart upak-bot

# Остановка
sudo systemctl stop upak-bot

# Отключение автозапуска
sudo systemctl disable upak-bot
```

## 🔍 Мониторинг и логирование

### Логи Docker
```bash
# Все логи
docker-compose logs

# Только ошибки
docker-compose logs upak-bot | grep ERROR

# Логи с определенной даты
docker-compose logs --since="2024-01-01" upak-bot
```

### Логи systemd
```bash
# Все логи
sudo journalctl -u upak-bot

# Только ошибки
sudo journalctl -u upak-bot -p err

# Последние 100 строк
sudo journalctl -u upak-bot -n 100

# Мониторинг в реальном времени
sudo journalctl -u upak-bot -f
```

## 🔧 Настройка производительности

### Redis оптимизация
```bash
# Для Docker (в docker-compose.yml уже настроено)
# Для нативной установки Redis:
sudo nano /etc/redis/redis.conf

# Добавьте:
maxmemory 256mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

### Настройка лимитов для systemd
```bash
sudo nano /etc/systemd/system/upak-bot.service

# Добавить в секцию [Service]:
LimitNOFILE=65536
LimitNPROC=4096
```

## 🔒 Безопасность

### Firewall настройки
```bash
# Разрешить только исходящие подключения для бота
sudo ufw allow out 443/tcp  # HTTPS для API
sudo ufw allow out 80/tcp   # HTTP если нужно
```

### Бекап конфигурации
```bash
# Создание бекапа
tar -czf upak-bot-backup-$(date +%Y%m%d).tar.gz .env *.py *.md

# Бекап через cron (ежедневно в 2:00)
echo "0 2 * * * cd /home/ubuntu/upak_repos/upak-bot && tar -czf ~/backups/upak-bot-\$(date +\%Y\%m\%d).tar.gz .env *.py *.md" | crontab -
```

## 📊 Мониторинг

### Простой health check скрипт
```bash
#!/bin/bash
# health_check.sh

BOT_TOKEN=$(grep TELEGRAM_TOKEN .env | cut -d'=' -f2)
RESPONSE=$(curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getMe")

if echo "$RESPONSE" | grep -q '"ok":true'; then
    echo "✅ Bot is healthy"
    exit 0
else
    echo "❌ Bot is not responding"
    echo "Response: $RESPONSE"
    exit 1
fi
```

### Настройка уведомлений при падении
```bash
# Добавить в cron проверку каждые 5 минут
*/5 * * * * cd /home/ubuntu/upak_repos/upak-bot && ./health_check.sh || systemctl restart upak-bot
```

## 🚀 Автоматизация деплоя

### Скрипт быстрого деплоя
```bash
#!/bin/bash
# deploy.sh

set -e

echo "🚀 Начинаем деплой UPAK Bot..."

# Проверка .env
if [ ! -f .env ]; then
    echo "❌ Файл .env не найден!"
    exit 1
fi

# Проверка токенов
if ! grep -q "TELEGRAM_TOKEN=" .env || ! grep -q "YANDEX_GPT_API_KEY=" .env; then
    echo "❌ Обязательные токены не настроены в .env!"
    exit 1
fi

# Выбор метода деплоя
if command -v docker-compose &> /dev/null; then
    echo "🐳 Используем Docker..."
    docker-compose down
    docker-compose up -d --build
    echo "✅ Деплой через Docker завершен!"
else
    echo "🔧 Используем systemd..."
    sudo systemctl stop upak-bot 2>/dev/null || true
    source venv/bin/activate
    pip install -r requirements.txt
    sudo systemctl start upak-bot
    echo "✅ Деплой через systemd завершен!"
fi

echo "🎉 Бот успешно развернут и запущен!"
```

## 📈 Масштабирование

### Горизонтальное масштабирование
```yaml
# docker-compose.scale.yml
version: '3.8'

services:
  upak-bot:
    build: .
    restart: unless-stopped
    env_file:
      - .env
    depends_on:
      - redis
    networks:
      - upak-network
    deploy:
      replicas: 3  # Запуск 3 экземпляров
```

```bash
# Запуск с масштабированием
docker-compose -f docker-compose.yml -f docker-compose.scale.yml up -d --scale upak-bot=3
```

## ⚠️ Важные замечания

1. **Токены безопасности**: Никогда не коммитьте .env в git
2. **Бекапы**: Регулярно делайте бекапы конфигурации
3. **Мониторинг**: Настройте уведомления о падении сервиса
4. **Логи**: Ротируйте логи для экономии места
5. **Обновления**: Регулярно обновляйте зависимости

## 📞 Поддержка

При проблемах с деплоем:
- Проверьте логи: `docker-compose logs` или `journalctl -u upak-bot`
- Убедитесь в правильности токенов в .env
- Проверьте доступность внешних API
- Свяжитесь с поддержкой: support@upak.space
