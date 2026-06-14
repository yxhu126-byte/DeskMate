"""语音转文字路由"""
import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from app.schemas.media import SpeechTranscribeResponse
from app.services.speech_to_text_service import speech_to_text_service

router = APIRouter(prefix="/api/speech", tags=["speech"])
logger = logging.getLogger(__name__)

_AUDIO_FORMAT_BY_MIME = {
    "audio/webm": "webm",
    "video/webm": "webm",
    "audio/ogg": "ogg",
    "application/ogg": "ogg",
    "audio/mp4": "mp4",
    "audio/x-m4a": "m4a",
    "audio/m4a": "m4a",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/flac": "flac",
    "audio/x-flac": "flac",
}
_SUPPORTED_AUDIO_EXTENSIONS = {
    "wav", "mp3", "m4a", "ogg", "flac", "webm", "mpga", "mpeg", "mp4", "oga"
}


def normalize_audio_format(filename: str | None, content_type: str | None) -> str:
    """根据上传 MIME 与文件名推断音频格式，优先信任浏览器提供的 content-type。"""
    if content_type:
        mime = content_type.split(";", 1)[0].strip().lower()
        if mime in _AUDIO_FORMAT_BY_MIME:
            return _AUDIO_FORMAT_BY_MIME[mime]

    if filename:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext in _SUPPORTED_AUDIO_EXTENSIONS:
            return ext

    return "webm"


@router.post("/transcribe", response_model=SpeechTranscribeResponse)
async def transcribe_speech(
    session_id: str = Form(...),
    audio: UploadFile = File(...),
):
    """
    语音转文字接口。

    接收音频文件，返回转写文本。
    支持的格式取决于后端 STT 服务 (Whisper 支持: flac, m4a, mp3, mp4,
    mpeg, mpga, oga, ogg, wav, webm)。
    """
    # 检查文件大小 (限制 10MB)
    audio_data = await audio.read()
    if len(audio_data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="音频文件不能超过 10MB")

    if len(audio_data) == 0:
        raise HTTPException(status_code=400, detail="音频文件为空")

    # 检测格式：优先使用浏览器上传的 content-type，再回退到文件扩展名
    audio_format = normalize_audio_format(audio.filename, audio.content_type)

    logger.info(
        f"收到语音转写请求: session={session_id[:8]}..., "
        f"大小={len(audio_data):,}B, filename={audio.filename}, "
        f"content_type={audio.content_type}, 格式={audio_format}"
    )

    try:
        result = await speech_to_text_service.transcribe(audio_data, audio_format)
        return result
    except Exception as e:
        logger.error(f"语音转写失败: {e}")
        raise HTTPException(status_code=500, detail=f"语音转写失败: {str(e)}")
