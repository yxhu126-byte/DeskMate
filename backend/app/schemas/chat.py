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
