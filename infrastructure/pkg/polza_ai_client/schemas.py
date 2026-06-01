# ai_service/infrastructure/pkg/polza_ai_client/schemas.py - Схемы API Polza.ai

#region Библиотеки и импорты

from enum import StrEnum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

#endregion

#region Перечисления API Polza.ai

class ModelType(StrEnum):
    chat = "chat"
    image = "image"
    embedding = "embedding"
    video = "video"
    audio = "audio"
    moderation = "moderation"
    stt = "stt"
    tts = "tts"
    document = "document"

class GenerationRequestType(StrEnum):
    chat = "chat"
    image = "image"
    video = "video"
    audio = "audio"

class GenerationStatus(StrEnum):
    completed = "completed"
    failed = "failed"
    pending = "pending"

class CatalogSortBy(StrEnum):
    name = "name"
    price = "price"
    created_at = "createdAt"

class SortOrder(StrEnum):
    asc = "asc"
    desc = "desc"

class HistorySortBy(StrEnum):
    created_at = "createdAt"
    client_cost = "clientCost"

class ChatMessageRole(StrEnum):
    system = "system"
    user = "user"
    assistant = "assistant"
    developer = "developer"
    tool = "tool"

#endregion

#region Генерация текста

class ChatMessageDTO(BaseModel):
    """
    Сообщение диалога (OpenAI-совместимый формат Polza.ai)
    """
    model_config = ConfigDict(extra = "allow")

    role: ChatMessageRole | str
    content: str | list[dict[str, Any]] | None = None
    name: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None

class ChatCompletionRequest(BaseModel):
    """
    POST /v1/chat/completions
    """
    model_config = ConfigDict(extra = "allow")

    model: str = Field(..., description = "ID модели из каталога Polza.ai")
    messages: list[ChatMessageDTO] | None = None
    prompt: str | None = None
    max_tokens: int | None = None
    max_completion_tokens: int | None = None
    temperature: float | None = Field(None, ge = 0, le = 2)
    top_p: float | None = Field(None, ge = 0, le = 1)
    top_k: int | None = None
    frequency_penalty: float | None = Field(None, ge = -2, le = 2)
    presence_penalty: float | None = Field(None, ge = -2, le = 2)
    stop: str | list[str] | None = None
    seed: int | None = None
    stream: bool = False
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict[str, Any] | None = None
    response_format: dict[str, Any] | None = None
    user: str | None = None

class ChatCompletionUsageDTO(BaseModel):
    model_config = ConfigDict(extra = "allow")

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cost_rub: float | None = None
    cost: float | None = None

class ChatCompletionChoiceDTO(BaseModel):
    model_config = ConfigDict(extra = "allow")

    index: int
    message: dict[str, Any]
    finish_reason: str | None = None

class ChatCompletionResponse(BaseModel):
    model_config = ConfigDict(extra = "allow")

    id: str
    object: str | None = None
    created: int | None = None
    model: str
    provider: str | None = None
    choices: list[ChatCompletionChoiceDTO]
    usage: ChatCompletionUsageDTO | None = None

#endregion

#region Список и каталог моделей

class ModelArchitectureDTO(BaseModel):
    model_config = ConfigDict(extra = "allow")

    input_modalities: list[str] = Field(default_factory = list)
    output_modalities: list[str] = Field(default_factory = list)

class ModelPricingDTO(BaseModel):
    model_config = ConfigDict(extra = "allow")

    currency: str | None = None
    prompt_per_million: str | None = None
    completion_per_million: str | None = None

class ModelDTO(BaseModel):
    model_config = ConfigDict(extra = "allow")

    id: str
    name: str
    type: str
    created: int | None = None
    architecture: ModelArchitectureDTO | None = None
    top_provider: dict[str, Any] | None = None
    endpoints: list[str] = Field(default_factory = list)

class ModelsListResponse(BaseModel):
    data: list[ModelDTO]

class CatalogPaginationDTO(BaseModel):
    model_config = ConfigDict(extra = "allow")

    page: int
    limit: int
    total: int
    totalPages: int
    availableProviders: list[str] = Field(default_factory = list)

class ModelsCatalogResponse(BaseModel):
    data: list[ModelDTO]
    meta: CatalogPaginationDTO

class ModelsCatalogQueryDTO(BaseModel):
    """
    Query-параметры GET /v1/models/catalog
    """
    search: str | None = None
    type: ModelType | str | None = None
    page: int = Field(1, ge = 1)
    limit: int = Field(20, ge = 1, le = 100)
    sortBy: CatalogSortBy | str | None = None
    sortOrder: SortOrder | None = None
    contextLengthMin: int | None = None
    contextLengthMax: int | None = None

#endregion

#region История генераций

class GenerationHistoryItemDTO(BaseModel):
    model_config = ConfigDict(extra = "allow")

    id: str
    model: str | None = None
    modelDisplayName: str | None = None
    requestType: str | None = None
    provider: str | None = None
    status: str | None = None
    cost: str | None = None
    usage: dict[str, Any] | None = None
    generationTimeMs: int | None = None
    createdAt: str | None = None

class HistoryPaginationDTO(BaseModel):
    page: int
    limit: int
    total: int
    totalPages: int

class GenerationsHistoryResponse(BaseModel):
    items: list[GenerationHistoryItemDTO]
    meta: HistoryPaginationDTO

class GenerationsHistoryQueryDTO(BaseModel):
    """
    Query-параметры GET /v1/history/generations
    """
    page: int = Field(1, ge = 1)
    limit: int = Field(20, ge = 1, le = 100)
    dateFrom: str | None = None
    dateTo: str | None = None
    requestType: GenerationRequestType | str | None = None
    status: GenerationStatus | str | None = None
    sortBy: HistorySortBy | str | None = Field(default = HistorySortBy.created_at)
    sortOrder: SortOrder | None = Field(default = SortOrder.desc)

class GenerationDetailDTO(BaseModel):
    model_config = ConfigDict(extra = "allow")

    id: str
    organizationId: str | None = None
    apiKeyId: str | None = None
    requestType: str | None = None
    apiType: str | None = None
    responseMode: str | None = None
    status: str | None = None
    finishReason: str | None = None
    finalEndpointSlug: str | None = None
    usage: dict[str, Any] | None = None
    clientCost: str | None = None
    generationTimeMs: int | None = None
    createdAt: str | None = None
    completedAt: str | None = None
    attemptsCount: int | None = None

#endregion
