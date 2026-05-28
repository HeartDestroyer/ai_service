# ai_service/infrastructure/worker_task/maintenance.py - Служебные фоновые задачи

#region Импорты и библиотеки

import json
import dramatiq

from core.configuration.settings import settings
from core.workers.worker import broker
from core.observability.logger import logger
from infrastructure.worker_task.redis_extensions import get_dramatiq_sync_redis_context

#endregion

#region Периодическая задача DLQ

@dramatiq.actor(queue_name = "scheduler", max_retries = 0)
def requeue_dlq_tasks_scheduled() -> None:
    """
    Перенос задач из DLQ обратно в исходные очереди.
    """
    dlq_key_prefix = settings.dramatiq.DLQ_KEY_PREFIX.rstrip(":")

    with get_dramatiq_sync_redis_context() as redis_client:
        for key in redis_client.scan_iter(f"{dlq_key_prefix}:*"):
            try:
                task_data = redis_client.get(key)
                if not task_data:
                    continue

                message = json.loads(task_data)
                broker.enqueue(dramatiq.Message(
                    queue_name = message.get("original_queue", "default"),
                    actor_name = message["task_name"],
                    args = message.get("args", []),
                    kwargs = message.get("kwargs", {}),
                    options = message.get("options", {}),
                ))
                
                redis_client.delete(key)
            
            except Exception as err:
                logger.error(f"Dramatiq | Ошибка requeue DLQ: {err}", exc_info = True)

#endregion
