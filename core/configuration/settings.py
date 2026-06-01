# ai_service/core/configuration/settings.py - Конфигурация приложения

#region Импорты и библиотеки

import json
from enum import Enum
from functools import lru_cache
from urllib.parse import quote_plus
from typing import Annotated
from pydantic import ConfigDict, Field, SecretStr, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode

#endregion

#region Утилиты

def _to_str_list(value: any) -> list[str]:
    """
    Преобразование значения в список строк
    """
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return []
        
        if candidate.startswith("["):
            try:
                loaded = json.loads(candidate)
            
            except json.JSONDecodeError as err:
                raise ValueError(f"Настройки приложения | Ожидался JSON-массив: {err}") from err
            
            if not isinstance(loaded, list):
                raise ValueError("Настройки приложения | Ожидался JSON-массив строк")
            
            return [str(item).strip() for item in loaded if str(item).strip()]
        return [item.strip() for item in candidate.split(",") if item.strip()]
    
    raise TypeError("Настройки приложения | Ожидалась строка, JSON-массив или список")

#endregion

#region Конфигурация приложения

class Environment(str, Enum):
    DEVELOPMENT = "DEVELOPMENT"
    PRODUCTION = "PRODUCTION"

class BaseConfigSettings(BaseSettings):
    model_config = ConfigDict(env_file = ".env", env_file_encoding = "utf-8", extra = 'ignore')

#endregion

#region Настройки приложения

class BaseSettingsClass(BaseConfigSettings):
    PROJECT_NAME: str = Field("AI Enrichment & Outreach Service", env = "PROJECT_NAME", description = "Название проекта")
    PROJECT_VERSION: str = Field("1.0", env = "PROJECT_VERSION", description = "Версия проекта")
    CONTACT_NAME: str = Field(..., env = "CONTACT_NAME", description = "Разработчик проекта")
    CONTACT_TG: str = Field(..., env = "CONTACT_TG", description = "TG разработчика")
    CONTACT_EMAIL: str = Field(..., env = "CONTACT_EMAIL", description = "Почта разработчика")
    DESCRIPTION: str = Field("ИИ сервис для обогащения B2B профилей и автоматизации писем для аутрича", env = "DESCRIPTION", description = "Описание проекта")
    API_PREFIX: str = Field("/api/v1", env = "API_PREFIX", description = "Префикс API")
    DEBUG: bool = Field(False, env = "DEBUG", description = "Режим отладки")
    ENVIRONMENT: Environment = Field(Environment.PRODUCTION, env = "ENVIRONMENT", description = "Окружение")

#endregion

#region Настройки безопасности

class SecurityConfig(BaseConfigSettings):
    SECRET_KEY: SecretStr = Field(..., env = "SECRET_KEY", description = "Секретный ключ приложения")
    API_KEY: dict[str, SecretStr] = Field(..., env = "API_KEY", description = "API ключи для аутентификации (название: ключ)")
    DOCS_WHITELIST: list[str] = Field(default_factory = lambda: ["/docs", "/redoc"], env = "DOCS_WHITELIST", description = "Список путей документации")
    DOCS_USERNAME: str = Field(..., env = "DOCS_USERNAME", description = "Логин для доступа к документации")
    DOCS_PASSWORD: SecretStr = Field(..., env = "DOCS_PASSWORD", description = "Пароль для доступа к документации")
    TRUSTED_PROXY_IPS: list[str] = Field(default_factory = lambda: ["127.0.0.1", "10.0.0.0/8"], env = "TRUSTED_PROXY_IPS", description = "Список доверенных IP-адресов или подсетей прокси-серверов")

    @field_validator("SECRET_KEY", mode="before")
    @classmethod
    def validate_secret_key(cls, value: any, info: ValidationInfo) -> any:
        if not value or len(str(value)) < 64:
            raise ValueError(f"Настройки безопасности | {info.field_name} должен содержать минимум 64 символа")
        return value

    @field_validator("API_KEY", mode="before")
    @classmethod
    def validate_api_keys(cls, value: any) -> dict[str, SecretStr]:
        if isinstance(value, str):
            value = json.loads(value)
        if not isinstance(value, dict) or not value:
            raise ValueError("Настройки безопасности | API_KEY должен быть непустым словарем")
        parsed: dict[str, SecretStr] = {}
        for key_name, raw_key in value.items():
            if len(str(raw_key)) < 64:
                raise ValueError(f"Настройки безопасности | API ключ {key_name} должен содержать минимум 64 символа")
            parsed[str(key_name)] = SecretStr(str(raw_key))
        return parsed

    @field_validator("DOCS_WHITELIST", "TRUSTED_PROXY_IPS", mode="before")
    @classmethod
    def parse_security_lists(cls, value: any) -> list[str]:
        return _to_str_list(value)

