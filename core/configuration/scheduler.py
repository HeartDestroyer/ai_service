# ai_service/core/configuration/scheduler.py - Конфигурация планировщика задач

#region Импорты и библиотеки

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

#endregion

#region Конфигурация планировщика задач

class CronSchedule(BaseModel):
    minute: int | str = Field(..., description = "Минуты")
    hour: int | str | None = Field(None, description = "Часы")
    day: int | str | None = Field(None, description = "Дни месяца")
    day_of_week: str | None = Field(None, description = "Дни недели")
    month: int | str | None = Field(None, description = "Месяц")
    year: int | str | None = Field(None, description = "Год")

#endregion

class SchedulerSettings(BaseSettings):
    
    #region Настройки планировщика задач

    DLQ_RETRY: CronSchedule | None = CronSchedule(minute = "*/15")

    #endregion

    model_config = SettingsConfigDict(env_prefix = "SCHEDULE__", env_nested_delimiter = "__", env_file = ".env", env_file_encoding = "utf-8", extra = "ignore")

schedule_settings = SchedulerSettings()
