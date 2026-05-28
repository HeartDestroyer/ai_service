# AI-service Dockerfile

# ----- ЭТАП 1: Сборщик зависимостей -----
# Называем этот этап "builder", чтобы потом на него сослаться
FROM python:3.12-slim AS builder

# Устанавливаем системные зависимости для psycopg2 и SCRAM, python3-dev для prometheus-client
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Отключаем создание .pyc файлов
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Создаем виртуальное окружение и активируем его
RUN python -m venv .venv
ENV PATH="/app/.venv/bin:$PATH"

# Копируем только файл с зависимостями, этот слой будет сброшен только если изменится сам requirements.txt
COPY requirements.txt .

# Устанавливаем зависимости в виртуальное окружение
RUN pip install --no-cache-dir -r requirements.txt


# ----- ЭТАП 2: Основной образ -----
# Используем официальный образ Python
FROM python:3.12-slim

# Устанавливаем runtime-зависимости, в данном случае libpq5 для psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Создаем пользователя и группу с ограниченными правами
RUN addgroup --system app && adduser --system --group app

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Создаем директорию для логов и назначаем права пользователю app
RUN mkdir -p /app/logs && chown -R app:app /app/logs
# Создаем директорию для хранения файлов и назначаем владельцем нашего пользователя
RUN mkdir -p /app/storage && chown -R app:app /app/storage
# Создаем директорию для временных файлов и назначаем владельцем нашего пользователя
RUN mkdir -p /app/shared_tmp && chown -R app:app /app/shared_tmp
# Создаем директории для метрик Prometheus (multiprocess mode) и назначаем владельцем нашего пользователя
RUN mkdir -p /app/dramatiq_metrics && chown -R app:app /app/dramatiq_metrics
RUN mkdir -p /app/app_metrics && chown -R app:app /app/app_metrics
RUN mkdir -p /app/dramatiq_metrics/prometheus_multiproc && chown -R app:app /app/dramatiq_metrics/prometheus_multiproc
RUN mkdir -p /app/app_metrics/prometheus_multiproc && chown -R app:app /app/app_metrics/prometheus_multiproc

# Копируем виртуальное окружение из сборщика
COPY --from=builder /app/.venv ./.venv

# Копируем исходный код и выставляем права для нового пользователя
COPY --chown=app:app ./cmd /app/cmd
COPY --chown=app:app ./core /app/core
COPY --chown=app:app ./modules /app/modules
COPY --chown=app:app ./infrastructure /app/infrastructure
COPY --chown=app:app ./alembic /app/alembic
COPY --chown=app:app ./alembic.ini /app/alembic.ini

# Активируем виртуальное окружение
ENV PATH="/app/.venv/bin:$PATH"

# Отключаем создание .pyc файлов и буферизацию
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Переключаемся на non-root пользователя
USER app

# Открываем порт, на котором будет работать приложение
EXPOSE 8000

# Указываем команду для запуска приложения при старте контейнера
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "cmd.main:create_application", "--bind", "0.0.0.0:8000"]
