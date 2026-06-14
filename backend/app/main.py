"""DeskMate AI 伴随助手 — FastAPI 应用入口"""
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import chat, speech, health, focus

# ── 日志配置 ──
# Windows 环境下强制 UTF-8 编码，避免 emoji 和中文导致的 UnicodeEncodeError
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


# ── 应用生命周期 ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动和关闭时的生命周期管理"""
    logger.info(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} 启动中...")
    logger.info(f"   AI 提供商: {settings.AI_PROVIDER}")
    logger.info(f"   图片压缩: 最大 {settings.IMAGE_MAX_WIDTH}px, "
                f"质量 {settings.IMAGE_QUALITY}%")
    logger.info(f"   会话 TTL: {settings.SESSION_TTL_SECONDS}s")
    yield
    logger.info(f"👋 {settings.APP_NAME} 关闭")


# ── 创建应用 ──
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="网页端 AI 多模态伴随助手 — 支持屏幕共享、摄像头、麦克风的多模态问答",
    lifespan=lifespan,
)

# ── CORS 配置 ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 注册路由 ──
app.include_router(chat.router)
app.include_router(speech.router)
app.include_router(health.router)
app.include_router(focus.router)


# ── 根路径 ──
@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/api/health",
    }


# ── 直接运行入口 ──
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
