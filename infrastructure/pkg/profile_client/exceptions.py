# ai_service/infrastructure/pkg/profile_client/exceptions.py - Исключения для клиента ПрофильХаб

#region Библиотеки и импорты

from typing import Any
from fastapi import HTTPException

#endregion

class ProfileHubClientError(HTTPException):
    def __init__(self, status_code: int, detail: str, *, headers: dict[str, str] | None = None):
        super().__init__(status_code = status_code, detail = detail, headers = headers)

class ProfileHubClientAuthenticationError(ProfileHubClientError):
    def __init__(self, detail: str = "ПрофильХаб: ошибка аутентификации"):
        super().__init__(status_code = 401, detail = detail)

class ProfileHubClientAuthorizationError(ProfileHubClientError):
    def __init__(self, detail: str = "ПрофильХаб: доступ запрещён"):
        super().__init__(status_code = 403, detail = detail)

class ProfileHubClientNotFoundError(ProfileHubClientError):
    def __init__(self, detail: str = "ПрофильХаб: ресурс не найден"):
        super().__init__(status_code = 404, detail = detail)

class ProfileHubClientBadRequestError(ProfileHubClientError):
    def __init__(self, detail: str = "ПрофильХаб: некорректный запрос"):
        super().__init__(status_code = 400, detail = detail)

class ProfileHubClientUnavailableError(ProfileHubClientError):
    def __init__(self, detail: str = "ПрофильХаб: сервис недоступен"):
        super().__init__(status_code = 503, detail = detail)

class ProfileHubRetryableError(Exception):
    """Временная ошибка ПрофильХаб (сеть, 502/503/504) — повтор запроса"""

def raise_for_status(status_code: int, detail: Any) -> None:
    """
    Вызов исключения в зависимости от статуса HTTP-ответа
    """
    message = _format_detail(detail)

    if status_code == 401:
        raise ProfileHubClientAuthenticationError(message)
    if status_code == 403:
        raise ProfileHubClientAuthorizationError(message)
    if status_code == 404:
        raise ProfileHubClientNotFoundError(message)
    if status_code in (400, 422):
        raise ProfileHubClientBadRequestError(message)
    if status_code >= 500:
        raise ProfileHubClientUnavailableError(message)

    raise ProfileHubClientError(status_code = status_code, detail = message)

def _format_detail(detail: Any) -> str:
    """
    Форматирование деталей ошибки
    """
    if detail is None: return "Неизвестная ошибка ПрофильХаб"
    if isinstance(detail, str): return detail
    if isinstance(detail, dict):
        if "detail" in detail:
            return _format_detail(detail["detail"])
        return str(detail)
    if isinstance(detail, list):
        return "; ".join(_format_detail(item) for item in detail)
    return str(detail)
