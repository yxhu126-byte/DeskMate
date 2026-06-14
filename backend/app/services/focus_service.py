"""专注陪伴模式 (Focus Companion) — 状态机与走神检测引擎"""
import logging
import time
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import Optional, Dict, List

from app.schemas.chat import (
    FocusTickRequest,
    FocusTickResponse,
    FocusReportRequest,
    FocusReportResponse,
    FocusSegment,
)
from app.services.multimodal_ai_service import multimodal_ai_service

logger = logging.getLogger(__name__)

# ── 走神关键词（规则判断用，后续 PR #5 改为 AI 判断） ──
DISTRACTION_KEYWORDS = [
    "视频", "游戏", "直播", "微博", "知乎", "贴吧", "抖音",
    "bilibili", "B站", "Bilibili", "youtube", "YouTube",
    "netflix", "Netflix", "漫画", "小说", "购物",
    "淘宝", "京东", "拼多多", "闲鱼", "豆瓣", "虎扑",
    "twitch", "Twitch", "discord", "steam", "Steam",
    "小红书", "斗鱼", "虎牙",
]

# ── 阈值配置 ──
SAME_HASH_AWAY_TICKS = 10       # 连续 hash 相同 → 判定离开
DISTRACTED_ALERT_TICKS = 4      # 连续走神 N 次后触发提醒（配合前端频率）
ALERT_COOLDOWN_SECONDS = 300    # 两次提醒至少间隔 5 分钟
HASH_CHANGE_MIN_DISTANCE = 3    # hash 距离小于此值视为无变化

# 北京时间时区
TZ_BEIJING = timezone(timedelta(hours=8))

_CN_TIME_FORMAT = "%H:%M"


def _now_cn() -> str:
    """返回北京时间 HH:MM 字符串"""
    return datetime.now(TZ_BEIJING).strftime(_CN_TIME_FORMAT)


def _is_distraction_title(title: Optional[str]) -> bool:
    """简单关键词匹配判断页面标题是否可能为走神内容"""
    if not title:
        return False
    for kw in DISTRACTION_KEYWORDS:
        if kw.lower() in title.lower():
            return True
    return False


# ══════════════════════════════════════════════════════════
# 专注会话
# ══════════════════════════════════════════════════════════

@dataclass
class FocusSession:
    """单个专注会话的完整状态"""
    session_id: str
    task: str
    start_time: str = field(default_factory=_now_cn)

    # 当前状态
    current_status: str = "focused"  # focused | distracted | away
    status_started_at: str = field(default_factory=_now_cn)
    consecutive_ticks: int = 0         # 当前状态连续 tick 数

    # 提醒控制
    alert_count: int = 0
    last_alert_at: Optional[float] = None  # epoch timestamp

    # 帧哈希历史
    last_hash: Optional[str] = None
    same_hash_count: int = 0          # 连续相同 hash 的 tick 数

    # 时段记录
    segments: List[dict] = field(default_factory=list)

    # 统计
    total_ticks: int = 0
    tick_start_time: Optional[float] = None  # 首次 tick 的时间戳


# ══════════════════════════════════════════════════════════
# 专注服务
# ══════════════════════════════════════════════════════════

