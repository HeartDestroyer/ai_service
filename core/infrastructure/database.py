# ai_service/core/infrastructure/database.py - Клиент базы данных

#region Импорты и библиотеки

from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine
from sqlalchemy.orm import sessionmaker
from typing import AsyncGenerator
import asyncio

from core.configuration.settings import settings
from core.observability.logger import logger

#endregion

#region Переменные

engine: AsyncEngine | None = None
AsyncSessionFactory: sessionmaker | None = None

#endregion

#region Клиент базы данных

class DatabaseClient:

    def __init__(self):
        self.engine: AsyncEngine | None = None
        self.session_factory: sessionmaker | None = None
        self._init_lock = asyncio.Lock()
    
    async def init_database(self) -> None:
        if self.session_factory is not None:
            return
        
        async with self._init_lock:
            if self.session_factory is not None:
                return

            self.engine = create_async_engine(
                settings.database.DATABASE_URL, 
                echo = settings.database.SQLALCHEMY_ECHO, 
                connect_args = {"timeout": settings.database.DB_CONNECT_TIMEOUT}, 
                **settings.database.SQLALCHEMY_ENGINE_OPTIONS
            )

            SQLAlchemyInstrumentor().instrument(engine = self.engine.sync_engine)
            self.session_factory = sessionmaker(engine = self.engine, class_ = AsyncSession, expire_on_commit = False, autoflush = False)
            self._sync_legacy_globals()

    def is_initialized(self) -> bool:
        return self.session_factory is not None
    
    async def dispose_database(self) -> None:
        if self.engine:
            await self.engine.dispose()
        
        self.engine = None
        self.session_factory = None
        self._sync_legacy_globals()
    
    async def get_db(self) -> AsyncGenerator[AsyncSession, None]:
        if not self.is_initialized() or self.session_factory is None:
            logger.launch("Расширение БД | Cессия базы данных не инициализирована")
            raise RuntimeError("Расширение БД | Ошибка жизненного цикла | Сессия базы данных не была инициализирована")
        
        async with self.session_factory() as session:
            yield session
    
    def get_session_factory(self) -> sessionmaker:
        if not self.is_initialized() or self.session_factory is None:
            raise RuntimeError("Расширение БД | Ошибка жизненного цикла | Фабрика сессий базы данных не была инициализирована")
        return self.session_factory
    
    def _sync_legacy_globals(self) -> None:
        global engine, AsyncSessionFactory
        engine = self.engine
        AsyncSessionFactory = self.session_factory

database_client = DatabaseClient()

#endregion

#region DI и зависимость

async def init_database() -> None:
    await database_client.init_database()

def is_database_initialized() -> bool:
    return database_client.is_initialized()

async def dispose_database() -> None:
    await database_client.dispose_database()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in database_client.get_db():
        yield session

def get_session_factory() -> sessionmaker:
    return database_client.get_session_factory()

#endregion
