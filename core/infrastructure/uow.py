# ai_service/core/infrastructure/uow.py - Паттерн UoW для работы с репозиториями

#region Импорты и библиотеки

from __future__ import annotations
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from core.observability.logger import logger
from core.infrastructure.database import get_db, is_database_initialized, AsyncSessionFactory as CurrentAsyncSessionFactory

#endregion

class UnitOfWork:

    def __init__(self, db_session: AsyncSession, isolation_level: str | None = None):
        self.db_session = db_session
        self.isolation_level = isolation_level
    
    async def create_isolated_uow(self) -> "IsolatedUnitOfWork":
        if not is_database_initialized() or CurrentAsyncSessionFactory is None:
            logger.error("Расширение UOW | Фабрика сессий не инициализирована")
            raise RuntimeError("Фабрика сессий не была инициализирована")
        
        new_db_session = CurrentAsyncSessionFactory()
        return IsolatedUnitOfWork(new_db_session, self.isolation_level)
    
    async def __aenter__(self):
        if self.isolation_level:
            await self.db_session.connection(execution_options = {"isolation_level": self.isolation_level})
    
    async def __aexit__(self, exc_type, exc, tb):
        if exc:
            await self.rollback()
    
    async def commit(self):
        await self.db_session.commit()
    
    async def rollback(self):
        await self.db_session.rollback()

class IsolatedUnitOfWork(UnitOfWork):

    async def __aexit__(self, exc_type, exc, tb):
        try:
            await super().__aexit__(exc_type, exc, tb)
        finally:
            await self.db_session.close()

#region DI и зависимость

async def get_uow(db_session: AsyncSession = Depends(get_db)) -> UnitOfWork:
    return UnitOfWork(db_session)

UowDep = Annotated[UnitOfWork, Depends(get_uow)]

#endregion
