from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, delete
from datetime import datetime

from backend.app.core.database import get_db
from backend.app.models.job import Job
from backend.app.schemas.job import JobResponse
from backend.app.services.concurrency_manager import concurrency_manager

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.delete("/clear")
@router.post("/clear")
async def clear_jobs(status: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """
    Clears jobs by status:
    - 'completed' or 'finished' -> COMPLETED
    - 'failed' -> FAILED
    - 'cancelled' -> CANCELLED
    - 'all' or None -> COMPLETED, FAILED, CANCELLED
    Active jobs (RUNNING, PENDING) are never deleted.
    """
    if status:
        norm_status = status.upper().strip()
        if norm_status in ["FINISHED", "COMPLETED"]:
            target_statuses = ["COMPLETED"]
        elif norm_status == "FAILED":
            target_statuses = ["FAILED"]
        elif norm_status in ["CANCELLED", "INTERRUPTED"]:
            target_statuses = ["CANCELLED", "INTERRUPTED"]
        elif norm_status == "ALL":
            target_statuses = ["COMPLETED", "FAILED", "CANCELLED", "INTERRUPTED"]
        else:
            raise HTTPException(status_code=400, detail=f"Invalid status filter: {status}")
    else:
        target_statuses = ["COMPLETED", "FAILED", "CANCELLED", "INTERRUPTED"]

    stmt = delete(Job).where(Job.status.in_(target_statuses))
    res = await db.execute(stmt)
    await db.commit()
    deleted_count = res.rowcount if hasattr(res, "rowcount") else 0
    return {
        "success": True,
        "count": deleted_count,
        "message": f"Cleared {deleted_count} job(s) with status: {', '.join(target_statuses)}"
    }


@router.get("", response_model=List[JobResponse])
async def list_jobs(limit: int = 50, db: AsyncSession = Depends(get_db)):
    stmt = select(Job).order_by(desc(Job.id)).limit(limit)
    res = await db.execute(stmt)
    return res.scalars().all()


@router.delete("/{job_id}")
async def delete_job(job_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Job).where(Job.id == job_id)
    res = await db.execute(stmt)
    job = res.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status in ["PENDING", "RUNNING"]:
        raise HTTPException(status_code=400, detail="Cannot delete an active or running job. Cancel it first.")

    await db.delete(job)
    await db.commit()
    return {"success": True, "message": f"Job #{job_id} deleted successfully"}


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Job).where(Job.id == job_id)
    res = await db.execute(stmt)
    job = res.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Job).where(Job.id == job_id)
    res = await db.execute(stmt)
    job = res.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status in ["COMPLETED", "FAILED", "CANCELLED"]:
        return {"success": False, "message": f"Job is already {job.status}"}

    cancelled = concurrency_manager.cancel_job(job_id)
    job.status = "CANCELLED"
    job.message = "Cancelled by user request."
    job.finished_at = datetime.utcnow()
    await db.commit()

    return {"success": True, "message": "Job marked as cancelled", "active_task_cancelled": cancelled}
