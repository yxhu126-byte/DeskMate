"""语音转文字路由"""
import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from app.schemas.media import SpeechTranscribeResponse
from app.services.speech_to_text_service import speech_to_text_service

router = APIRouter(prefix="/api/speech", tags=["speech"])
logger = logging.getLogger(__name__)


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

    # 检测格式
    audio_format = "webm"
    if audio.filename:
        ext = audio.filename.rsplit(".", 1)[-1].lower() if "." in audio.filename else ""
        if ext in ("wav", "mp3", "m4a", "ogg", "flac", "webm", "mpga", "mpeg", "mp4", "oga"):
            audio_format = ext

    logger.info(
        f"收到语音转写请求: session={session_id[:8]}..., "
        f"大小={len(audio_data):,}B, 格式={audio_format}"
    )

    try:
        result = await speech_to_text_service.transcribe(audio_data, audio_format)
        return result
    except Exception as e:
        logger.error(f"语音转写失败: {e}")
        raise HTTPException(status_code=500, detail=f"语音转写失败: {str(e)}")
