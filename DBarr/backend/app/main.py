from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select

from backend.app.core.config import settings
from backend.app.core.database import init_db, AsyncSessionLocal
from backend.app.api.v1.router import api_router
from backend.app.models.setting import Setting
from backend.app.services.concurrency_manager import concurrency_manager


from backend.app.core.config_manager import sync_config_on_startup


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database schema
    await init_db()

    # Sync persistent config.json, environment variables, and SQLite settings
    async with AsyncSessionLocal() as db:
        try:
            await sync_config_on_startup(db)
            stmt = select(Setting)
            res = await db.execute(stmt)
            data = {r.key: r.value for r in res.scalars().all()}
            max_jobs = int(data.get("max_concurrent_jobs", 1)) if str(data.get("max_concurrent_jobs", "")).isdigit() else 1
            max_ollama = int(data.get("max_concurrent_ollama_requests", 1)) if str(data.get("max_concurrent_ollama_requests", "")).isdigit() else 1
            concurrency_manager.update_limits(max_jobs, max_ollama)
        except Exception:
            pass

    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "port": settings.PORT
    }


# Static file hosting (Frontend SPA)
static_dir = Path(__file__).resolve().parent / "static"

if static_dir.exists() and (static_dir / "index.html").exists():
    if (static_dir / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        if full_path.startswith("api"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        file_path = static_dir / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(static_dir / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
