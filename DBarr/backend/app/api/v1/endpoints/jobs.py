from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from datetime import datetime

from backend.app.core.database import get_db
from backend.app.models.job import Job
from backend.app.schemas.job import JobResponse
from backend.app.services.concurrency_manager import concurrency_manager

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=List[JobResponse])
async def list_jobs(limit: int = 50, db: AsyncSession = Depends(get_db)):
    stmt = select(Job).order_by(desc(Job.id)).limit(limit)
    res = await db.execute(stmt)
    return res.scalars().all()


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
