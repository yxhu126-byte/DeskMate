"""
火山引擎语音识别 (ASR) 服务封装

火山方舟的 API Key 用于大模型对话，语音识别需要单独开通：
1. 打开 https://console.volcengine.com/speech/app
2. 创建应用 → 获取 App ID 和 Access Token
3. 填入下方配置即可使用

两个 Key 各自独立，互不冲突：
- ARK_API_KEY → 大模型对话（/api/v3/chat/completions）
- ASR_APP_ID + ASR_ACCESS_TOKEN → 语音识别（openspeech.bytedance.com）
"""

import io
import json
import logging
from typing import Optional

import httpx

from app.config import settings
from app.schemas.media import SpeechTranscribeResponse

logger = logging.getLogger(__name__)

# 火山引擎语音识别 REST API 地址
ASR_API_URL = "https://openspeech.bytedance.com/api/v2/asr"


class VolcengineASRService:
    """火山引擎语音识别服务"""

    def __init__(self):
        self.app_id = settings.ASR_APP_ID
        self.access_token = settings.ASR_ACCESS_TOKEN
        self.resource_id = settings.ASR_RESOURCE_ID or "volc.bigasr.sauc.duration"

    @property
    def is_configured(self) -> bool:
        """检查是否已配置 ASR 凭证"""
        return bool(self.app_id and self.access_token)

    async def transcribe(
        self, audio_data: bytes, audio_format: str = "wav"
    ) -> Optional[SpeechTranscribeResponse]:
        """
        调用火山引擎 ASR 进行语音识别。

        Args:
            audio_data: 音频二进制数据
            audio_format: 音频格式 (wav, mp3, ogg 等)

        Returns:
            识别结果，失败返回 None
        """
        if not self.is_configured:
            logger.warning("ASR 未配置，跳过语音识别")
            return None

        headers = {
            "X-Api-App-Key": self.app_id,
            "X-Api-Access-Key": self.access_token,
            "X-Api-Resource-Id": self.resource_id,
        }

        # 构建请求元数据
        request_meta = {
            "app": {"appid": self.app_id},
            "user": {"uid": "deskmate-user"},
            "audio": {
                "format": audio_format,
                "rate": 16000,
                "bits": 16,
                "channel": 1,
            },
            "request": {
                "model_name": "bigmodel",  # 大模型版 ASR，识别效果更好
                "enable_punctuation": True,
                "enable_itn": True,  # 逆文本归一化（数字转阿拉伯数字等）
            },
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # multipart/form-data 上传
                files = {
                    "audio": (f"recording.{audio_format}", audio_data, f"audio/{audio_format}"),
                    "request": (None, json.dumps(request_meta, ensure_ascii=False), "application/json"),
                }

                resp = await client.post(ASR_API_URL, headers=headers, files=files)
                resp.raise_for_status()
                result = resp.json()

                logger.info(f"ASR 响应: {json.dumps(result, ensure_ascii=False)[:300]}")

                # 解析响应
                text = ""
                confidence = 0.0

                if "result" in result:
                    text = result["result"].get("text", "")
                elif "results" in result:
                    # 另一种响应格式
                    utterances = result.get("results", [{}])[0].get("utterances", [])
                    if utterances:
                        text = utterances[0].get("text", "")
                        confidence = utterances[0].get("confidence", 0.0)

                if not text:
                    logger.warning(f"ASR 返回空文本: {json.dumps(result, ensure_ascii=False)[:200]}")
                    return None

                return SpeechTranscribeResponse(
                    text=text,
                    confidence=confidence,
                    language="zh",
                )

        except httpx.HTTPStatusError as e:
            logger.error(f"ASR HTTP 错误: {e.response.status_code} - {e.response.text[:300]}")
            return None
        except Exception as e:
            logger.error(f"ASR 调用异常: {e}")
            return None


volcengine_asr_service = VolcengineASRService()
