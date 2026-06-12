"""健康检查路由"""
from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "ai_provider": settings.AI_PROVIDER,
    }
