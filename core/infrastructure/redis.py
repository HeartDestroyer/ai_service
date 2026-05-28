# ai_service/core/infrastructure/redis.py - Клиент Redis

#region Импорты и библиотеки

import redis.asyncio as aioredis
import asyncio
from fastapi import HTTPException

from core.configuration.settings import settings
from core.observability.logger import logger

#endregion

class RedisClient:

    def __init__(self):
        self.redis_client: aioredis.Redis | None = None
        self._init_lock = asyncio.Lock()
        self.redis_url = settings.redis.REDIS_URL
        self.redis_max_connections = settings.redis.REDIS_MAX_CONNECTIONS
        self.redis_timeout = settings.redis.REDIS_TIMEOUT
    
    async def init_redis(self) -> None:
        async with self._init_lock:
            if self.redis_client is not None:
                try:
                    await self.redis_client.ping()
                    return
                except Exception:
                    await self.dispose_redis()
            
            pool = aioredis.ConnectionPool.from_url(
                self.redis_url,
                encoding = "utf-8",
                decode_responses = False,
                socket_timeout = self.redis_timeout,
                socket_connect_timeout = self.redis_timeout,
                retry_on_timeout = True,
                max_connections = self.redis_max_connections,
                health_check_interval = 30,
                socket_keepalive = True,
            )

            self.redis_client = aioredis.Redis(connection_pool = pool)
            await self.redis_client.ping()
            logger.launch("Расширение Redis | Redis клиент успешно инициализирован")
    
    async def dispose_redis(self) -> None:
        if self.redis_client is not None:
            await self.redis_client.connection_pool.disconnect()
        self.redis_client = None
    
    def get_client(self) -> aioredis.Redis | None:
        return self.redis_client
    
    async def get_healthy_client(self) -> aioredis.Redis | None:
        if self.redis_client is None:
            await self.init_redis()
            return self.redis_client
        
        try:
            await self.redis_client.ping()
        except Exception:
            await self.dispose_redis()
            await self.init_redis()
        
        return self.redis_client

redis_client = RedisClient()

#region DI и зависимость

async def get_redis() -> aioredis.Redis:
    try:
        return await redis_client.get_healthy_client()
    except Exception as err:
        logger.error(f"Расширение Redis | Критическая ошибка получения клиента: {err}")
        raise HTTPException(status_code = 503, detail = "Критический компонент системы недоступен")

#endregion
