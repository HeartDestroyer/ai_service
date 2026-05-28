# ai_service/core/initialization/app_initializer.py - Настройка FastAPI приложения

#region Импорты и библиотеки

from tenacity import retry, stop_after_attempt, wait_exponential
import asyncio
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend

from core.configuration.settings import settings
from core.observability.logger import logger
from core.infrastructure.database import init_database, dispose_database
from core.infrastructure.redis import redis_client

#endregion

#region Переменные

db_retry_attempts: int = settings.database.DB_INIT_RETRY_ATTEMPTS
redis_retry_attempts: int = settings.redis.REDIS_INIT_RETRY_ATTEMPTS
db_timeout: int = settings.database.DB_CONNECT_TIMEOUT
redis_timeout: int = settings.redis.REDIS_TIMEOUT

#endregion

def _tenacity_before_sleep(retry_state):
    logger.warning(f"Настройка FastAPI приложения | Перезапуск {retry_state.fn.__name__} | Попытка {retry_state.attempt_number}")

class AppInitializer:
    
    def __init__(self):
        self._init_lock = asyncio.Lock()
        self._initialized = False
        self._cleanup_lock = asyncio.Lock()
        self._cleanup_completed = False

    #region Инициализация всех компонентов

    async def initialize_all(self) -> None:
        async with self._init_lock:
            if self._initialized:
                logger.launch("Настройка FastAPI приложения | Компоненты уже инициализированы | Пропускаем инициализацию")
                return
            
            await self.initialize_database()
            await self.initialize_redis()
            await self.initialize_fastapi_cache()
            self._initialized = True
            logger.launch("Настройка FastAPI приложения | Все компоненты успешно инициализированы")

    @retry(stop = stop_after_attempt(db_retry_attempts), wait = wait_exponential(multiplier = 1, min = 2, max = 10), before_sleep = _tenacity_before_sleep, reraise = True)
    async def initialize_database(self) -> None:
        await asyncio.wait_for(init_database(), timeout = db_timeout)

    @retry(stop = stop_after_attempt(redis_retry_attempts), wait = wait_exponential(multiplier = 1, min = 2, max = 10), before_sleep = _tenacity_before_sleep, reraise = True)
    async def initialize_redis(self) -> None:
        await asyncio.wait_for(redis_client.init_redis(), timeout = redis_timeout)

    @retry(stop = stop_after_attempt(redis_retry_attempts), wait = wait_exponential(multiplier = 1, min = 2, max = 10), before_sleep = _tenacity_before_sleep, reraise = True)
    async def initialize_fastapi_cache(self) -> None:
        redis_connection = redis_client.get_client()
        if not redis_connection:
            raise RuntimeError("Настройка FastAPI приложения | Redis клиент не доступен для кэширования")
        
        backend = RedisBackend(redis_connection)
        FastAPICache.init(backend, prefix = "app_cache")

    #endregion

    #region Инициализация и очистка приложения

    async def cleanup_all(self) -> None:
        async with self._cleanup_lock:
            if self._cleanup_completed:
                return
            
            await self.cleanup_fastapi_cache()
            await asyncio.gather(self.cleanup_database(), self.cleanup_redis(), return_exceptions = True)
            self._cleanup_completed = True

    async def cleanup_database(self) -> None:
        await dispose_database()

    async def cleanup_redis(self) -> None:
        await redis_client.dispose_redis()

    async def cleanup_fastapi_cache(self) -> None:
        try:
            cache_backend = FastAPICache.get_backend()
            if cache_backend:
                await cache_backend.clear()
        
        except Exception as err:
            logger.error(f"Настройка FastAPI приложения | Ошибка при очистке FastAPICache: {err}")

    #endregion
