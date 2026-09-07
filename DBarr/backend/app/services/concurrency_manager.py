import asyncio
import logging
from typing import Dict, Optional, Set
from datetime import datetime
from sqlalchemy import select

from backend.app.core.database import AsyncSessionLocal
from backend.app.models.job import Job

logger = logging.getLogger(__name__)


class AdjustableSemaphore:
    """
    An adjustable concurrency limiter that maintains a single, persistent
    instance across configuration changes.

    Unlike reassigning an asyncio.Semaphore (which abandons held permits and
    allows excess tasks to run concurrently), AdjustableSemaphore dynamically
    resizes capacity and cleanly manages waiters without leaking concurrency slots.
    """
    def __init__(self, capacity: int = 1):
        self._capacity = max(1, capacity)
        self._current = 0
        self._cond: Optional[asyncio.Condition] = None

    def _get_cond(self) -> asyncio.Condition:
        if self._cond is None:
            self._cond = asyncio.Condition()
        return self._cond

    async def __aenter__(self):
        cond = self._get_cond()
        async with cond:
            while self._current >= self._capacity:
                await cond.wait()
            self._current += 1
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        cond = self._get_cond()
        async with cond:
            self._current = max(0, self._current - 1)
            cond.notify()

    def update_capacity(self, new_capacity: int):
        new_val = max(1, new_capacity)
        if new_val == self._capacity:
            return
        cond = self._get_cond()
        self._capacity = new_val
        try:
            loop = asyncio.get_running_loop()
            async def _wake_waiters():
                async with cond:
                    cond.notify_all()
            loop.create_task(_wake_waiters())
        except RuntimeError:
            pass

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def current(self) -> int:
        return self._current


class ConcurrencyManager:
    def __init__(self, max_concurrent_jobs: int = 2, max_concurrent_ollama: int = 1):
        self.job_semaphore = AdjustableSemaphore(max_concurrent_jobs)
        self.ollama_semaphore = AdjustableSemaphore(max_concurrent_ollama)
        self.active_tasks: Dict[int, asyncio.Task] = {}
        self.cancelled_job_ids: Set[int] = set()

    def update_limits(self, max_jobs: int, max_ollama: int):
        self.job_semaphore.update_capacity(max_jobs)
        self.ollama_semaphore.update_capacity(max_ollama)

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
