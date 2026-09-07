from typing import List, Optional
import json
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
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
        elif norm_status == "CANCELLED":
            target_statuses = ["CANCELLED"]
        elif norm_status == "INTERRUPTED":
            target_statuses = ["INTERRUPTED"]
        elif norm_status in ["CANCELLED_OR_INTERRUPTED", "CANCELLED_INTERRUPTED"]:
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
        task = concurrency_manager.active_tasks.get(job_id)
        if task and not task.done():
            raise HTTPException(status_code=400, detail="Cannot delete an actively running job. Cancel it first.")

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

    if job.status in ["COMPLETED", "FAILED", "CANCELLED", "INTERRUPTED"]:
        return {"success": False, "message": f"Job is already {job.status}"}

    cancelled = concurrency_manager.cancel_job(job_id)
    job.status = "CANCELLED"
    job.message = "Cancelled by user request."
    job.finished_at = datetime.utcnow()
    await db.commit()

    return {"success": True, "message": "Job marked as cancelled", "active_task_cancelled": cancelled}


@router.post("/{job_id}/restart")
async def restart_job(job_id: int, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    stmt = select(Job).where(Job.id == job_id)
    res = await db.execute(stmt)
    job = res.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # If status is PENDING or RUNNING, only block if it is genuinely executing in asyncio
    if job.status in ["PENDING", "RUNNING"]:
        task = concurrency_manager.active_tasks.get(job_id)
        if task and not task.done():
            return {"success": False, "message": f"Job #{job_id} is currently actively executing."}

    # Reset any previous cancellation in ConcurrencyManager
    concurrency_manager.clear_cancellation(job.id)

    # Reset job state
    job.status = "PENDING"
    job.progress = 0.0
    job.finished_at = None
    restart_ts = datetime.utcnow().strftime("%H:%M:%S")
    current_logs = job.logs or ""
    job.logs = (current_logs + f"\n[{restart_ts}] --- Job restarted by user request ---") if current_logs else f"[{restart_ts}] --- Job restarted by user request ---"
    job.message = "Job queued for restart..."
    await db.commit()

    # Parse payload parameters
    payload_data = {}
    if job.payload:
        try:
            payload_data = json.loads(job.payload)
        except Exception:
            pass

    # Dispatch to background task based on job_type
    if job.job_type in ["IMPORT_SHOW", "BATCH_IMPORT"]:
        from backend.app.api.v1.endpoints.shows import run_import_pipeline
        sonarr_series_id = payload_data.get("sonarr_series_id")
        scan_mode = payload_data.get("scan_mode", "full")
        if sonarr_series_id:
            background_tasks.add_task(
                run_import_pipeline,
                sonarr_series_id=sonarr_series_id,
                job_id=job.id,
                scan_mode=scan_mode
            )
        else:
            job.status = "FAILED"
            job.message = "Cannot restart: missing Sonarr series ID in payload"
            await db.commit()
            return {"success": False, "message": job.message}

    elif job.job_type == "AUDIT_SHOW":
        from backend.app.services.verification_engine import VerificationEngine
        show_id = payload_data.get("show_id") or job.show_id
        if show_id:
            background_tasks.add_task(
                VerificationEngine.run_show_verification,
                show_id=show_id,
                job_id=job.id
            )
        else:
            job.status = "FAILED"
            job.message = "Cannot restart: missing show ID in job"
            await db.commit()
            return {"success": False, "message": job.message}

    return {"success": True, "message": f"Job #{job_id} restarted successfully"}
