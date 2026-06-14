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

    def process_tick(self, request: FocusTickRequest) -> FocusTickResponse:
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

        # ── 2. 判断新状态 ──
        new_status = self._determine_status(session, meta, hash_changed)

        # ── 3. 状态转换处理 ──
        if new_status != session.current_status:
            # 记录上一个时段
            self._close_segment(session, new_status)
            session.current_status = new_status
            session.status_started_at = _now_cn()
            session.consecutive_ticks = 1
        else:
            session.consecutive_ticks += 1

        # ── 4. 判断是否需要提醒 ──
        should_alert, alert_message = self._should_alert(session, meta)

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

    def _determine_status(
        self,
        session: FocusSession,
        meta,
        hash_changed: bool,
    ) -> str:
        """
        状态机核心逻辑。

        规则（非 AI 版本）：
        - 画面长时间无变化 → AWAY
        - 画面变化 + 标题包含娱乐关键词 → DISTRACTED
        - 从 DISTRACTED/AWAY 回来 + 画面变化 + 标题不匹配娱乐 → FOCUSED
        - 默认保持当前状态
        """
        current = session.current_status

        # 规则 1: 长时间画面无变化 → 离开
        if session.same_hash_count >= SAME_HASH_AWAY_TICKS:
            return "away"

        # 规则 2: 从离开状态恢复
        if current == "away" and hash_changed:
            return "focused"

        # 规则 3: 画面有显著变化 → 判断内容
        if hash_changed and _is_distraction_title(meta.page_title):
            # 标题匹配走神关键词 → 走神
            if current == "focused":
                return "distracted"
            return current  # 已经是 distracted 就保持

        # 规则 4: 从走神中恢复
        if current == "distracted" and hash_changed:
            if not _is_distraction_title(meta.page_title):
                return "focused"

        # 默认：保持当前状态
        return current

    # ═══════════════════════════════════════════════════
    # 提醒判断
    # ═══════════════════════════════════════════════════

    def _should_alert(self, session: FocusSession, meta) -> tuple:
        """
        判断此时是否应提醒用户。

        提醒规则：
        - 刚进入 DISTRACTED 且连续走神 tick 数达到阈值 → 提醒
        - 仍在 DISTRACTED 中，距上次提醒 > 冷却时间 → 提醒
        - 从 AWAY 恢复 → 简短欢迎（不算提醒）
        - 其他情况 → 不提醒
        """
        now = time.time()

        # 冷却检查
        if session.last_alert_at and (now - session.last_alert_at) < ALERT_COOLDOWN_SECONDS:
            return False, None

        # DISTRACTED 提醒
        if session.current_status == "distracted":
            # 刚进入走神状态（连续 tick = 1）且持续一定次数才提醒
            if session.consecutive_ticks >= DISTRACTED_ALERT_TICKS:
                # 首次提醒 or 冷却已过
                task_brief = session.task[:20] + "..." if len(session.task) > 20 else session.task
                page = meta.page_title or "其他页面"
                message = (
                    f"看起来你切到了「{page}」——还记得你的目标吗？\n"
                    f"📋 {task_brief}\n"
                    f"要回来继续吗？💪"
                )
                session.last_alert_at = now
                session.alert_count += 1
                return True, message

        # 从 AWAY 恢复 → 简短欢迎
        if session.current_status == "focused" and session.consecutive_ticks == 1:
            # 检查上一状态是否为 away（通过 segments 判断）
            if session.segments and session.segments[-1].get("status") == "away":
                message = "看到你回来了！继续加油～"
                session.last_alert_at = now
                session.alert_count += 1
                return True, message

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

    def generate_report(self, session_id: str) -> FocusReportResponse:
        """生成任务简报"""
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

        # 统计各状态时长（简化：按 segment 数量估算分钟数）
        focused_segments = [s for s in session.segments if s["status"] == "focused"]
        distracted_segments = [s for s in session.segments if s["status"] == "distracted"]
        away_segments = [s for s in session.segments if s["status"] == "away"]

        total_ticks = session.total_ticks
        focused_ticks = sum(
            session.consecutive_ticks if s["status"] == "focused" else 0
            for s in session.segments
        )

        # 估算分钟数（粗略：tick 数 × 30s / 60）
        total_min = max(1, round(total_ticks * 30 / 60))
        focused_min = max(0, round(len(focused_segments) * total_min / max(1, len(session.segments))))
        distracted_min = max(0, round(len(distracted_segments) * total_min / max(1, len(session.segments))))
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

        # 走神摘要
        distraction_notes = [s.get("note", "") for s in distracted_segments]
        distraction_summary = "、".join(distraction_notes[:3]) if distraction_notes else "无"

        # 构建建议
        suggestions = []
        if distracted_min > 5:
            suggestions.append(f"下次可以尝试在开始前关闭容易分心的网页和应用")
        if away_min > 5:
            suggestions.append("离开时间偏长，可以试试番茄工作法：25 分钟专注 + 5 分钟休息")
        if focused_min / max(1, total_min) > 0.7:
            suggestions.append("专注度不错！继续保持这个节奏 🎉")
        if not suggestions:
            suggestions.append("继续保持，你可以做得更好！")

        completion = (
            f"本次专注共 {total_min} 分钟，"
            f"其中专注约 {focused_min} 分钟，"
            f"走神约 {distracted_min} 分钟（{distraction_summary}），"
            f"离开约 {away_min} 分钟。"
        )

        summary = (
            f"在 {total_min} 分钟的专注会话中，"
            f"你保持了约 {focused_min} 分钟的专注状态。"
            + (f"中间有 {distracted_min} 分钟走神和 {away_min} 分钟离开。" if distracted_min + away_min > 0 else "表现很好！")
        )

        return FocusReportResponse(
            task=session.task,
            total_minutes=total_min,
            focused_minutes=focused_min,
            distracted_minutes=distracted_min,
            away_minutes=away_min,
            segments=segments_out,
            completion_assessment=completion,
            summary=summary,
            suggestions=suggestions,
        )


# ── 单例 ──
focus_service = FocusService()