#endregion

#region Настройки сервера

class ServerConfig(BaseConfigSettings):
    SERVER_HOST: str = Field("0.0.0.0", env = "SERVER_HOST", description = "Адрес сервера")
    SERVER_PORT: int = Field(8000, env = "SERVER_PORT", description = "Порт сервера")
    APP_WORKERS_COUNT: int = Field(4, env = "APP_WORKERS_COUNT", ge = 1, description = "Количество рабочих процессов")
    LIMIT_CONCURRENCY: int = Field(100, env = "LIMIT_CONCURRENCY", ge = 1, description = "Количество одновременных запросов")
    TIMEOUT_KEEP_ALIVE: int = Field(5, env = "TIMEOUT_KEEP_ALIVE", ge = 1, description = "Время ожидания keep-alive в секундах")
    STARTUP_TIMEOUT: int = Field(30, env = "STARTUP_TIMEOUT", ge = 1, description = "Таймаут запуска приложения в секундах")
    SHUTDOWN_TIMEOUT: int = Field(15, env = "SHUTDOWN_TIMEOUT", ge = 1, description = "Таймаут остановки приложения в секундах")

#endregion

#region Настройки CORS

class CORSConfig(BaseConfigSettings):
    CORS_ALLOW_CREDENTIALS: bool = Field(True, env = "CORS_ALLOW_CREDENTIALS", description = "Разрешение использования credentials в CORS")
    CORS_ALLOW_METHODS: Annotated[list[str], NoDecode] = Field(default_factory = lambda: ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"], env = "CORS_ALLOW_METHODS")
    CORS_ALLOW_HEADERS: Annotated[list[str], NoDecode] = Field(default_factory = lambda: ["Content-Type", "X-API-Key"], env = "CORS_ALLOW_HEADERS")
    CORS_ALLOW_ORIGINS: Annotated[list[str], NoDecode] = Field(default_factory = list, env = "CORS_ALLOW_ORIGINS")

    @field_validator("CORS_ALLOW_METHODS", "CORS_ALLOW_HEADERS", "CORS_ALLOW_ORIGINS", mode="before")
    @classmethod
    def parse_list_fields(cls, value: any) -> list[str]:
        return _to_str_list(value)

#endregion

#region Настройки логирования

class LoggingConfig(BaseConfigSettings):
    LOG_LEVEL: str = Field("INFO", env = "LOG_LEVEL")
    LOGS_DIR: str = Field("logs", env = "LOGS_DIR")
    LOG_FILE_MAX_BYTES: int = Field(104857600, env = "LOG_FILE_MAX_BYTES", ge = 1, description = "Максимальный размер файла логирования - 100MB")
    LOG_FILE_BACKUP_COUNT: int = Field(5, env = "LOG_FILE_BACKUP_COUNT", ge = 1, description = "Количество резервных копий файлов логирования")
    LOG_AUDIT_BACKUP_DAYS: int = Field(30, env = "LOG_AUDIT_BACKUP_DAYS", ge = 1, description = "Количество дней хранения резервных копий логирования")
    LOG_QUEUE_MAX_SIZE: int = Field(1000, env = "LOG_QUEUE_MAX_SIZE", ge = 100, description = "Максимальное количество сообщений в очереди логирования")

#endregion

#region Настройки базы данных

class DatabaseConfig(BaseConfigSettings):
    DB_HOST: str = Field(..., env = "DB_HOST", description = "Адрес сервера базы данных")
    DB_PORT: int = Field(..., env = "DB_PORT", description = "Порт сервера базы данных")
    POSTGRES_USER: str = Field(..., env = "POSTGRES_USER", description = "Имя пользователя базы данных")
    POSTGRES_PASSWORD: SecretStr = Field(..., env = "POSTGRES_PASSWORD", description = "Пароль пользователя базы данных")
    POSTGRES_DB: str = Field(..., env = "POSTGRES_DB", description = "Имя базы данных")
    DATABASE_URL: str | None = Field(None, env = "DATABASE_URL", description = "URL для подключения к базе данных")
    TYPE_CONNECTION: str = Field("postgresql+asyncpg", env = "TYPE_CONNECTION", description = "Тип соединения к базе данных")
    SQLALCHEMY_ECHO: bool = Field(..., env = "SQLALCHEMY_ECHO", description = "Вывод SQL запросов в консоль")
    DB_CONNECT_TIMEOUT: int = Field(10, env = "DB_CONNECT_TIMEOUT", ge = 1, description = "Таймаут соединения к базе данных")
    DB_POOL_SIZE: int = Field(20, env = "DB_POOL_SIZE", ge = 1, description = "Максимальное количество соединений в пуле")
    DB_MAX_OVERFLOW: int = Field(10, env = "DB_MAX_OVERFLOW", ge = 0, description = "Максимальное количество соединений в пуле сверх основного")
    DB_POOL_TIMEOUT: int = Field(30, env = "DB_POOL_TIMEOUT", ge = 1, description = "Таймаут ожидания соединения в пуле")
    DB_POOL_RECYCLE: int = Field(1800, env = "DB_POOL_RECYCLE", ge = 1, description = "Время жизни соединения в пуле")
    DB_POOL_PRE_PING: bool = Field(True, env = "DB_POOL_PRE_PING", description = "Проверка соединения перед использованием")
    DB_INIT_RETRY_ATTEMPTS: int = Field(5, env = "DB_INIT_RETRY_ATTEMPTS", ge = 1, description = "Количество попыток инициализации соединения")
    MAX_LIMIT: int = Field(100, env = "MAX_LIMIT", ge = 1, description = "Максимальное количество запросов к базе данных")
    DB_WORKERS_COUNT: int = Field(4, env = "DB_WORKERS_COUNT", ge = 1, description = "Количество рабочих процессов для базы данных")
    MAX_CONNECT_DB: int = Field(200, env = "MAX_CONNECT_DB", ge = 1, description = "Максимальное количество одновременных соединений к базе данных")

    @property
    def SQLALCHEMY_ENGINE_OPTIONS(self) -> dict[str, any]:
        return {
            "pool_size": self.DB_POOL_SIZE,
            "max_overflow": self.DB_MAX_OVERFLOW,
            "pool_timeout": self.DB_POOL_TIMEOUT,
            "pool_recycle": self.DB_POOL_RECYCLE,
            "pool_pre_ping": self.DB_POOL_PRE_PING,
        }

    @model_validator(mode="after")
    def assemble_db_connection(self) -> "DatabaseConfig":
        if self.DATABASE_URL:
            return self
        encoded_password = quote_plus(self.POSTGRES_PASSWORD.get_secret_value())
        self.DATABASE_URL = f"{self.TYPE_CONNECTION}://{self.POSTGRES_USER}:{encoded_password}@{self.DB_HOST}:{self.DB_PORT}/{self.POSTGRES_DB}"
        return self

#endregion

#region Настройки Redis

class RedisConfig(BaseConfigSettings):
    REDIS_HOST: str = Field(..., env = "REDIS_HOST", description = "Адрес сервера Redis")
    REDIS_PORT: int = Field(..., env = "REDIS_PORT", description = "Порт сервера Redis")
    REDIS_DB: int = Field(..., env = "REDIS_DB", description = "Имя базы данных Redis")
    REDIS_PASSWORD: SecretStr = Field(..., env = "REDIS_PASSWORD", description = "Пароль пользователя Redis")
    REDIS_URL: str | None = Field(None, env = "REDIS_URL", description = "URL для подключения к Redis")
    REDIS_TIMEOUT: int = Field(15, env = "REDIS_TIMEOUT", ge = 1, description = "Таймаут ожидания соединения в Redis")
    REDIS_MAX_CONNECTIONS: int = Field(100, env = "REDIS_MAX_CONNECTIONS", ge = 1, description = "Максимальное количество соединений в пуле Redis")
    REDIS_INIT_RETRY_ATTEMPTS: int = Field(5, env = "REDIS_INIT_RETRY_ATTEMPTS", ge = 1, description = "Количество попыток инициализации соединения к Redis")

    @model_validator(mode="after")
    def assemble_redis_url(self) -> "RedisConfig":
        if self.REDIS_URL:
            return self
        encoded_password = quote_plus(self.REDIS_PASSWORD.get_secret_value())
        self.REDIS_URL = f"redis://:{encoded_password}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return self

#endregion

#region Настройки Dramatiq

class DramatiqConfig(BaseConfigSettings):
    DRAMATIQ_REDIS_HOST: str = Field(..., env = "DRAMATIQ_REDIS_HOST", description = "Адрес сервера Redis для Dramatiq")
    DRAMATIQ_REDIS_PORT: int = Field(..., env = "DRAMATIQ_REDIS_PORT", description = "Порт сервера Redis для Dramatiq")
    DRAMATIQ_REDIS_PASSWORD: SecretStr = Field(..., env = "DRAMATIQ_REDIS_PASSWORD", description = "Пароль пользователя Redis для Dramatiq")
    DRAMATIQ_REDIS_DB: int = Field(..., env = "DRAMATIQ_REDIS_DB", description = "Имя базы данных Redis для Dramatiq")
    DRAMATIQ_REDIS_URL: str | None = Field(None, env = "DRAMATIQ_REDIS_URL", description = "URL для подключения к Redis для Dramatiq")
    MAX_RETRIES: int = Field(5, env = "DRAMATIQ_MAX_RETRIES", ge = 0, description = "Максимальное количество попыток повторного выполнения задачи")
    MIN_BACKOFF: int = Field(5000, env = "DRAMATIQ_MIN_BACKOFF", ge = 0, description = "Минимальное время ожидания между попытками повторного выполнения задачи")
    MAX_BACKOFF: int = Field(60000, env = "DRAMATIQ_MAX_BACKOFF", ge = 0, description = "Максимальное время ожидания между попытками повторного выполнения задачи")
    DLQ_TTL_DAYS: int = Field(7, env = "DRAMATIQ_DLQ_TTL_DAYS", ge = 1, description = "Время жизни задачи в DLQ")
    RESULTS_KEY_PREFIX: str = Field("dramatiq:results:", env = "DRAMATIQ_RESULTS_PREFIX", description = "Префикс ключа для результатов задач")
    DLQ_KEY_PREFIX: str = Field("dramatiq:dlq:", env = "DRAMATIQ_DLQ_PREFIX", description = "Префикс ключа для задач в DLQ")
    REPORTS_KEY_PREFIX: str = Field("dramatiq:reports:", env = "DRAMATIQ_REPORTS_PREFIX", description = "Префикс ключа для отчетов о выполнении задач")

    @model_validator(mode="after")
    def assemble_dramatiq_redis_url(self) -> "DramatiqConfig":
        if self.DRAMATIQ_REDIS_URL:
            return self
        encoded_password = quote_plus(self.DRAMATIQ_REDIS_PASSWORD.get_secret_value())
        self.DRAMATIQ_REDIS_URL = f"redis://:{encoded_password}@{self.DRAMATIQ_REDIS_HOST}:{self.DRAMATIQ_REDIS_PORT}/{self.DRAMATIQ_REDIS_DB}"
        return self

#endregion

#region Настройки интеграции

class IntegrationConfig(BaseConfigSettings):
    API_KEY_PROFILEHUB: SecretStr = Field(..., env = "API_KEY_PROFILEHUB")
    API_URL_PROFILEHUB: str = Field(..., env = "API_URL_PROFILEHUB")
    ATTEMPTS_PROFILEHUB: int = Field(5, ge = 1, env = "ATTEMPTS_PROFILEHUB", description = "Количество попыток запроса к ПрофильХаб")
    TIMEOUT_PROFILEHUB: int = Field(15, ge = 1, env = "TIMEOUT_PROFILEHUB", description = "Таймаут запроса к ПрофильХаб (сек)")
    CONNECT_TIMEOUT_PROFILEHUB: int = Field(10, ge = 1, env = "CONNECT_TIMEOUT_PROFILEHUB", description = "Таймаут соединения с ПрофильХаб (сек)")

    API_KEY_POLZA: SecretStr = Field(..., env = "API_KEY_POLZA")
    API_URL_POLZA: str = Field(..., env = "API_URL_POLZA")
    ATTEMPTS_POLZA: int = Field(5, ge = 1, env = "ATTEMPTS_POLZA", description = "Количество попыток запроса к Polza.ai")
    TIMEOUT_POLZA: int = Field(120, ge = 1, env = "TIMEOUT_POLZA", description = "Таймаут запроса к Polza.ai (сек)")
    CONNECT_TIMEOUT_POLZA: int = Field(10, ge = 1, env = "CONNECT_TIMEOUT_POLZA", description = "Таймаут соединения с Polza.ai (сек)")

#endregion

class Settings:

    def __init__(self):
        self._configs = {
            "app": BaseSettingsClass(), "security": SecurityConfig(), "server": ServerConfig(), "cors": CORSConfig(), "logging": LoggingConfig(),
            "database": DatabaseConfig(), "redis": RedisConfig(), "dramatiq": DramatiqConfig(), "integration": IntegrationConfig(),
        }
    
    def __getattr__(self, name: str):
        if name not in self._configs:
            raise AttributeError(f"Настройки приложения | Конфигурация {name} не найдена")
        return self._configs[name]

#region DI и зависимость

@lru_cache(maxsize = 1)
def get_settings() -> Settings:
    return Settings()

settings = get_settings()

#endregion
