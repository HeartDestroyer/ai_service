# ai_service/core/observability/logger.py - Расширение для логирования

#region Импорты и библиотеки

from logging.handlers import RotatingFileHandler, QueueHandler, QueueListener
from queue import Queue
import json, queue, sys, logging
from pathlib import Path
from datetime import datetime
from opentelemetry import trace

from core.configuration.settings import settings

#endregion

#region Кастомные уровни логирования

LAUNCH_LEVEL = 26
ANALYSIS_LEVEL = 25
DIAGNOSTICS_LEVEL = 24
API_LEVEL = 23

#endregion

#region Регистрация кастомного уровня логирования

def _register_custom_level(levelno: int, level_name: str, method_name: str) -> None:
    """
    Регистрация кастомного уровня логирования
    """

    logging.addLevelName(levelno, level_name)
    
    def _log_for_level(self, message, *args, **kwargs):
        if self.isEnabledFor(levelno):
            self._log(levelno, message, args, **kwargs)
    setattr(logging.Logger, method_name, _log_for_level)

_register_custom_level(LAUNCH_LEVEL, "LAUNCH", "launch")
_register_custom_level(ANALYSIS_LEVEL, "ANALYSIS", "analysis")
_register_custom_level(API_LEVEL, "API", "api")
_register_custom_level(DIAGNOSTICS_LEVEL, "DIAGNOSTICS", "diagnostics")

#endregion

#region Форматтеры и фильтры

class CustomJsonFormatter(logging.Formatter):
    
    def __init__(self):
        super().__init__()
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Форматирование сообщения в JSON
        """
        log_object: dict[str, any] = {
            'timestamp': datetime.fromtimestamp(record.created).strftime("%d.%m.%Y %H:%M:%S"),
            'level': record.levelname,
            'message': str(record.getMessage()),
            'correlation_id': getattr(record, 'correlation_id', None),
            'module': record.module,
            'line': record.lineno,
        }

        span = trace.get_current_span()
        if span and span.get_span_context().is_valid:
            span_context = span.get_span_context()
            log_object["trace_id"] = format(span_context.trace_id, "032x")
            log_object["span_id"] = format(span_context.span_id, "016x")
        
        if record.exc_info:
            exc_type, exc_value, _ = record.exc_info
            log_object['exception'] = {'type': exc_type.__name__ if exc_type else None, 'message': str(exc_value) if exc_value else None, 'traceback': self.formatException(record.exc_info)}
        
        return json.dumps(log_object, ensure_ascii = False)

class NonBlockingQueueHandler(QueueHandler):
    
    def enqueue(self, record: logging.LogRecord) -> None:
        """
        Добавление сообщения в очередь
        """
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            sys.stderr.write("Не удалось добавить сообщение в очередь, очередь заполнена\n")

class ExactLevelFilter(logging.Filter):
    
    def __init__(self, levelno: int):
        super().__init__()
        self.levelno = levelno
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Фильтрация сообщений по уровню логирования
        """
        return record.levelno == self.levelno

class ExcludeLevelFilter(logging.Filter):
    
    def __init__(self, levelno: int):
        super().__init__()
        self.levelno = levelno
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Фильтрация сообщений по уровню логирования
        """
        return record.levelno != self.levelno

#endregion

#region Менеджер handlers

class LoggerHandlerManager:
    
    def __init__(self, logs_dir: Path):
        self.logs_dir = logs_dir
        self.logs_dir.mkdir(parents = True, exist_ok = True)
        self.app, self.info, self.analysis, self.api, self.launch, self.error, self.diagnostics = "app.log", "info.log", "analysis.log", "api.log", "launch.log", "error.log", "diagnostics.log"
    
    def _create_rotating_handler(self, filename: str, level: int = None, log_filter: logging.Filter = None) -> RotatingFileHandler:
        """
        Создание обработчика ротации файлов
        """
        handler = RotatingFileHandler(filename = self.logs_dir / filename, maxBytes = settings.logging.LOG_FILE_MAX_BYTES, backupCount = settings.logging.LOG_FILE_BACKUP_COUNT, encoding = "utf-8")
        handler.setFormatter(CustomJsonFormatter())
        
        if level is not None:
            handler.setLevel(level)
        
        if log_filter is not None:
            handler.addFilter(log_filter)
        
        return handler
    
    def create_file_handler(self) -> RotatingFileHandler:
        return self._create_rotating_handler(self.app, log_filter = ExcludeLevelFilter(LAUNCH_LEVEL))
    
    def create_info_handler(self) -> RotatingFileHandler:
        return self._create_rotating_handler(self.info, log_filter = ExactLevelFilter(logging.INFO))
    
    def create_analysis_handler(self) -> RotatingFileHandler:
        return self._create_rotating_handler(self.analysis, log_filter = ExactLevelFilter(ANALYSIS_LEVEL))
    
    def create_api_handler(self) -> RotatingFileHandler:
        return self._create_rotating_handler(self.api, log_filter = ExactLevelFilter(API_LEVEL))
    
    def create_diagnostics_handler(self) -> RotatingFileHandler:
        return self._create_rotating_handler(self.diagnostics, log_filter = ExactLevelFilter(DIAGNOSTICS_LEVEL))
    
    def create_error_handler(self) -> RotatingFileHandler:
        return self._create_rotating_handler(self.error, level = logging.ERROR)
    
    def create_launch_handler(self) -> RotatingFileHandler:
        return self._create_rotating_handler(self.launch, log_filter = ExactLevelFilter(LAUNCH_LEVEL))

#endregion

#region Класс Logger

class Logger:

    def __init__(self):
        project_root = Path(__file__).resolve().parent.parent.parent
        self.logs_dir = project_root / settings.logging.LOGS_DIR
        self.logger = logging.getLogger('app')
        self.logger.setLevel(settings.logging.LOG_LEVEL)
        self.logger.handlers.clear()
        self.handler_manager = LoggerHandlerManager(self.logs_dir)
        self._log_queue = Queue(maxsize = settings.logging.LOG_QUEUE_MAX_SIZE)
        self._queue_listener = None
        self._handlers_initialized = False
        self._setup_handlers()
    
    def _setup_handlers(self) -> None:
        """
        Настройка обработчиков логирования
        """
        if self._handlers_initialized:
            return
        
        self._handlers_initialized = True
        handlers = [
            self.handler_manager.create_file_handler(),
            self.handler_manager.create_info_handler(),
            self.handler_manager.create_analysis_handler(),
            self.handler_manager.create_api_handler(),
            self.handler_manager.create_diagnostics_handler(),
            self.handler_manager.create_error_handler(),
            self.handler_manager.create_launch_handler(),
        ]

        self._queue_listener = QueueListener(self._log_queue, *handlers, respect_handler_level = True)
        self._queue_listener.start()
        self.logger.addHandler(NonBlockingQueueHandler(self._log_queue))
        self.logger.propagate = False
    
    def get_logger(self) -> logging.Logger:
        return self.logger
    
    def shutdown(self) -> None:
        if self._queue_listener is not None:
            self._queue_listener.stop()
            self._queue_listener = None
            self._handlers_initialized = False

logger_instance = Logger()
logger = logger_instance.get_logger()

#endregion
