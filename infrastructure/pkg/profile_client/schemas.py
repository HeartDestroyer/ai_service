# ai_service/infrastructure/pkg/profile_client/schemas.py - Схемы API ПрофильХаб

#region Библиотеки и импорты

from datetime import datetime
from enum import StrEnum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

#endregion

#region Перечисления ПрофильХаб

class CompanySource(StrEnum):
    kontur = "kontur"
    sbis = "sbis"
    nalogovaya = "nalogovaya"
    manual_contacts = "manual_contacts"
    kontur_old = "kontur_old"
    nalogovaya_old = "nalogovaya_old"
    eruz = "eruz"
    nostroy = "nostroy"
    nopriz = "nopriz"
    zakupki = "zakupki"
    rnp = "rnp"
    gosbase = "gosbase"
    checko = "checko"
    crm_expertcenter = "crm_expertcenter"

class CompanyStatus(StrEnum):
    active = "active"
    liquidating = "liquidating"
    liquidated = "liquidated"
    bankrupt = "bankrupt"
    reorganizing = "reorganizing"
    unknown = "unknown"

class ExportFormat(StrEnum):
    excel = "excel"
    csv = "csv"

class EmailValidationType(StrEnum):
    verifier = "verifier"
    reacher = "reacher"

class EmailValidationStatus(StrEnum):
    VALID = "VALID"
    PROBABLY_VALID = "PROBABLY_VALID"
    DISPOSABLE = "DISPOSABLE"
    INVALID_FORMAT = "INVALID_FORMAT"
    INVALID_DOMAIN = "INVALID_DOMAIN"
    INVALID_MX = "INVALID_MX"
    UNKNOWN = "UNKNOWN"
    NO_MX_RECORDS = "NO_MX_RECORDS"
    MISSING_EMAIL = "MISSING_EMAIL"

#endregion

#region Запросы ПрофильХаб

class CompanyQueryParamsDTO(BaseModel):
    """
    Параметры запроса для выборки компаний
    """
    model_config = ConfigDict(extra = "forbid")

    query: str | None = Field(..., description = "Поисковый запрос")
    okved_codes: list[str] | None = Field(..., description = "Коды оквэд")
    search_in_additional_okveds: bool = Field(False, description = "Поиск в дополнительных оквэдах")
    region_codes: list[str] | None = Field(..., description = "Коды регионов")
    has_phones: bool | None = Field(..., description = "Имеются телефоны")
    has_emails: bool | None = Field(..., description = "Имеются почты")
    sources: list[CompanySource] | None = Field(..., description = "Источники данных")
    status: list[CompanyStatus] | None = Field(..., description = "Статусы компаний")
    created_after: datetime | str | None = Field(..., description = "Дата создания после")
    updated_after: datetime | str | None = Field(..., description = "Дата обновления после")
    offset: int = Field(default = 0, ge = 0, description = "Сдвиг")
    limit: int = Field(default = 100, ge = 1, le = 10000, description = "Количество компаний на странице")
    cursor: str | None = Field(None, description = "Курсор")
    sort_by: str | None = Field("id", description = "Поле для сортировки")
    sort_order: str | None = Field("desc", description = "Порядок сортировки")
    export_columns: dict[str, Any] | None = None

class EmailValidationBatchRequest(BaseModel):
    """
    Запрос для пакетной валидации почт
    """
    model_config = ConfigDict(extra = "forbid")

    emails: list[str] = Field(..., min_length = 1, max_length = 100, description = "Список почт для проверки")

#endregion

#region Ответы ПрофильХаб

class EnrichmentDataByInnSchema(BaseModel):
    """
    Обогащение данных по ИНН
    """
    model_config = ConfigDict(extra = "allow")

    inn_company: str
    name_company: str | None = None
    status: str | None = None
    status_at: str | None = None
    status_description: str | None = None
    inn_leader: str | None = None
    name_leader: str | None = None
    address_company: str | None = None
    okved: str | None = None
    okveds: list[Any] | None = None
    phones: list[str] | None = None
    emails: list[str] | None = None
    sources: list[Any] | None = None
    created_at: str | None = None
    updated_at: str | None = None
    employees_count: int | None = None
    revenue: str | None = None
    profit: str | None = None
    balance: str | None = None
    arbitration: str | None = None
    licenses: list[str] | None = None
    purchases: list[Any] | None = None
    edo_identifier: list[str] | None = None
    extra_data: dict[str, Any] | None = None

class CompanySearchFilterSchema(BaseModel):
    """
    Фильтр для поиска компаний
    """
    model_config = ConfigDict(extra = "allow")

    inn_company: str | None = None
    name_company: str | None = None

class PaginatedCompaniesResponse(BaseModel):
    """
    Ответ для выборки компаний
    """
    model_config = ConfigDict(extra = "allow")

    items: list[CompanySearchFilterSchema]
    total: int
    offset: int
    limit: int
    has_next: bool
    has_prev: bool

class UniversalSearchItemSchema(BaseModel):
    """
    Элемент универсального поиска
    """
    model_config = ConfigDict(extra = "allow")

    inn_company: str | None = None
    name_company: str | None = None
    inn_leader: str | None = None
    name_leader: str | None = None

class UniversalSearchResponse(BaseModel):
    """
    Ответ для универсального поиска
    """
    model_config = ConfigDict(extra = "allow")

    search_type: str | None = None
    query: str
    items: list[UniversalSearchItemSchema]
    total: int

class EmailValidationSchemasResponse(BaseModel):
    """
    Ответ для валидации почт
    """
    model_config = ConfigDict(extra = "allow")

    email: str
    status: EmailValidationStatus
    validations: dict[str, Any] | None = None
    aliasOf: str | None = None
    original_data: dict[str, Any] | None = None

#endregion
