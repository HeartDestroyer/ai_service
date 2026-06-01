# ai_service/core/middleware/limiter.py - Клиент лимитера

#region Импорты и библиотеки

from hashlib import sha256
from fastapi import Request
from slowapi import Limiter

from core.configuration.settings import settings
from core.middleware.security import resolve_client_ip

#endregion

class RateLimiterClient:
    
    def __init__(self):
        self._limiter = Limiter(key_func = self.key_func, storage_uri = settings.redis.REDIS_URL)

    def key_func(self, request: Request) -> str:
        """
        Формирует уникальный ключ для лимитера
        """
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return sha256(api_key.encode("utf-8")).hexdigest().lower()

        return resolve_client_ip(request)

    def get_limiter(self) -> Limiter:
        return self._limiter

limiter_client = RateLimiterClient()
limiter = limiter_client.get_limiter()

#region DI и зависимость

def get_limiter() -> Limiter:
    return limiter_client.get_limiter()

#endregion
