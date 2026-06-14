"""对话相关数据模型"""
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class InputSource(str, Enum):
    SCREEN = "screen"
    CAMERA = "camera"
    MICROPHONE = "microphone"


class SceneMode(str, Enum):
    GENERAL = "general"
    LEARNING = "learning"
    OFFICE = "office"
    CODING = "coding"


class ImageInput(BaseModel):
    """图片输入"""
    type: str = Field(..., description="screen | camera")
    mime_type: str = Field(default="image/jpeg", description="图片 MIME 类型")
    data: str = Field(..., description="base64 编码的图片数据")


class InputSources(BaseModel):
    """输入源标记"""
    screen: bool = False
    camera: bool = False
    microphone: bool = False


class MultimodalChatRequest(BaseModel):
    """多模态对话请求"""
    session_id: str = Field(..., description="会话 ID (UUID)")
    user_text: str = Field(..., description="用户文本问题")
    mode: SceneMode = Field(default=SceneMode.GENERAL, description="场景模式")
    input_sources: InputSources = Field(default_factory=InputSources, description="使用的输入源")
    images: list[ImageInput] = Field(default_factory=list, description="截取的图片列表")


class MultimodalChatResponse(BaseModel):
    """多模态对话响应"""
    answer: str = Field(..., description="AI 回答文本")
    used_sources: list[str] = Field(default_factory=list, description="本次回答依据: screen/camera/voice")
    uncertainty: Optional[str] = Field(default=None, description="AI 对回答不确定性的说明")
    suggestions: list[str] = Field(default_factory=list, description="建议的后续操作")


class ChatMessage(BaseModel):
    """单条对话消息"""
    role: str  # user | assistant
    content: str
    sources: Optional[list[str]] = None


# ══════════════════════════════════════════════════════════
# 专注陪伴模式 (Focus Companion) 数据模型
# ══════════════════════════════════════════════════════════

class FocusTickMetadata(BaseModel):
    """专注模式 — 单次 tick 的元数据"""
    tick_index: int = Field(..., description="第几次 tick（从 1 开始）")
    seconds_elapsed: int = Field(..., description="专注已进行秒数")
    page_title: Optional[str] = Field(default=None, description="当前页面标题")
    frame_hash: str = Field(..., description="前端计算的感知哈希值")
    idle_seconds: int = Field(default=0, description="用户无操作秒数")


class FocusTickRequest(BaseModel):
    """专注模式 — 单次 tick 请求"""
    session_id: str = Field(..., description="会话 ID")
    task: str = Field(..., description="用户设定的任务描述")
    screen_frame: ImageInput = Field(..., description="当前屏幕帧")
    metadata: FocusTickMetadata = Field(..., description="tick 元数据")


class FocusTickResponse(BaseModel):
    """专注模式 — 单次 tick 响应"""
    status: str = Field(default="focused", description="当前状态: focused | distracted | away | returned")
    should_alert: bool = Field(default=False, description="是否需要提醒用户")
    alert_message: Optional[str] = Field(default=None, description="提醒文本")
    ai_note: Optional[str] = Field(default=None, description="AI 内部记录（不展示给用户）")


class FocusSegment(BaseModel):
    """专注模式 — 一个时段记录"""
    start_time: str = Field(..., description="时段开始时间（ISO 格式）")
    end_time: Optional[str] = Field(default=None, description="时段结束时间")
    status: str = Field(..., description="focused | distracted | away")
    note: Optional[str] = Field(default=None, description="AI 备注")


class FocusReportRequest(BaseModel):
    """专注模式 — 简报请求"""
    session_id: str = Field(..., description="会话 ID")


class FocusReportResponse(BaseModel):
    """专注模式 — 简报响应"""
    task: str = Field(default="", description="用户任务描述")
    total_minutes: int = Field(default=0, description="总时长（分钟）")
    focused_minutes: int = Field(default=0, description="专注时长（分钟）")
    distracted_minutes: int = Field(default=0, description="走神时长（分钟）")
    away_minutes: int = Field(default=0, description="离开时长（分钟）")
    segments: list[FocusSegment] = Field(default_factory=list, description="时段列表")
    completion_assessment: str = Field(default="", description="任务完成度评估")
    summary: str = Field(default="", description="AI 总结")
    suggestions: list[str] = Field(default_factory=list, description="建议列表")
