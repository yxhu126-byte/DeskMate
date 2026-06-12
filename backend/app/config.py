"""应用配置管理"""
import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """应用配置"""

    # 服务配置
    APP_NAME: str = "DeskMate AI 伴随助手"
    APP_VERSION: str = "1.0.0-demo"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS 配置 (前端地址)
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5500", "http://127.0.0.1:5500", "*"]

    # AI 模型配置
    AI_PROVIDER: str = "anthropic"  # "anthropic" | "openai" | "mock"
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_BASE_URL: Optional[str] = None   # 代理地址，如 "https://api.openai.com/v1"

    # 图片处理配置
    IMAGE_MAX_WIDTH: int = 1280
    IMAGE_MAX_HEIGHT: int = 1280
    IMAGE_QUALITY: int = 75
    IMAGE_FORMAT: str = "JPEG"

    # 会话配置
    MAX_RECENT_MESSAGES: int = 10
    SESSION_TTL_SECONDS: int = 1800  # 30 分钟

    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_SANITIZE_IMAGES: bool = True  # 禁止记录图片 base64

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
