# ai_service/core/workers/worker.py - Воркер Dramatiq

#region Импорты и библиотеки

import asyncio

from core.workers.broker import redis_broker as broker
from core.infrastructure.database import init_database
from core.observability.logger import logger

#endregion

#region Инициализация worker-процессов Dramatiq

def init_database_worker() -> None:
    
    logger.launch("Dramatiq worker | Запуск инициализации БД...")

    try:
        asyncio.run(init_database())
    except Exception as err:
        logger.error(f"Dramatiq worker | Ошибка инициализации БД: {err}", exc_info = True)
        raise
    
    logger.launch("Dramatiq worker | Инициализация БД успешно завершена")

def setup_dramatiq_worker() -> None:
    
    logger.launch("Dramatiq worker | Настройка воркера...")
    init_database_worker()
    logger.launch("Dramatiq worker | Воркер успешно настроен")

setup_dramatiq_worker()

#endregion
