FROM python:3.11-slim

# Настройки для корректного логгирования и работы Python в контейнере
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Установка системных зависимостей
# (Необходимо для сборки некоторых библиотек, например Pillow или python-docx, если нет binary wheel)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Установка Python-зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода приложения
COPY . .

# Railway ожидает, что приложение будет слушать порт, переданный в переменной $PORT.
# Мы используем EXPOSE для документации, но реальный порт будет взят из CMD.
EXPOSE 8080

# Команда запуска:
# 1. alembic upgrade head — применяет миграции базы данных при каждом деплое.
# 2. Запуск uvicorn без --reload (для продакшена) и на порту ${PORT}.
CMD sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"