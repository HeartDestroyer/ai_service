# ai_service/infrastructure/pkg/profile_client/http_client.py - HTTP-клиент для клиента ПрофильХаб

#region Библиотеки и импорты

import httpx
import asyncio
from typing import Any
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from core.configuration.settings import settings
from core.observability.logger import logger
from infrastructure.pkg.profile_client.exceptions import ProfileHubClientUnavailableError, ProfileHubRetryableError, raise_for_status
from infrastructure.pkg.profile_client.schemas import CompanyQueryParamsDTO, CompanySource, EmailValidationBatchRequest, EmailValidationSchemasResponse, EmailValidationType, EnrichmentDataByInnSchema, ExportFormat, PaginatedCompaniesResponse, UniversalSearchResponse

#endregion

#region Константы и утилиты

_RETRYABLE_STATUS_CODES = {502, 503, 504}
_RETRYABLE_EXCEPTIONS = (ProfileHubRetryableError, httpx.TimeoutException, httpx.TransportError)
_PROFILE_HUB_RETRY_ATTEMPTS = settings.integration.ATTEMPTS_PROFILEHUB

def _profile_request_before_sleep(retry_state) -> None:
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    logger.warning(f"HTTP-клиент | ПрофильХаб | Повтор запроса | Попытка {retry_state.attempt_number} | Ошибка: {exc}")

#endregion

class ProfileHubClient:

    def __init__(self):
        self._api_key = settings.integration.API_KEY_PROFILEHUB.get_secret_value()
        self._base_url = settings.integration.API_URL_PROFILEHUB.rstrip("/")
        self._timeout = httpx.Timeout(settings.integration.TIMEOUT_PROFILEHUB, connect = settings.integration.CONNECT_TIMEOUT_PROFILEHUB)

        self._client: httpx.AsyncClient | None = None
        self._init_lock = asyncio.Lock()

    #region Управление жизненным циклом

    async def startup(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url = self._base_url, headers = {"X-API-Key": self._api_key}, timeout = self._timeout)
            logger.launch("HTTP-клиент | ПрофильХаб | Клиент успешно инициализирован")

    async def shutdown(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

        logger.launch("HTTP-клиент | ПрофильХаб | Клиент успешно закрыт")

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            async with self._init_lock:
                if self._client is None:
                    await self.startup()
        return self._client

    #endregion

    #region Внутренние HTTP-операции

    async def profile_request(self, method: str, path: str, *, params: dict[str, Any] | None = None, json: Any | None = None) -> Any:
        """
        Выполнение HTTP-запроса с повторными попытками при ошибках
        """
        try:
            return await self._profile_request_with_retry(method, path, params = params, json = json)
        except _RETRYABLE_EXCEPTIONS as err:
            raise ProfileHubClientUnavailableError(f"HTTP-клиент | ПрофильХаб | Недоступен после {_PROFILE_HUB_RETRY_ATTEMPTS} попыток: {err}") from err

    @retry(
        stop = stop_after_attempt(_PROFILE_HUB_RETRY_ATTEMPTS), 
        wait = wait_exponential(multiplier = 1, min = 1, max = 8),
        retry = retry_if_exception_type(_RETRYABLE_EXCEPTIONS), 
        before_sleep = _profile_request_before_sleep, 
        reraise = True,
    )
    async def _profile_request_with_retry(self, method: str, path: str, *, params: dict[str, Any] | None = None, json: Any | None = None) -> Any:
        """
        Выполнение HTTP-запроса с повторными попытками при ошибках\n
            - `method` - метод HTTP-запроса
            - `path` - путь HTTP-запроса
            - `params` - параметры HTTP-запроса
            - `json` - JSON-тело HTTP-запроса
        """
        client = await self.get_client()
        response = await client.request(method, path, params = params, json = json)

        if response.status_code in _RETRYABLE_STATUS_CODES:
            raise ProfileHubRetryableError(f"HTTP-клиент | ПрофильХаб | {method} | {path} | Cтатус {response.status_code}")

        if response.is_success:
            if not response.content:
                return None
            return response.json()

        raise_for_status(response.status_code, response.json() if response.content else response.text)

    @staticmethod
    def _dump_params(**kwargs: Any) -> dict[str, Any]:
        """
        Преобразование словаря параметров в словарь для HTTP-запроса
        """
        return {key: value for key, value in kwargs.items() if value is not None}

    #endregion

    #region HTTP-запросы для обогащения данных

    async def get_enrichment_by_inn(self, inn: str, *, is_sources: bool | None = None, is_extra: bool | None = None, exclude_sources: list[CompanySource] | None = None, include_sources: list[CompanySource] | None = None) -> EnrichmentDataByInnSchema:
        """
        GET /api/v1/enrichment/{inn} — обогащение данных по ИНН\n
            - `inn` - ИНН компании
            - `is_sources` - включить источники данных
            - `is_extra` - включить дополнительные данные
            - `exclude_sources` - исключить источники данных
            - `include_sources` - включить источники данных
        """
        params = self._dump_params(
            is_sources = is_sources,
            is_extra = is_extra,
            exclude_sources = [s.value for s in exclude_sources] if exclude_sources else None,
            include_sources = [s.value for s in include_sources] if include_sources else None,
        )
        data = await self.profile_request("GET", f"/api/v1/enrichment/{inn}", params = params or None)
        return EnrichmentDataByInnSchema.model_validate(data)

    async def filter_companies(self, filters: CompanyQueryParamsDTO, *, export_format: ExportFormat | None = None, include_contacts: bool | None = None) -> PaginatedCompaniesResponse:
        """
        POST /api/v1/enrichment/filters — выборка компаний по фильтрам\n
            - `filters` - фильтры для выборки компаний
            - `export_format` - формат экспорта
            - `include_contacts` - включить контакты
        """
        params = self._dump_params(
            export_format = export_format.value if export_format else None,
            include_contacts = include_contacts,
        )
        body = filters.model_dump(mode = "json", exclude_none = True)
        data = await self.profile_request("POST", "/api/v1/enrichment/filters", params = params or None, json = body)
        return PaginatedCompaniesResponse.model_validate(data)

    async def search_enrichment(self, q: str) -> UniversalSearchResponse:
        """
        POST /api/v1/enrichment/search — универсальный поиск (ИНН, телефон, почта, название, ФИО)\n
            - `q` - поисковый запрос
        """
        data = await self.profile_request("POST", "/api/v1/enrichment/search", params = {"q": q})
        return UniversalSearchResponse.model_validate(data)

    #endregion

    #region Валидация почты

    async def validate_emails_batch(self, emails: list[str], *, validation_type: EmailValidationType = EmailValidationType.reacher) -> list[EmailValidationSchemasResponse]:
        """
        POST /api/v1/email-validate/validate/batch — пакетная проверка почт (1–100)\n
            - `emails` - список почт для проверки
            - `validation_type` - тип валидации
        """
        body = EmailValidationBatchRequest(emails = emails).model_dump()
        params = {"validation_type": validation_type.value}
        data = await self.profile_request("POST", "/api/v1/email-validate/validate/batch", params = params, json = body)
        return [EmailValidationSchemasResponse.model_validate(item) for item in data]

    #endregion

#region Паттерн "Управление жизненным циклом и DI"

profile_client = ProfileHubClient()

def get_profile_client() -> ProfileHubClient:
    return profile_client

#endregion
