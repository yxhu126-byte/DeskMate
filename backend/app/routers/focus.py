"""专注陪伴模式 (Focus Companion) 路由"""
import logging
from fastapi import APIRouter

from app.schemas.chat import (
    FocusTickRequest,
    FocusTickResponse,
    FocusReportRequest,
    FocusReportResponse,
)
from app.services.focus_service import focus_service

router = APIRouter(prefix="/api/focus", tags=["focus"])
logger = logging.getLogger(__name__)


@router.post("/tick", response_model=FocusTickResponse)
async def focus_tick(request: FocusTickRequest):
    """
    专注模式 — 周期性屏幕帧上传。

    前端按设定频率截取屏幕帧发送到此端点。
    FocusService 维护专注会话状态机，判断当前状态（专注/走神/离开），
    并在满足条件时返回提醒消息。
    """
    logger.info(
        f"[Focus Tick] session={request.session_id[:8]}... "
        f"tick=#{request.metadata.tick_index} "
        f"elapsed={request.metadata.seconds_elapsed}s "
        f"title={request.metadata.page_title or '-'} "
        f"hash={request.metadata.frame_hash[:8]}..."
    )

    return focus_service.process_tick(request)


@router.post("/report", response_model=FocusReportResponse)
async def focus_report(request: FocusReportRequest):
    """
    专注模式 — 任务简报生成。

    在用户结束专注后调用，基于 FocusService 中记录的专注/走神/离开
    时段数据生成结构化的任务简报。
    """
    logger.info(f"[Focus Report] session={request.session_id[:8]}...")
    return focus_service.generate_report(request.session_id)
