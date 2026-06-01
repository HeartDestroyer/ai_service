# ai_service/infrastructure/pkg/polza_ai_client/http_client.py - HTTP-клиент для Polza.ai

#region Библиотеки и импорты

import httpx
import asyncio
from typing import Any
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from core.configuration.settings import settings
from core.observability.logger import logger
from infrastructure.pkg.polza_ai_client.exceptions import PolzaClientBadRequestError, PolzaClientUnavailableError, PolzaRetryableError, raise_for_status
from infrastructure.pkg.polza_ai_client.schemas import ChatCompletionRequest, ChatCompletionResponse, GenerationDetailDTO, GenerationsHistoryQueryDTO, GenerationsHistoryResponse, ModelType, ModelsCatalogQueryDTO, ModelsCatalogResponse, ModelsListResponse

#endregion

#region Константы и утилиты

_RETRYABLE_STATUS_CODES = {408, 502, 503, 504}
_RETRYABLE_EXCEPTIONS = (PolzaRetryableError, httpx.TimeoutException, httpx.TransportError)
_POLZA_RETRY_ATTEMPTS = settings.integration.ATTEMPTS_POLZA

def _polza_request_before_sleep(retry_state) -> None:
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    logger.warning(f"HTTP-клиент | Polza.ai | Повтор запроса | Попытка {retry_state.attempt_number} | Ошибка: {exc}")

#endregion

class PolzaClient:
    """
    HTTP-клиент Polza.ai (OpenAI-совместимый API)
    """

    def __init__(self):
        self._api_key = settings.integration.API_KEY_POLZA.get_secret_value()
        self._base_url = settings.integration.API_URL_POLZA.rstrip("/")
        self._timeout = httpx.Timeout(settings.integration.TIMEOUT_POLZA, connect = settings.integration.CONNECT_TIMEOUT_POLZA)

        self._client: httpx.AsyncClient | None = None
        self._init_lock = asyncio.Lock()

    #region Управление жизненным циклом

    async def startup(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url = self._base_url, headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}, timeout = self._timeout)
            logger.launch("HTTP-клиент | Polza.ai | Клиент успешно инициализирован")

    async def shutdown(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        logger.launch("HTTP-клиент | Polza.ai | Клиент успешно закрыт")

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            async with self._init_lock:
                if self._client is None:
                    await self.startup()
        return self._client

    #endregion

    #region Внутренние HTTP-операции

    async def polza_request(self, method: str, path: str, *, params: dict[str, Any] | None = None, json: Any | None = None) -> Any:
        """
        Выполнение HTTP-запроса с повторными попытками при временных ошибках
        """
        try:
            return await self._polza_request_with_retry(method, path, params = params, json = json)
        except _RETRYABLE_EXCEPTIONS as err:
            raise PolzaClientUnavailableError(f"HTTP-клиент | Polza.ai | Недоступен после {_POLZA_RETRY_ATTEMPTS} попыток: {err}") from err

    @retry(
        stop = stop_after_attempt(_POLZA_RETRY_ATTEMPTS),
        wait = wait_exponential(multiplier = 1, min = 1, max = 8),
        retry = retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
        before_sleep = _polza_request_before_sleep,
        reraise = True,
    )
    async def _polza_request_with_retry(self, method: str, path: str, *, params: dict[str, Any] | None = None, json: Any | None = None) -> Any:
        client = await self.get_client()
        response = await client.request(method, path, params = params, json = json)

        if response.status_code in _RETRYABLE_STATUS_CODES:
            raise PolzaRetryableError(f"HTTP-клиент | Polza.ai | {method} | {path} | Статус {response.status_code}")

        if response.is_success:
            if not response.content:
                return None
            return response.json()

        raise_for_status(response.status_code, response.json() if response.content else response.text)

    @staticmethod
    def _dump_params(**kwargs: Any) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in kwargs.items():
            if value is None:
                continue
            if hasattr(value, "value"):
                result[key] = value.value
            else:
                result[key] = value
        return result

    #endregion

    #region Генерация текста

    async def chat_completions(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """
        POST /v1/chat/completions — генерация текста (диалог, tool calling, JSON mode)
        """
        if request.stream:
            raise PolzaClientBadRequestError("Стриминг не поддерживается этим HTTP-клиентом")

        body = request.model_dump(mode = "json", exclude_none = True)
        data = await self.polza_request("POST", "/v1/chat/completions", json = body)
        return ChatCompletionResponse.model_validate(data)

    #endregion

    #region Список и каталог моделей

    async def list_models(self, *, model_type: ModelType | str | None = None, include_providers: bool | None = None) -> ModelsListResponse:
        """
        GET /v1/models — список доступных моделей
        """
        params = self._dump_params(type = model_type, include_providers = include_providers)
        data = await self.polza_request("GET", "/v1/models", params = params or None)
        return ModelsListResponse.model_validate(data)

    async def get_models_catalog(self, query: ModelsCatalogQueryDTO | None = None) -> ModelsCatalogResponse:
        """
        GET /v1/models/catalog — каталог моделей с фильтрацией и пагинацией
        """
        params = self._dump_params(**(query.model_dump(exclude_none = True) if query else {}))
        data = await self.polza_request("GET", "/v1/models/catalog", params = params or None)
        return ModelsCatalogResponse.model_validate(data)

    #endregion

    #region История генераций

    async def list_generations_history(self, query: GenerationsHistoryQueryDTO | None = None) -> GenerationsHistoryResponse:
        """
        GET /v1/history/generations — история генераций с фильтрацией
        """
        params = self._dump_params(**(query.model_dump(exclude_none = True) if query else {}))
        data = await self.polza_request("GET", "/v1/history/generations", params = params or None)
        return GenerationsHistoryResponse.model_validate(data)

    async def get_generation_details(self, generation_id: str) -> GenerationDetailDTO:
        """
        GET /v1/history/generations/{id} — детали генерации
        """
        data = await self.polza_request("GET", f"/v1/history/generations/{generation_id}")
        return GenerationDetailDTO.model_validate(data)

    #endregion

#region Паттерн "Управление жизненным циклом и DI"

polza_client = PolzaClient()

def get_polza_client() -> PolzaClient:
    return polza_client

#endregion
