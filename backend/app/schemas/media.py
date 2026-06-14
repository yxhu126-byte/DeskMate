"""媒体相关数据模型"""
from pydantic import BaseModel, Field


class SpeechTranscribeRequest(BaseModel):
    """语音转文字请求 (元数据通过 multipart 传递)"""
    session_id: str = Field(..., description="会话 ID")


class SpeechTranscribeResponse(BaseModel):
    """语音转文字响应"""
    text: str = Field(..., description="转写文本")
    confidence: float = Field(default=0.0, description="置信度 0-1")
    language: str = Field(default="zh", description="识别到的语言")
    provider: str | None = Field(default=None, description="实际使用的转写服务")
    status: str = Field(default="ok", description="ok | not_configured | failed | empty")
    message: str | None = Field(default=None, description="面向前端的状态说明")


class ImageCompressResult(BaseModel):
    """图片压缩结果"""
    original_size: int = Field(..., description="原始体积 (bytes)")
    compressed_size: int = Field(..., description="压缩后体积 (bytes)")
    width: int
    height: int
    format: str
    quality: int
    data: str = Field(..., description="base64 编码的压缩后图片")
