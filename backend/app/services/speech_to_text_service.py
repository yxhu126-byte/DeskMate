"""语音转文字服务封装"""
import logging
from typing import Optional
import io

from app.config import settings
from app.schemas.media import SpeechTranscribeResponse

logger = logging.getLogger(__name__)


class SpeechToTextService:
    """语音转文字服务"""

    def __init__(self):
        self._provider = settings.AI_PROVIDER

    async def transcribe(self, audio_data: bytes, audio_format: str = "webm") -> SpeechTranscribeResponse:
        """
        将音频转为文本。

        MVP 阶段策略:
        - 如果配置了 OpenAI API，使用 Whisper API
        - 否则返回模拟结果（Demo 模式）
        """
        if self._provider == "mock":
            return await self._mock_transcribe()

        # 尝试使用 OpenAI Whisper API
        try:
            import openai
            client = openai.AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL or "https://api.openai.com/v1",
            )

            # Whisper API 支持的文件格式
            audio_file = io.BytesIO(audio_data)
            audio_file.name = f"recording.{audio_format}"

            response = await client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="json",
                language="zh",
            )

            return SpeechTranscribeResponse(
                text=response.text,
                confidence=getattr(response, 'confidence', 0.8),
                language="zh",
            )

        except Exception as e:
            logger.warning(f"STT 调用失败: {e}，降级为模拟模式")
            return await self._mock_transcribe()

    async def _mock_transcribe(self) -> SpeechTranscribeResponse:
        """Demo 模式: 返回占位文本"""
        return SpeechTranscribeResponse(
            text="[演示模式] 语音转写功能需要配置 OpenAI API Key",
            confidence=0.5,
            language="zh",
        )


speech_to_text_service = SpeechToTextService()
