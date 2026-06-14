"""专注陪伴模式 (Focus Companion) 路由"""
import logging
from fastapi import APIRouter

from app.schemas.chat import (
    FocusTickRequest,
    FocusTickResponse,
    FocusReportRequest,
    FocusReportResponse,
)

router = APIRouter(prefix="/api/focus", tags=["focus"])
logger = logging.getLogger(__name__)


@router.post("/tick", response_model=FocusTickResponse)
async def focus_tick(request: FocusTickRequest):
    """
    专注模式 — 周期性屏幕帧上传。

    前端按设定频率（默认 30s）截取屏幕帧发送到此端点。
    当前为 mock 实现，后续 PR 将接入 FocusService 进行走神检测。
    """
    logger.info(
        f"[Focus Tick] session={request.session_id[:8]}... "
        f"tick=#{request.metadata.tick_index} "
        f"elapsed={request.metadata.seconds_elapsed}s "
        f"hash={request.metadata.frame_hash[:8]}..."
    )

    return FocusTickResponse(
        status="focused",
        should_alert=False,
        alert_message=None,
        ai_note=None,
    )


@router.post("/report", response_model=FocusReportResponse)
async def focus_report(request: FocusReportRequest):
    """
    专注模式 — 任务简报生成。

    在用户结束专注后调用，返回本次专注的结构化简报。
    当前为 mock 实现，后续 PR 将基于 FocusService 的 segments 生成真实报告。
    """
    logger.info(f"[Focus Report] session={request.session_id[:8]}...")

    return FocusReportResponse(
        task="(演示) 专注任务",
        total_minutes=30,
        focused_minutes=22,
        distracted_minutes=5,
        away_minutes=3,
        segments=[
            {"start_time": "14:05", "end_time": "14:20", "status": "focused", "note": "专注工作中"},
            {"start_time": "14:20", "end_time": "14:25", "status": "distracted", "note": "浏览其他页面"},
            {"start_time": "14:25", "end_time": "14:35", "status": "focused", "note": "继续工作"},
        ],
        completion_assessment="(演示) 你完成了约 70% 的任务内容。",
        summary="(演示) 这段时间你大部分时间在专注工作，中间短暂分心了 5 分钟。整体表现不错！",
        suggestions=[
            "(演示) 下次可以尝试关闭不必要的标签页",
            "(演示) 25 分钟专注 + 5 分钟休息的节奏可以试试",
        ],
    )
