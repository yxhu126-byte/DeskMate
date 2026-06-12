"""会话相关数据模型"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class SessionMode(str, Enum):
    GENERAL = "general"
    LEARNING = "learning"
    OFFICE = "office"
    CODING = "coding"


class SessionState(BaseModel):
    """会话状态"""
    session_id: str
    created_at: datetime = Field(default_factory=datetime.now)
    last_active_at: datetime = Field(default_factory=datetime.now)
    active_mode: SessionMode = SessionMode.GENERAL
    recent_messages: list[dict] = Field(default_factory=list, description="最近几轮对话")
    last_screen_summary: Optional[str] = Field(default=None, description="上一轮屏幕内容摘要")
    last_camera_summary: Optional[str] = Field(default=None, description="上一轮摄像头内容摘要")
    last_used_sources: list[str] = Field(default_factory=list)
    image_count: int = Field(default=0, description="本次会话累计上传图片数")
    estimated_cost: float = Field(default=0.0, description="本次会话累计估算成本 (USD)")

    def add_message(self, role: str, content: str, sources: Optional[list[str]] = None):
        """添加一条对话记录，自动裁剪历史"""
        self.recent_messages.append({
            "role": role,
            "content": content,
            "sources": sources or []
        })
        # 保留最近 N 条
        if len(self.recent_messages) > 20:
            self.recent_messages = self.recent_messages[-20:]
        self.last_active_at = datetime.now()