class FocusService:
    """专注陪伴模式核心服务"""

    def __init__(self):
        self._sessions: Dict[str, FocusSession] = {}

    # ── 获取或创建会话 ──
    def _get_session(self, session_id: str, task: str) -> FocusSession:
        if session_id not in self._sessions:
            self._sessions[session_id] = FocusSession(
                session_id=session_id,
                task=task,
            )
        return self._sessions[session_id]

    # ═══════════════════════════════════════════════════
    # 核心方法：处理一次 tick
    # ═══════════════════════════════════════════════════

    async def process_tick(self, request: FocusTickRequest) -> FocusTickResponse:
        session = self._get_session(request.session_id, request.task)
        session.total_ticks += 1

        if session.tick_start_time is None:
            session.tick_start_time = time.time()

        meta = request.metadata
        current_hash = meta.frame_hash

        # ── 1. 计算 hash 是否变化 ──
        hash_changed = True
        if session.last_hash:
            # hash 完全相同 → 画面无变化
            if current_hash == session.last_hash:
                session.same_hash_count += 1
                hash_changed = False
            else:
                session.same_hash_count = 0
        else:
            session.same_hash_count = 0

        session.last_hash = current_hash

        # ── 2. 判断新状态（AI 增强 + 规则兜底） ──
        new_status = await self._determine_status(session, request, hash_changed)

        # ── 3. 状态转换处理 ──
        if new_status != session.current_status:
            # 记录上一个时段
            self._close_segment(session, new_status)
            session.current_status = new_status
            session.status_started_at = _now_cn()
            session.consecutive_ticks = 1
        else:
            session.consecutive_ticks += 1

        # ── 4. 判断是否需要提醒（AI 生成文案 + 模板兜底） ──
        should_alert, alert_message = await self._should_alert(session, meta)

        # ── 5. 内部 AI 备注（PR #5 升级为真实 AI 内容） ──
        ai_note = self._build_ai_note(session, meta)

        logger.debug(
            f"[Focus] session={session.session_id[:8]}... "
            f"tick=#{meta.tick_index} status={new_status} "
            f"consec={session.consecutive_ticks} alert={should_alert}"
        )

        return FocusTickResponse(
            status=new_status,
            should_alert=should_alert,
            alert_message=alert_message,
            ai_note=ai_note,
        )

    # ═══════════════════════════════════════════════════
    # 状态判定（规则版本，PR #5 升级为 AI）
    # ═══════════════════════════════════════════════════

    async def _determine_status(
        self,
        session: FocusSession,
        request: FocusTickRequest,
        hash_changed: bool,
    ) -> str:
        """
        状态机核心逻辑（AI 增强版）。

        策略:
        1. 画面无变化 → AWAY（规则快速通道，无需 AI）
        2. 从 AWAY 恢复 → FOCUSED（规则快速通道）
        3. 画面有变化 → 调用 AI 判断相关性（有 API Key 时）
           → 规则兜底（mock 模式或无 Key）
        """
        meta = request.metadata
        current = session.current_status

        # 规则快速通道: 长时间画面无变化 → 离开
        if session.same_hash_count >= SAME_HASH_AWAY_TICKS:
            return "away"

        # 规则快速通道: 从离开状态恢复
        if current == "away" and hash_changed:
            return "focused"

        # 画面无明显变化 → 保持当前状态
        if not hash_changed:
            return current

        # 画面有变化 → AI 判断任务相关度
        ai_result = await multimodal_ai_service.focus_check_relevance(
            task=session.task,
            image_base64=request.screen_frame.data,
            page_title=meta.page_title,
        )

        # 缓存 AI 判断结果供后续使用
        session._last_ai_activity = ai_result.get("activity", "")
        session._last_ai_confidence = ai_result.get("confidence", 0.5)

        is_related = ai_result.get("related", True)
        confidence = ai_result.get("confidence", 0.5)

        if is_related:
            # 与任务相关 → 专注
            if current == "distracted":
                return "focused"  # 从走神中恢复
            return "focused"
        else:
            # 与任务不相关 → 走神（高置信度时）
            if confidence > 0.6 and current == "focused":
                return "distracted"
            return current  # 低置信度或已在走神，保持不变

    # ═══════════════════════════════════════════════════
    # 提醒判断
    # ═══════════════════════════════════════════════════

    async def _should_alert(self, session: FocusSession, meta) -> tuple:
        """
        判断此时是否应提醒用户（AI 生成提醒文案）。
        """
        now = time.time()

        # 冷却检查
        if session.last_alert_at and (now - session.last_alert_at) < ALERT_COOLDOWN_SECONDS:
            return False, None

        # DISTRACTED 提醒
        if session.current_status == "distracted":
            if session.consecutive_ticks >= DISTRACTED_ALERT_TICKS:
                current_activity = getattr(session, '_last_ai_activity', meta.page_title or '其他页面')
                distracted_min = round(session.consecutive_ticks * 30 / 60) or 1

                # 调用 AI 生成提醒文案
                message = await multimodal_ai_service.focus_generate_alert(
                    task=session.task,
                    elapsed_minutes=round(
                        (time.time() - (session.tick_start_time or now)) / 60
                    ) or 1,
                    current_activity=current_activity,
                    distracted_minutes=distracted_min,
                )

                session.last_alert_at = now
                session.alert_count += 1
                return True, message

        # 从 AWAY 恢复 → 简短欢迎（不用 AI，保持简洁）
        if session.current_status == "focused" and session.consecutive_ticks == 1:
            if session.segments and session.segments[-1].get("status") == "away":
                session.last_alert_at = now
                session.alert_count += 1
                return True, "看到你回来了！继续加油～"

        return False, None

    # ═══════════════════════════════════════════════════
    # 时段管理
    # ═══════════════════════════════════════════════════

    def _close_segment(self, session: FocusSession, new_status: str):
        """结束当前时段，记录到 segments"""
        now = _now_cn()
        if session.segments:
            session.segments[-1]["end_time"] = now

        session.segments.append({
            "start_time": now,
            "end_time": None,
            "status": new_status,
            "note": self._status_note(new_status),
        })

    def _status_note(self, status: str) -> str:
        notes = {
            "focused": "专注中",
            "distracted": "走神 - 页面内容与任务无关",
            "away": "离开 - 画面长时间无变化",
        }
        return notes.get(status, status)

    def _build_ai_note(self, session: FocusSession, meta) -> Optional[str]:
        """构建 AI 内部备注（PR #5 升级）"""
        if session.current_status == "distracted":
            return f"用户页面: {meta.page_title or '未知'}"
        if session.current_status == "away":
            return f"画面连续不变 {session.same_hash_count} 次"
        return None

    # ═══════════════════════════════════════════════════
    # 简报生成（骨架，PR #7 完整实现）
    # ═══════════════════════════════════════════════════

    async def generate_report(self, session_id: str) -> FocusReportResponse:
        """生成任务简报（AI 增强版）"""
        session = self._sessions.get(session_id)
        if not session:
            return FocusReportResponse(
                task="(未找到会话)",
                summary="没有找到对应的专注会话记录",
                suggestions=["请确认 session_id 正确"],
            )

        # 关闭最后一个 segment
        if session.segments:
            session.segments[-1]["end_time"] = _now_cn()

        # 统计时长
        total_ticks = session.total_ticks
        total_min = max(1, round(total_ticks * 30 / 60))

        # 按 segment 类型估算分钟
        seg_count = max(1, len(session.segments))
        focused_count = sum(1 for s in session.segments if s["status"] == "focused")
        distracted_count = sum(1 for s in session.segments if s["status"] == "distracted")
        away_count = sum(1 for s in session.segments if s["status"] == "away")

        focused_min = max(0, round(focused_count * total_min / seg_count))
        distracted_min = max(0, round(distracted_count * total_min / seg_count))
        away_min = max(0, total_min - focused_min - distracted_min)

        # 构建 Segment 列表
        segments_out = [
            FocusSegment(
                start_time=s["start_time"],
                end_time=s.get("end_time"),
                status=s["status"],
                note=s.get("note"),
            )
            for s in session.segments
        ]

        # ── 调用 AI 生成简报 ──
        timeline_text = "\n".join(
            f"[{s['start_time']}-{s.get('end_time', '?')}] {s['status']}: {s.get('note', '')}"
            for s in session.segments
        )

        ai_report = await multimodal_ai_service.focus_generate_report(
            task=session.task,
            total_min=total_min,
            focused_min=focused_min,
            distracted_min=distracted_min,
            away_min=away_min,
            timeline_text=timeline_text,
        )

        return FocusReportResponse(
            task=session.task,
            total_minutes=total_min,
            focused_minutes=focused_min,
            distracted_minutes=distracted_min,
            away_minutes=away_min,
            segments=segments_out,
            completion_assessment=ai_report.get("completion_assessment", ""),
            summary=ai_report.get("summary", ""),
            suggestions=ai_report.get("suggestions", []),
        )


# ── 单例 ──
focus_service = FocusService()
