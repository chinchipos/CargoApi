import traceback

from src.celery_tasks.init import sync_task_logger


class SyncError(Exception):

    def __init__(self, trace: bool, message: str) -> None:
        if trace:
            trace_info = traceback.format_exc()
            sync_task_logger.error(message)
            sync_task_logger.error(trace_info)

        else:
            sync_task_logger.error(message)

        super().__init__(message)