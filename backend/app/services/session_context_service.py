"""会话上下文管理服务"""
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional

from app.config import settings
from app.schemas.session import SessionState, SessionMode

logger = logging.getLogger(__name__)


class SessionContextService:
    """会话上下文管理"""

    def __init__(self):
        self._sessions: dict[str, SessionState] = {}

    def create_session(self, mode: SessionMode = SessionMode.GENERAL) -> SessionState:
        """创建新会话"""
        session_id = str(uuid.uuid4())
        session = SessionState(
            session_id=session_id,
            active_mode=mode,
        )
        self._sessions[session_id] = session
        logger.info(f"创建会话: {session_id}, 模式: {mode.value}")
        return session

    def get_session(self, session_id: str) -> Optional[SessionState]:
        """获取会话，不存在时返回 None"""
        session = self._sessions.get(session_id)
        if session is None:
            return None
        # 检查是否过期
        if datetime.now() - session.last_active_at > timedelta(seconds=settings.SESSION_TTL_SECONDS):
            logger.info(f"会话已过期: {session_id}")
            del self._sessions[session_id]
            return None
        return session

    def get_or_create_session(self, session_id: Optional[str] = None) -> SessionState:
        """获取或创建会话"""
        if session_id:
            session = self.get_session(session_id)
            if session:
                return session
        return self.create_session()

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"删除会话: {session_id}")
            return True
        return False

    def update_mode(self, session_id: str, mode: SessionMode) -> Optional[SessionState]:
        """更新会话模式"""
        session = self.get_session(session_id)
        if session:
            session.active_mode = mode
            session.last_active_at = datetime.now()
        return session

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        sources: Optional[list[str]] = None,
    ) -> Optional[SessionState]:
        """向会话添加一条消息"""
        session = self.get_session(session_id)
        if session:
            session.add_message(role, content, sources)
        return session

    def track_image_upload(self, session_id: str, image_count: int = 1):
        """跟踪图片上传"""
        session = self.get_session(session_id)
        if session:
            session.image_count += image_count

    def cleanup_expired(self):
        """清理所有过期会话"""
        now = datetime.now()
        expired = [
            sid for sid, s in self._sessions.items()
            if now - s.last_active_at > timedelta(seconds=settings.SESSION_TTL_SECONDS)
        ]
        for sid in expired:
            del self._sessions[sid]
        if expired:
            logger.info(f"清理了 {len(expired)} 个过期会话")


session_context_service = SessionContextService()
