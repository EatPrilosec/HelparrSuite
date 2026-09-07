import asyncio
import logging
from typing import Dict, Optional, Set
from datetime import datetime
from sqlalchemy import select

from backend.app.core.database import AsyncSessionLocal
from backend.app.models.job import Job

logger = logging.getLogger(__name__)


class ConcurrencyManager:
    def __init__(self, max_concurrent_jobs: int = 2, max_concurrent_ollama: int = 1):
        self.job_semaphore = asyncio.Semaphore(max_concurrent_jobs)
        self.ollama_semaphore = asyncio.Semaphore(max_concurrent_ollama)
        self.active_tasks: Dict[int, asyncio.Task] = {}
        self.cancelled_job_ids: Set[int] = set()

    def update_limits(self, max_jobs: int, max_ollama: int):
        self.job_semaphore = asyncio.Semaphore(max(1, max_jobs))
        self.ollama_semaphore = asyncio.Semaphore(max(1, max_ollama))

    def register_task(self, job_id: int, task: asyncio.Task):
        self.active_tasks[job_id] = task

    def unregister_task(self, job_id: int):
        self.active_tasks.pop(job_id, None)

    def cancel_job(self, job_id: int) -> bool:
        self.cancelled_job_ids.add(job_id)
        task = self.active_tasks.get(job_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    def is_cancelled(self, job_id: int) -> bool:
        return job_id in self.cancelled_job_ids

    def clear_cancellation(self, job_id: int):
        self.cancelled_job_ids.discard(job_id)

    async def append_log(self, job_id: int, message: str, progress: Optional[float] = None):
        timestamp = datetime.utcnow().strftime("%H:%M:%S")
        log_line = f"[{timestamp}] {message}"
        async with AsyncSessionLocal() as db:
            try:
                res = await db.execute(select(Job).where(Job.id == job_id))
                job = res.scalars().first()
                if job:
                    current_logs = job.logs or ""
                    job.logs = (current_logs + "\n" + log_line) if current_logs else log_line
                    job.message = message[:250]
                    if progress is not None:
                        job.progress = min(100.0, max(0.0, float(progress)))
                    await db.commit()
            except Exception as e:
                logger.error(f"Failed to append log to job {job_id}: {e}")


concurrency_manager = ConcurrencyManager()
