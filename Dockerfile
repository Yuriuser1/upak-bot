
FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Создание пользователя для безопасности
RUN useradd --create-home --shell /bin/bash app

# Установка рабочей директории
WORKDIR /app

# Копирование requirements.txt и установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копирование кода приложения
COPY bot.py .
COPY .env* ./

# Изменение владельца файлов
RUN chown -R app:app /app

# Переключение на пользователя app
USER app

# Healthcheck для проверки работоспособности
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('https://api.telegram.org/bot${TELEGRAM_TOKEN}/getMe')" || exit 1

# Запуск бота
CMD ["python", "bot.py"]
