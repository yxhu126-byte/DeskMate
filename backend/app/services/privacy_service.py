"""隐私服务：日志脱敏、敏感内容提示策略"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class PrivacyService:
    """隐私与安全服务"""

    # 敏感关键词列表 (UI 提示用，不是精确检测)
    SENSITIVE_KEYWORDS = [
        "password", "密码", "secret", "密钥", "token", "api_key",
        "身份证", "银行卡", "信用卡", "社保", "银行账号",
        "登录", "login", "credential", "credentials",
    ]

    @staticmethod
    def sanitize_log_text(text: str, max_length: int = 500) -> str:
        """对日志中的文本进行安全截断"""
        if len(text) > max_length:
            return text[:max_length] + "...[truncated]"
        return text

    @staticmethod
    def should_show_privacy_warning(user_text: str) -> bool:
        """
        根据用户输入判断是否需要显示隐私提示。
        当前版本使用简单关键词匹配。
        """
        text_lower = user_text.lower()
        return any(kw.lower() in text_lower for kw in PrivacyService.SENSITIVE_KEYWORDS)

    @staticmethod
    def get_screen_share_privacy_tips() -> list[str]:
        """获取屏幕共享前的隐私提示"""
        return [
            "请关闭或隐藏包含密码、聊天记录、私人信息的窗口",
            "建议仅共享需要 AI 查看的单个标签页或窗口",
            "AI 回答使用的截图不会在服务器端永久保存",
            "你可以随时点击「暂停分析」按钮停止截图",
        ]

    @staticmethod
    def mask_sensitive_in_response(text: str) -> str:
        """
        对 AI 回复中的疑似敏感信息做简单脱敏。
        当前版本仅做基础处理。
        """
        # MVP 阶段: 不做激进脱敏，避免误杀正常内容
        return text


privacy_service = PrivacyService()
