# ai_service/core/workers/broker.py - Брокер Dramatiq

#region Импорты и библиотеки

import json
import os
import socket
import time
import dramatiq
import redis
from datetime import datetime, timedelta, timezone
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import AsyncIO, Middleware
from dramatiq.middleware.prometheus import Prometheus as DramatiqPrometheusMiddleware
from dramatiq.results import Results
from dramatiq.results.backends import RedisBackend
from prometheus_client import CollectorRegistry, Counter, Histogram, multiprocess, start_http_server

from core.configuration.settings import settings
from core.observability.logger import logger

#endregion

#region Переменные и метрики

os.environ.setdefault("PROMETHEUS_MULTIPROC_DIR", "/app/dramatiq_metrics/prometheus_multiproc")
MULTIPROC_DIR = os.environ["PROMETHEUS_MULTIPROC_DIR"]
os.makedirs(MULTIPROC_DIR, exist_ok = True)

DRAMATIQ_TASKS_TOTAL = Counter("dramatiq_tasks_total", "Total number of Dramatiq tasks executed", ["queue_name", "actor_name", "status"])
DRAMATIQ_TASK_DURATION = Histogram("dramatiq_task_duration_seconds", "Task execution time in seconds", ["queue_name", "actor_name"])

#endregion

#region Middleware Dramatiq

class PrometheusMetricsMiddleware(Middleware):
    """
    Middleware для Prometheus metrics\n
        - before_worker_boot - запуск Prometheus exporter
        - before_process_message - запись времени начала выполнения задачи
        - after_process_message - запись времени окончания выполнения задачи и метрик
    """

    def __init__(self, metrics_port: int = 9191):
        self.metrics_port = metrics_port
    
    def before_worker_boot(self, broker, worker):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(("0.0.0.0", self.metrics_port))
            sock.close()
            registry = CollectorRegistry()
            multiprocess.MultiProcessCollector(registry)
            start_http_server(self.metrics_port, registry = registry)
            logger.launch(f"Dramatiq | Prometheus exporter запущен на порту {self.metrics_port}")
        
        except OSError:
            logger.launch(f"Dramatiq | Worker пишет метрики в {MULTIPROC_DIR}")
    
    def before_process_message(self, broker, message):
        message.options["prometheus_start_time"] = time.time()
    
    def after_process_message(self, broker, message, *, result = None, exception = None):
        start_time = message.options.get("prometheus_start_time", time.time())
        duration = time.time() - start_time
        status = "error" if exception else "success"
        DRAMATIQ_TASKS_TOTAL.labels(queue_name = message.queue_name, actor_name = message.actor_name, status = status).inc()
        DRAMATIQ_TASK_DURATION.labels(queue_name = message.queue_name, actor_name = message.actor_name).observe(duration)

class TaskReportMiddleware(Middleware):
    """
    Middleware для отчетов о выполнении задач\n
        - before_process_message - запись времени начала выполнения задачи
        - after_process_message - запись времени окончания выполнения задачи и отчета
    """

    def __init__(self):
        self.redis_client = redis.Redis.from_url(settings.dramatiq.DRAMATIQ_REDIS_URL, decode_responses = True)
        self.reports_key_prefix = settings.dramatiq.REPORTS_KEY_PREFIX.rstrip(":")
        self.reports_ttl_days = int(os.getenv("DRAMATIQ_REPORTS_TTL_DAYS", "5"))
    
    def before_process_message(self, broker, message):
        report = {"task_id": message.message_id, "task_name": message.actor_name, "status": "running", "started_at": datetime.now(timezone.utc).isoformat(), "retries": message.options.get("retries", 0), "kwargs": message.kwargs, "args": message.args}
        self.redis_client.setex(f"{self.reports_key_prefix}:{message.message_id}", timedelta(days = self.reports_ttl_days), json.dumps(report, ensure_ascii = False))
    
    def after_process_message(self, broker, message, *, result = None, exception = None):
        key = f"{self.reports_key_prefix}:{message.message_id}"
        raw_report = self.redis_client.get(key)
        report = json.loads(raw_report) if raw_report else {"task_id": message.message_id, "task_name": message.actor_name, "started_at": datetime.now(timezone.utc).isoformat(), "retries": message.options.get("retries", 0), "kwargs": message.kwargs, "args": message.args}
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        
        if exception:
            report["status"] = "failed"
            report["error"] = str(exception)
            report["error_type"] = type(exception).__name__
        else:
            report["status"] = "completed"
            if result is not None:
                report["result"] = result
        
        self.redis_client.setex(key, timedelta(days = self.reports_ttl_days), json.dumps(report, ensure_ascii = False))

class DeadLetterQueueMiddleware(Middleware):
    """
    Middleware для отправки задач в DLQ\n
        - after_process_message - запись задачи в DLQ
    """

    def __init__(self):
        self.redis_client = redis.Redis.from_url(settings.dramatiq.DRAMATIQ_REDIS_URL, decode_responses = True)
        self.max_retries = settings.dramatiq.MAX_RETRIES
        self.dlq_key_prefix = settings.dramatiq.DLQ_KEY_PREFIX.rstrip(":")
        self.dlq_ttl_days = settings.dramatiq.DLQ_TTL_DAYS
    
    def after_process_message(self, broker, message, *, result = None, exception = None):
        if not exception or message.options.get("retries", 0) < self.max_retries:
            return
        
        dlq_data = {"task_id": message.message_id, "task_name": message.actor_name, "failed_at": datetime.now(timezone.utc).isoformat(), "retries_exhausted": message.options.get("retries", 0), "final_error": str(exception), "error_type": type(exception).__name__, "kwargs": message.kwargs, "args": message.args, "original_queue": message.queue_name}
        self.redis_client.setex(f"{self.dlq_key_prefix}:{message.message_id}", timedelta(days = self.dlq_ttl_days), json.dumps(dlq_data, ensure_ascii = False))
        logger.warning(f"Dramatiq | Задача {message.message_id} отправлена в DLQ")

#endregion

#region Инициализация брокера

redis_broker = RedisBroker(url = settings.dramatiq.DRAMATIQ_REDIS_URL)
result_backend = RedisBackend(url = settings.dramatiq.DRAMATIQ_REDIS_URL, namespace = settings.dramatiq.RESULTS_KEY_PREFIX)
redis_broker.middleware = [middleware for middleware in redis_broker.middleware if not isinstance(middleware, DramatiqPrometheusMiddleware)]
redis_broker.add_middleware(AsyncIO())
redis_broker.add_middleware(Results(backend = result_backend))
redis_broker.add_middleware(PrometheusMetricsMiddleware(metrics_port = int(os.getenv("DRAMATIQ_METRICS_PORT", "9191"))))
redis_broker.add_middleware(TaskReportMiddleware())
redis_broker.add_middleware(DeadLetterQueueMiddleware())
dramatiq.set_broker(redis_broker)

#endregion

#region DI и зависимость

def get_broker() -> RedisBroker:
    return redis_broker

#endregion
