# ai_service/infrastructure/worker_task/scheduler_wrapper.py - Обертка планировщика задач Dramatiq

#region Импорты и библиотеки

from apscheduler.schedulers.blocking import BlockingScheduler
from zoneinfo import ZoneInfo

from core.observability.logger import logger
from core.configuration.scheduler import schedule_settings
from infrastructure.worker_task import requeue_dlq_tasks_scheduled

#endregion

#region Конфигурация планировщика

scheduler = BlockingScheduler(timezone = ZoneInfo("UTC"))
settings_cron: dict[str, dict] = {}

if schedule_settings.DLQ_RETRY:
    settings_cron["sys_dlq_retry"] = schedule_settings.DLQ_RETRY.model_dump(exclude_none = True)

if "sys_dlq_retry" in settings_cron:
    scheduler.add_job(lambda: requeue_dlq_tasks_scheduled.send(), "cron", id = "sys_dlq_retry", **settings_cron["sys_dlq_retry"])

#endregion

#region Запуск планировщика

if __name__ == "__main__":
    logger.launch("Scheduler | Запуск cron-планировщика Dramatiq")
    scheduler.start()

#endregion
