"""多模态对话路由"""
import logging
from fastapi import APIRouter, HTTPException

from app.schemas.chat import MultimodalChatRequest, MultimodalChatResponse
from app.services.multimodal_ai_service import multimodal_ai_service
from app.services.session_context_service import session_context_service
from app.services.image_service import image_service
from app.services.privacy_service import privacy_service
from app.config import settings

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger(__name__)


@router.post("/multimodal", response_model=MultimodalChatResponse)
async def multimodal_chat(request: MultimodalChatRequest):
    """
    多模态对话接口。

    接收用户文本 + 可选图片 (屏幕截图/摄像头画面)，
    调用多模态 AI 返回回答。
    """
    # 1. 获取或创建会话
    session = session_context_service.get_or_create_session(request.session_id)

    # 2. 压缩图片 (如果有)
    compressed_images = []
    for img in request.images:
        try:
            result = image_service.compress(
                img.data,
                max_width=settings.IMAGE_MAX_WIDTH,
                max_height=settings.IMAGE_MAX_HEIGHT,
                quality=settings.IMAGE_QUALITY,
            )
            img.data = result["data"]
            compressed_images.append(img)
            session_context_service.track_image_upload(session.session_id, 1)
            logger.info(
                f"图片压缩: {result['original_size']:,}B → {result['compressed_size']:,}B "
                f"({result['width']}x{result['height']})"
            )
        except Exception as e:
            logger.error(f"图片处理失败: {e}")
            raise HTTPException(status_code=400, detail=f"图片处理失败: {str(e)}")

    request.images = compressed_images

    # 3. 检查图片可读性
    for img in compressed_images:
        readable, msg = image_service.is_likely_readable(img.data)
        if not readable:
            logger.warning(f"图片可读性警告: {msg}")

    # 4. 检查隐私提示需求
    if privacy_service.should_show_privacy_warning(request.user_text):
        logger.info(f"检测到可能的敏感内容查询 (会话: {request.session_id[:8]}...)")

    # 5. 构建会话上下文
    session_ctx = {
        "recent_messages": session.recent_messages,
        "active_mode": session.active_mode.value,
    }

    # 6. 调用 AI
    try:
        response = await multimodal_ai_service.chat(request, session_ctx)
    except Exception as e:
        logger.error(f"AI 调用失败: {e}")
        raise HTTPException(status_code=500, detail=f"AI 服务暂时不可用: {str(e)}")

    # 7. 保存到会话历史
    user_msg_summary = privacy_service.sanitize_log_text(request.user_text)
    session_context_service.add_message(
        session.session_id, "user", user_msg_summary,
        sources=response.used_sources
    )
    session_context_service.add_message(
        session.session_id, "assistant", response.answer,
        sources=response.used_sources
    )

    # 8. 脱敏处理日志中的回答
    safe_answer = privacy_service.sanitize_log_text(response.answer)

    # 9. 更新最后使用的输入源
    session.last_used_sources = response.used_sources
    session.last_screen_summary = safe_answer[:200]

    return response


@router.post("/clear")
async def clear_session(session_id: str):
    """清除指定会话"""
    success = session_context_service.delete_session(session_id)
    return {"success": success, "message": "会话已清除" if success else "会话不存在或已过期"}
