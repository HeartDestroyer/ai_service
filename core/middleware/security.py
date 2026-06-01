# ai_service/core/middleware/auth.py - Сервисы безопасности

#region Импорты и библиотеки

import ipaddress
import secrets
from typing import Callable
from fastapi import Depends, HTTPException, Request, Security
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.security.api_key import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware

from core.configuration.settings import settings
from core.infrastructure.redis import redis_client
from core.observability.logger import logger

#endregion

#region Переменные

api_key_header = APIKeyHeader(name = "X-API-Key", auto_error = False)
basic_auth_scheme = HTTPBasic()

#endregion

#region Определение IP клиента

TRUSTED_NETWORKS = [ipaddress.ip_network(cidr.strip()) for cidr in settings.security.TRUSTED_PROXY_IPS]

def resolve_client_ip(request: Request) -> str:
    """
    Единая точка определения реального IP клиента с защитой от спуфинга
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    forwarded_for = request.headers.get("X-Forwarded-For")

    if forwarded_for:
        try:
            client_ip_obj = ipaddress.ip_address(client_ip)
            if any(client_ip_obj in net for net in TRUSTED_NETWORKS):
                return forwarded_for.split(",")[0].strip()
            else:
                logger.warning(f"Сервис безопасности | Игнорируем X-Forwarded-For от недоверенного узла: {client_ip}")
        except ValueError:
            pass

    # Резервный вариант: проверяем валидность прямого IP
    try:
        ipaddress.ip_address(client_ip)
        return client_ip
    except ValueError:
        logger.warning(f"Сервис безопасности | Некорректный IP: {client_ip}")
        return "127.0.0.1"

#endregion

#region Сервисы безопасности

class ApiKeyValidator:
    """
    Сервис для проверки и валидации API ключей
    """

    def get_matched_names(self, api_key_value: str | None) -> list[str]:
        """
        Получение списка ключей, соответствующих предоставленному API ключу
        """
        if not api_key_value:
            raise HTTPException(status_code = 403, detail = "Доступ запрещен: не предоставлен API ключ")
        matched_names = [name for name, key in settings.security.API_KEY.items() if secrets.compare_digest(api_key_value, key.get_secret_value())]

        if not matched_names:
            raise HTTPException(status_code = 403, detail = "Доступ запрещен: некорректный API ключ")
        return matched_names

    def ensure_valid_or_forbidden(self, api_key_value: str | None) -> bool:
        """
        Проверка, является ли предоставленный API ключ действительным
        """
        if not api_key_value:
            return False

        is_valid = any(secrets.compare_digest(api_key_value, key.get_secret_value()) for key in settings.security.API_KEY.values())
        if not is_valid:
            raise HTTPException(status_code = 403, detail = "Доступ запрещен: некорректный API ключ")
        return True

class AnonymousRateLimiter:
    """
    Сервис для принудительного ограничения нагрузки для анонимных клиентов
    """

    def __init__(self, limit: int = 10, window_seconds: int = 60 * 60, redis_key_prefix: str = "limit:anonymous:"):
        self.limit = limit
        self.window_seconds = window_seconds
        self.redis_key_prefix = redis_key_prefix

    async def enforce(self, request: Request) -> None:
        """
        Принудительное ограничение нагрузки для анонимных клиентов
        """
        if request.method.upper() == "OPTIONS":
            return

        api_key = request.headers.get("X-API-Key")
        if api_key and api_key_validator.ensure_valid_or_forbidden(api_key):
            return

        client_ip = resolve_client_ip(request)
        redis = await redis_client.get_healthy_client()
        if redis is None:
            raise HTTPException(status_code = 503, detail = "Критический компонент Redis недоступен")

        key = f"{self.redis_key_prefix}{client_ip}"
        requests_count = await redis.incr(key)
        if requests_count == 1:
            await redis.expire(key, self.window_seconds)

        if requests_count > self.limit:
            raise HTTPException(status_code = 429, detail = "Доступ запрещен: превышен лимит запросов без API ключа")

class AnonymousRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware для принудительного ограничения нагрузки для анонимных клиентов
    """
    
    async def dispatch(self, request: Request, call_next):
        """
        Обработка запроса с учетом ограничения нагрузки для анонимных клиентов
        """
        try:
            await enforce_anonymous_rate_limit(request)
        
        except HTTPException as err:
            return JSONResponse(status_code = err.status_code, content = {"detail": err.detail})
        return await call_next(request)

api_key_validator = ApiKeyValidator()
anonymous_rate_limiter = AnonymousRateLimiter()

#endregion

#region Функции безопасности

async def get_hashed_api_key(api_key_header_value: str = Security(api_key_header)) -> list[str]:
    """
    Получение списка ключей, соответствующих предоставленному API ключу
    """
    return api_key_validator.get_matched_names(api_key_header_value)

def create_api_key_checker(allowed_keys: list[str]) -> Callable[[list[str]], list[str]]:
    """
    Создание функции проверки API ключа
    """
    async def api_key_checker(api_key_names: list[str] = Depends(get_hashed_api_key)) -> list[str]:
        if not any(name in allowed_keys for name in api_key_names):
            raise HTTPException(status_code = 403, detail = "Доступ к этому ресурсу запрещен для вашего API-ключа")
        return api_key_names

    return api_key_checker

async def protected_docs_dependency_basic_auth(credentials: HTTPBasicCredentials = Security(basic_auth_scheme)) -> str:
    """
    Проверка учетных данных для доступа к документации
    """
    correct_username = secrets.compare_digest(credentials.username, settings.security.DOCS_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, settings.security.DOCS_PASSWORD.get_secret_value())

    if not (correct_username and correct_password):
        raise HTTPException(status_code = 401, detail = "Неверные учетные данные", headers = {"WWW-Authenticate": "Basic"})
    return credentials.username

async def enforce_anonymous_rate_limit(request: Request) -> None:
    """
    Принудительное ограничение нагрузки для анонимных клиентов
    """
    await anonymous_rate_limiter.enforce(request)

#endregion
