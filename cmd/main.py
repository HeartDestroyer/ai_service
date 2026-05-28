# ai_service/cmd/main.py - Точка входа в приложение

#region Импорты и библиотеки

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from slowapi.middleware import SlowAPIMiddleware
import uvicorn, asyncio
from prometheus_fastapi_instrumentator import Instrumentator

from core.initialization.app_initializer import AppInitializer
from core.configuration.settings import settings, Environment
from core.observability.logger import logger, logger_instance
from core.middleware.limiter import get_limiter
from core.middleware.headers import HeadersMiddleware
from core.middleware.security import protected_docs_dependency_basic_auth, AnonymousRateLimitMiddleware

#endregion

#region Управление жизненным циклом приложения

async def lifespan(app: FastAPI):
    """
    Управление жизненным циклом приложения
        - _startup_events - Асинхронная инициализация компонентов приложения
        - _shutdown_events - Отказоустойчивое закрытие приложения при завершении работы
    """
    try:
        await _startup_events(app)
        yield
    
    except Exception as err:
        logger.error(f"Главный модуль | Ошибка жизненного цикла | При запуске приложения: {err}")
        raise
    finally:
        await _shutdown_events(app)

async def _startup_events(app: FastAPI):
    """
    Асинхронная инициализация компонентов приложения
    """
    app.state.initializer = AppInitializer()
    logger.launch("Главный модуль | Запуск приложения...")

    # Быстрый сбой при таймауте инициализации критических компонентов
    try:
        await asyncio.wait_for(app.state.initializer.initialize_all(), timeout = settings.server.STARTUP_TIMEOUT)
    
    except (asyncio.TimeoutError, RuntimeError):
        raise RuntimeError(f"Главный модуль | Критическая ошибка | Инициализация не завершена в установленное время: {settings.server.STARTUP_TIMEOUT} секунд")

    logger.launch("Главный модуль | Приложение запущено")

async def _shutdown_events(app: FastAPI):
    """
    Отказоустойчивое закрытие приложения при завершении работы
    """

    # Проверяем, был ли инициализатор вообще создан
    if not hasattr(app, 'state') or not hasattr(app.state, 'initializer'):
        logger_instance.shutdown()
        return
    
    logger.launch("Главный модуль | Закрытие приложения...")

    # Очистка основных ресурсов
    shutdown_tasks = [app.state.initializer.cleanup_all()]

    # Запускаем все задачи одновременно и ждем их завершения
    results = await asyncio.gather(*shutdown_tasks, return_exceptions = True)
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Главный модуль | Ошибка жизненного цикла | При завершении работы: {result}")

    # Закрытие логгера
    logger_instance.shutdown()

#endregion

#region Создание экземпляра FastAPI

def create_application() -> FastAPI:
    app = FastAPI(
        title = settings.app.PROJECT_NAME,
        version = settings.app.PROJECT_VERSION,
        contact = {"name": settings.app.CONTACT_NAME, "url": settings.app.CONTACT_TG},
        debug = settings.app.DEBUG,
        lifespan = lifespan,
        docs_url = None,                    # Защищенная документация
        redoc_url = None,                   # Защищенная документация
        openapi_url = "/docs/openapi.json"  # Защищенная документация схемы
    )

    configure_docs(app)
    configure_metrics(app)
    configure_limiter(app)
    configure_cors(app)
    register_middlewares(app)
    register_routers(app)
    return app

#endregion

#region Регистрация и настройка компонентов приложения

def configure_docs(app: FastAPI) -> None:
    """
    Настройка документации
    """
    
    @app.get(app.openapi_url, include_in_schema = False)
    async def protected_openapi(_: str = Depends(protected_docs_dependency_basic_auth)):
        return app.openapi()

    @app.get("/docs", include_in_schema = False)
    async def protected_swagger_ui_html(_: str = Depends(protected_docs_dependency_basic_auth)):
        return get_swagger_ui_html(openapi_url = app.openapi_url, title = app.title + " - Swagger UI", swagger_ui_parameters = {"docExpansion": "none"})

    @app.get("/redoc", include_in_schema = False)
    async def protected_redoc_html(_: str = Depends(protected_docs_dependency_basic_auth)):
        return get_redoc_html(openapi_url = app.openapi_url, title = app.title + " - ReDoc")

def configure_metrics(app: FastAPI) -> None:
    """
    Настройка метрик\n
    `should_group_status_codes` = `False` - Не группировать статусы кодов HTTP
    """
    Instrumentator(should_group_status_codes = False).instrument(app).expose(app, include_in_schema = False)

def configure_limiter(app: FastAPI) -> None:
    app.state.limiter = get_limiter()

def configure_cors(app: FastAPI) -> None:
    """
    Настройка CORS
    """
    if settings.cors.CORS_ALLOW_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins = [str(url) for url in settings.cors.CORS_ALLOW_ORIGINS],
            allow_credentials = settings.cors.CORS_ALLOW_CREDENTIALS,
            allow_methods = settings.cors.CORS_ALLOW_METHODS,
            allow_headers = settings.cors.CORS_ALLOW_HEADERS,
        )

def register_middlewares(app: FastAPI) -> None:
    """
    Настройка middleware для приложения\n
        - Добавление AnonymousRateLimitMiddleware (Ограничение количества запросов от анонимных пользователей)
        - Добавление HeadersMiddleware (Обработка заголовков запросов)
        - Добавление SlowAPIMiddleware (Ограничение количества запросов от одного IP)
    """
    app.add_middleware(AnonymousRateLimitMiddleware)
    app.add_middleware(HeadersMiddleware)
    app.add_middleware(SlowAPIMiddleware)

def register_routers(app: FastAPI) -> None:
    """
    Регистрация маршрутов\n
    """

#endregion

#region Запуск приложения

if __name__ == "__main__":
    uvicorn.run(
        "cmd.main:create_application",
        host = settings.server.SERVER_HOST,
        port = settings.server.SERVER_PORT,
        reload = settings.app.ENVIRONMENT == Environment.DEVELOPMENT,
        log_level = settings.logging.LOG_LEVEL.lower(),
        workers = settings.server.APP_WORKERS_COUNT,
        loop = "uvloop",
        limit_concurrency = settings.server.LIMIT_CONCURRENCY,
        timeout_keep_alive = settings.server.TIMEOUT_KEEP_ALIVE,
        factory = True
    )

#endregion
