# ai_service/infrastructure/pkg/polza_ai_client/exceptions.py - Исключения для клиента Polza.ai

#region Библиотеки и импорты

from typing import Any
from fastapi import HTTPException

#endregion

class PolzaClientError(HTTPException):
    def __init__(self, status_code: int, detail: str, *, headers: dict[str, str] | None = None):
        super().__init__(status_code = status_code, detail = detail, headers = headers)

class PolzaClientAuthenticationError(PolzaClientError):
    def __init__(self, detail: str = "Polza.ai: ошибка аутентификации"):
        super().__init__(status_code = 401, detail = detail)

class PolzaClientPaymentRequiredError(PolzaClientError):
    def __init__(self, detail: str = "Polza.ai: недостаточно средств"):
        super().__init__(status_code = 402, detail = detail)

class PolzaClientAuthorizationError(PolzaClientError):
    def __init__(self, detail: str = "Polza.ai: доступ запрещён"):
        super().__init__(status_code = 403, detail = detail)

class PolzaClientNotFoundError(PolzaClientError):
    def __init__(self, detail: str = "Polza.ai: ресурс не найден"):
        super().__init__(status_code = 404, detail = detail)

class PolzaClientBadRequestError(PolzaClientError):
    def __init__(self, detail: str = "Polza.ai: некорректный запрос"):
        super().__init__(status_code = 400, detail = detail)

class PolzaClientRateLimitError(PolzaClientError):
    def __init__(self, detail: str = "Polza.ai: превышен лимит запросов"):
        super().__init__(status_code = 429, detail = detail)

class PolzaClientUnavailableError(PolzaClientError):
    def __init__(self, detail: str = "Polza.ai: сервис недоступен"):
        super().__init__(status_code = 503, detail = detail)

class PolzaRetryableError(Exception):
    """Временная ошибка Polza.ai (сеть, 408/502/503/504) — повтор запроса"""

def raise_for_status(status_code: int, detail: Any) -> None:
    """
    Вызов исключения в зависимости от статуса HTTP-ответа
    """
    message = _format_detail(detail)

    if status_code == 401:
        raise PolzaClientAuthenticationError(message)
    if status_code == 402:
        raise PolzaClientPaymentRequiredError(message)
    if status_code == 403:
        raise PolzaClientAuthorizationError(message)
    if status_code == 404:
        raise PolzaClientNotFoundError(message)
    if status_code == 429:
        raise PolzaClientRateLimitError(message)
    if status_code in (400, 422):
        raise PolzaClientBadRequestError(message)
    if status_code >= 500:
        raise PolzaClientUnavailableError(message)

    raise PolzaClientError(status_code = status_code, detail = message)

def _format_detail(detail: Any) -> str:
    """
    Форматирование деталей ошибки (в формат Polza: {"error": {"code", "message"}})
    """
    if detail is None:
        return "Неизвестная ошибка Polza.ai"
    if isinstance(detail, str):
        return detail
    if isinstance(detail, dict):
        error_block = detail.get("error")
        if isinstance(error_block, dict):
            code = error_block.get("code")
            message = error_block.get("message")
            if message:
                return f"{code}: {message}" if code else str(message)
        if "detail" in detail:
            return _format_detail(detail["detail"])
        if "message" in detail:
            return str(detail["message"])
        return str(detail)
    if isinstance(detail, list):
        return "; ".join(_format_detail(item) for item in detail)
    return str(detail)
