from fastapi import APIRouter
from backend.app.api.v1.endpoints.shows import router as shows_router
from backend.app.api.v1.endpoints.episodes import router as episodes_router
from backend.app.api.v1.endpoints.jobs import router as jobs_router
from backend.app.api.v1.endpoints.settings import router as settings_router

api_router = APIRouter()
api_router.include_router(shows_router)
api_router.include_router(episodes_router)
api_router.include_router(jobs_router)
api_router.include_router(settings_router)
