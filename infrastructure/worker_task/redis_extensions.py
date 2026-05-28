# ai_service/infrastructure/worker_task/redis_extensions.py - Расширения Redis для фоновых задач

#region Импорты и библиотеки

import inspect
from contextlib import asynccontextmanager, contextmanager
import redis
import redis.asyncio as aioredis

from core.configuration.settings import settings
from core.observability.logger import logger

#endregion

#region Параметры подключения Redis для воркеров

def _worker_redis_connection_params() -> dict[str, any]:
    """
    Параметры подключения Redis для воркеров
    """
    return {
        "encoding": "utf-8",
        "decode_responses": True,
        "socket_timeout": settings.redis.REDIS_TIMEOUT,
        "socket_connect_timeout": settings.redis.REDIS_TIMEOUT,
        "retry_on_timeout": True,
        "health_check_interval": 30,
        "socket_keepalive": True,
    }

#endregion

#region Redis для статусов задач

@asynccontextmanager
async def get_task_state_redis_context() -> aioredis.Redis:
    redis_client = aioredis.Redis.from_url(settings.redis.REDIS_URL, **_worker_redis_connection_params())
    try:
        yield redis_client
    finally:
        try:
            close_method = getattr(redis_client, "aclose", None) or getattr(redis_client, "close", None)
            if close_method is None:
                raise AttributeError("Не удалось найти метод закрытия Redis клиента")
            
            maybe_coro = close_method()
            if inspect.isawaitable(maybe_coro):
                await maybe_coro
        
        except Exception as err:
            logger.error(f"Dramatiq | Ошибка закрытия Redis клиента: {err}", exc_info = True)

#endregion

#region Redis брокера Dramatiq

@contextmanager
def get_dramatiq_sync_redis_context() -> redis.Redis:
    redis_client = redis.Redis.from_url(settings.dramatiq.DRAMATIQ_REDIS_URL, **_worker_redis_connection_params())
    try:
        yield redis_client
    finally:
        try:
            redis_client.close()
        except Exception as err:
            logger.error(f"Dramatiq | Ошибка закрытия Redis клиента: {err}", exc_info = True)

#endregion
