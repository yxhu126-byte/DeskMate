"""语音转文字服务封装（多后端：火山引擎 ASR > OpenAI Whisper > Mock）"""
import logging
from typing import Optional
import io

from app.config import settings
from app.schemas.media import SpeechTranscribeResponse
from app.services.volcengine_asr_service import volcengine_asr_service

logger = logging.getLogger(__name__)


class SpeechToTextService:
    """语音转文字服务

    优先级：
    1. 火山引擎 ASR（需配置 ASR_APP_ID + ASR_ACCESS_TOKEN）
    2. OpenAI Whisper API（需配置 OPENAI_API_KEY + 标准 base_url）
    3. 返回空文本 → 前端提示用户手动输入
    """

    def __init__(self):
        self._provider = settings.AI_PROVIDER

    async def transcribe(
        self, audio_data: bytes, audio_format: str = "webm"
    ) -> SpeechTranscribeResponse:
        """将音频转为文本"""

        # 策略 1: 优先尝试火山引擎 ASR
        if volcengine_asr_service.is_configured:
            # 格式映射：火山 ASR 支持 wav/pcm/mp3/ogg_opus/aac/m4a/flac
            _asr_format = audio_format
            if audio_format in ("ogg", "oga", "webm"):
                _asr_format = "ogg_opus"
            logger.info(f"使用火山引擎 ASR 进行语音识别 (格式: {_asr_format})...")
            result = await volcengine_asr_service.transcribe(audio_data, _asr_format)
            if result and result.text.strip():
                logger.info(f"ASR 识别成功: {result.text[:50]}...")
                result.provider = "volcengine"
                result.status = "ok"
                return result
            logger.warning("火山引擎 ASR 未返回有效结果")

        # 策略 2: 仅在 OpenAI Key 存在且 Base URL 支持 Whisper 时尝试
        if settings.OPENAI_API_KEY:
            base_url = (settings.OPENAI_BASE_URL or "").lower()
            if "volces.com" in base_url:
                logger.info("当前 OpenAI Base URL 为火山方舟，不支持 Whisper API，跳过降级")
            else:
                if volcengine_asr_service.is_configured:
                    logger.info("尝试降级到 OpenAI Whisper 进行语音识别...")
                result = await self._try_openai_whisper(audio_data, audio_format)
                if result and result.text.strip():
                    return result
                logger.warning("OpenAI Whisper 未返回有效结果")

        # 策略 3: 返回空文本（前端将提示用户手动输入）
        if volcengine_asr_service.is_configured or settings.OPENAI_API_KEY:
            logger.warning("已配置的语音转写服务均未返回有效结果")
            return SpeechTranscribeResponse(
                text="",
                confidence=0.0,
                language="zh",
                provider=None,
                status="failed",
                message="语音转写失败，请重试或手动输入问题",
            )

        logger.info("语音转写服务未配置，返回空文本（前端将引导用户手动输入）")
        return SpeechTranscribeResponse(
            text="",
            confidence=0.0,
            language="zh",
            provider=None,
            status="not_configured",
            message="语音转写未配置，请手动输入问题",
        )

    async def _try_openai_whisper(
        self, audio_data: bytes, audio_format: str
    ) -> Optional[SpeechTranscribeResponse]:
        """尝试 OpenAI Whisper API"""
        try:
            import openai

            client = openai.AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL or "https://api.openai.com/v1",
            )

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
                confidence=getattr(response, "confidence", 0.8),
                language="zh",
                provider="openai_whisper",
                status="ok",
            )

        except Exception as e:
            logger.warning(f"Whisper API 不可用: {e}")
            return None


speech_to_text_service = SpeechToTextService()
