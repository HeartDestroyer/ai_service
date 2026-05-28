# ai_service/core/middleware/headers.py - Middleware заголовков

#region Импорты и библиотеки

from fastapi import Request
from secure import Secure
from starlette.middleware.base import BaseHTTPMiddleware

from core.configuration.settings import settings

#endregion

secure_headers = Secure.with_default_headers()

class HeadersMiddleware(BaseHTTPMiddleware):
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        if request.url.path in settings.security.DOCS_WHITELIST:
            return response

        secure_headers.set_headers(response)
        return response
