"""多模态 AI 服务：封装大模型调用，支持 Anthropic / OpenAI / Mock 三种后端"""
import base64
import json
import logging
import time
from typing import Optional

from app.config import settings
from app.schemas.chat import (
    MultimodalChatRequest,
    MultimodalChatResponse,
    SceneMode,
    InputSource,
)
from app.services.image_service import image_service
from app.services.privacy_service import privacy_service

logger = logging.getLogger(__name__)

# ── 系统提示词（按场景模式） ──────────────────────────────────────────

BASE_PROMPT = """你是一个网页端 AI 多模态伴随助手，名叫「桌面伴侣」。

你的核心能力：
- 查看用户分享的屏幕截图，理解用户正在做的事情
- 查看用户摄像头画面，理解用户面前的现实环境
- 听取用户的语音问题，给出有帮助的回复

重要规则：
1. 如果你看不清图片中的内容（文字太小、模糊、光线不足），必须明确告诉用户，并建议调整
2. 不要对你无法确认的内容做绝对判断
3. 优先提供思路和方向，而不是直接给答案（尤其是学习场景）
4. 回答应简洁、具体、可执行
5. 用中文回答"""

SCENE_PROMPTS = {
    SceneMode.GENERAL: BASE_PROMPT,
    SceneMode.LEARNING: BASE_PROMPT + """

当前处于「学习模式」：
- 优先讲解思路和原理，引导用户自己得出答案
- 对题目类内容，先分析已知条件，再引导解题步骤
- 对概念类内容，用通俗语言解释核心思想
- 如果用户看起来困惑，可以建议分步骤学习""",

    SceneMode.OFFICE: BASE_PROMPT + """

当前处于「办公模式」：
- 优先帮助总结、优化结构和表达
- 对文档/邮件，关注语气、逻辑、结构
- 对 PPT，关注信息密度、排版、视觉层次
- 给出具体可执行的建议，而不是抽象评价""",

    SceneMode.CODING: BASE_PROMPT + """

当前处于「编程模式」：
- 优先解释代码逻辑和报错原因
- 给出修改建议和示例代码
- 对报错信息，定位到具体行号和原因
- 如果截图分辨率不足导致看不清代码，提醒用户放大终端或 IDE 窗口
- 注意区分语法错误、逻辑错误和运行时错误""",
}


class MultimodalAIService:
    """多模态 AI 服务"""

    def __init__(self):
        self._provider = settings.AI_PROVIDER

    async def chat(
        self,
        request: MultimodalChatRequest,
        session_context: Optional[dict] = None,
    ) -> MultimodalChatResponse:
        """
        处理多模态对话请求。
        """
        start_time = time.time()

        # 1. 构建 system prompt
        system_prompt = SCENE_PROMPTS.get(request.mode, BASE_PROMPT)

        # 2. 构建完整的多模态用户消息
        user_content = self._build_multimodal_content(request, session_context)

        # 3. 调用 AI
        if self._provider == "mock":
            answer = self._mock_response(request)
        elif self._provider == "anthropic":
            answer = await self._call_anthropic(system_prompt, user_content)
        elif self._provider == "openai":
            answer = await self._call_openai(system_prompt, user_content)
        else:
            answer = self._mock_response(request)

        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(
            f"AI 调用完成, 耗时: {elapsed_ms:.0f}ms, "
            f"模式: {request.mode.value}, 图片数: {len(request.images)}"
        )

        # 4. 构建响应：screen/camera 只按实际图片计算，voice 按本次语音转写标记计算
        used_sources = self._derive_used_sources(request)

        uncertainty = self._check_uncertainty(request, answer)

        return MultimodalChatResponse(
            answer=answer,
            used_sources=used_sources,
            uncertainty=uncertainty,
            suggestions=self._generate_suggestions(request),
        )

    def _derive_used_sources(self, request: MultimodalChatRequest) -> list[str]:
        sources = []
        image_types = {img.type for img in request.images}

        if "screen" in image_types:
            sources.append("screen")
        if "camera" in image_types:
            sources.append("camera")
        if request.input_sources.microphone:
            sources.append("voice")

        return sources

    def _build_multimodal_content(
        self,
        request: MultimodalChatRequest,
        session_context: Optional[dict] = None,
    ) -> list[dict]:
        """
        构建完整的多模态用户消息，包含：
        - 可选的对话历史
        - 文本问题
        - 图片 (屏幕截图、摄像头画面)
        """
        content = []

        # ── 对话历史 (纯文本) ──
        if session_context and session_context.get("recent_messages"):
            recent = session_context["recent_messages"][-6:]
            context_parts = ["【最近的对话历史】"]
            for msg in recent:
                role_label = "用户" if msg["role"] == "user" else "桌面伴侣"
                context_parts.append(f"{role_label}: {msg['content'][:300]}")
            context_parts.append("【当前问题】")
            content.append({
                "type": "text",
                "text": "\n".join(context_parts) + "\n",
            })

        # ── 输入源标注 ──
        source_desc = []
        image_types = {img.type for img in request.images}
        if "screen" in image_types:
            source_desc.append("📺 屏幕截图")
        if "camera" in image_types:
            source_desc.append("📷 摄像头画面")
        if request.input_sources.microphone:
            source_desc.append("🎤 语音输入")

        source_tag = ""
        if source_desc:
            source_tag = f"[输入源: {', '.join(source_desc)}]\n\n"

        # ── 用户文本问题 ──
        content.append({
            "type": "text",
            "text": source_tag + request.user_text,
        })

        # ── 图片 ──
        for img in request.images:
            # 去除可能的 data: URI 前缀
            image_data = img.data
            if "," in image_data and image_data.startswith("data:"):
                image_data = image_data.split(",", 1)[1]

            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": img.mime_type,
                    "data": image_data,
                },
            })

        return content

    async def _call_anthropic(
        self, system_prompt: str, user_content: list[dict]
    ) -> str:
        """调用 Anthropic Claude API"""
        try:
            import anthropic

            client = anthropic.AsyncAnthropic(
                api_key=settings.ANTHROPIC_API_KEY,
                auth_token=settings.ANTHROPIC_AUTH_TOKEN,
                base_url=settings.ANTHROPIC_BASE_URL or None,
            )

            response = await client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=2048,
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}],
            )

            return response.content[0].text

        except Exception as e:
            logger.error(f"Anthropic API 调用失败: {e}")
            raise

    async def _call_openai(
        self, system_prompt: str, user_content: list[dict]
    ) -> str:
        """调用 OpenAI GPT-4o API"""
        try:
            import openai

            client = openai.AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL or "https://api.openai.com/v1",
            )

            # 将 Anthropic 格式的图片内容转为 OpenAI 格式
            openai_content = []
            for block in user_content:
                if block["type"] == "text":
                    openai_content.append(block)
                elif block["type"] == "image":
                    openai_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{block['source']['media_type']};base64,{block['source']['data']}",
                            "detail": "auto",
                        },
                    })

            response = await client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": openai_content},
                ],
                max_tokens=2048,
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"OpenAI API 调用失败: {e}")
            raise

    def _mock_response(self, request: MultimodalChatRequest) -> str:
        """Demo 模式: 返回模拟回答"""
        mode_responses = {
            SceneMode.CODING: (
                "从你的屏幕截图看，这是一个 Python 的 NameError 报错。\n\n"
                "**错误原因**：你在第 12 行使用了变量 `result`，但在此之前没有给它赋值。\n\n"
                "**建议修改**：\n"
                "1. 检查变量名是否拼写正确\n"
                "2. 确保在使用 `result` 之前已经对它进行了赋值\n"
                "3. 如果这个变量应该从一个函数返回，检查函数是否有 return 语句\n\n"
                "如果截图中的代码文字较小，建议你放大 IDE 窗口或终端后再截一次，我可以给出更精确的定位。"
            ),
            SceneMode.LEARNING: (
                "看到你屏幕上的内容了。让我按照学习模式来讲讲思路：\n\n"
                "**首先**，我们先理解题目问的是什么；\n"
                "**然后**，我们找出题目给出的已知条件；\n"
                "**接着**，我们判断这属于哪个知识点；\n"
                "**最后**，我们一步步推导答案。\n\n"
                "如果图中内容不够清晰，请放大页面后告诉我，我会重新分析。"
            ),
            SceneMode.OFFICE: (
                "我已经查看了你当前的屏幕内容。以下是我的分析和建议：\n\n"
                "1. **整体结构**：当前文档的结构清晰，逻辑流程合理\n"
                "2. **表达优化**：部分段落可以更加简洁，建议突出重点\n"
                "3. **下一步行动**：建议先完成核心内容，再回头调整格式\n\n"
                "如果需要针对具体部分给出修改建议，可以告诉我。"
            ),
            SceneMode.GENERAL: (
                "我已经看到了你分享的屏幕内容。\n\n"
                "根据当前的画面，我理解你正在浏览/编辑内容。如果你有具体的问题，"
                "可以直接告诉我，我会根据画面内容给你更有针对性的回答。\n\n"
                "💡 提示：你可以通过语音或文字直接问我「这页在讲什么？」「这个报错是什么意思？」等问题。"
            ),
        }
        return mode_responses.get(request.mode, mode_responses[SceneMode.GENERAL])

    def _check_uncertainty(
        self, request: MultimodalChatRequest, answer: str
    ) -> Optional[str]:
        """检查 AI 回答中是否表达了不确定性"""
        uncertainty_signals = [
            "看不清", "不太清楚", "无法确认", "可能不准确",
            "截图不够清晰", "可能", "似乎", "也许",
        ]
        for signal in uncertainty_signals:
            if signal in answer:
                return "截图中部分内容不够清晰，建议放大目标区域后重新截图，或提供更多上下文。"
        return None

    def _generate_suggestions(self, request: MultimodalChatRequest) -> list[str]:
        """根据场景生成建议的后续操作"""
        suggestions = []
        if any(img.type == "screen" for img in request.images):
            suggestions.append("你可以放大关键区域后重新截图提问")
        if request.mode == SceneMode.CODING:
            suggestions.append("尝试切换到高精度模式以获取更清晰的代码截图")
        return suggestions


    # ══════════════════════════════════════════════════════════
    # 专注陪伴模式 (Focus Companion) — AI 方法
    # ══════════════════════════════════════════════════════════

    async def focus_check_relevance(
        self, task: str, image_base64: str, page_title: Optional[str] = None
    ) -> dict:
        """
        调用 AI 判断屏幕截图是否与用户任务相关。

        Returns:
            {"related": bool, "activity": str, "confidence": float}
        """
        title_hint = f"页面标题: {page_title}" if page_title else ""

        prompt = f"""用户设定的任务: "{task}"
{title_hint}

请判断这张屏幕截图的内容是否与用户任务相关:
1. 截图显示用户在做什么？
2. 这跟「{task}」有关系吗？

用 JSON 回答（仅 JSON，无其他文字）:
{{"related": true或false, "activity": "简短描述(10字以内)", "confidence": 0.0到1.0}}

注意: 查资料/看文档/搜索技术问题 → related=true; 社交媒体/视频/游戏/购物 → related=false; 看不清 → related=true"""

        if self._provider == "mock":
            return await self._mock_focus_relevance(image_base64, page_title)

        try:
            if self._provider == "anthropic":
                return await self._call_anthropic_focus_relevance(prompt, image_base64)
            elif self._provider == "openai":
                return await self._call_openai_focus_relevance(prompt, image_base64)
        except Exception as e:
            logger.error(f"Focus relevance check failed: {e}, falling back to rules")
            return await self._mock_focus_relevance(image_base64, page_title)

        return await self._mock_focus_relevance(image_base64, page_title)

    async def focus_generate_alert(
        self, task: str, elapsed_minutes: int, current_activity: str,
        distracted_minutes: int
    ) -> str:
        """
        调用 AI 生成走神提醒文案。

        Returns:
            提醒文本（不超过 40 字）
        """
        prompt = f"""用户任务: "{task}"
已进行: {elapsed_minutes} 分钟
用户当前在: {current_activity}（与任务不相关）
已连续偏离: 约 {distracted_minutes} 分钟

请用一句话温和提醒用户回到任务。要求:
- 朋友式关心，不指责
- 不使用"你又在摸鱼""总是分心"等负面表达
- 可以带一点幽默感，但不轻浮
- 不超过 40 个字
- 仅输出提醒文本，无其他内容"""

        if self._provider == "mock":
            return self._mock_focus_alert(task, current_activity)

        try:
            if self._provider == "anthropic":
                response = await self._call_anthropic_simple(prompt)
            elif self._provider == "openai":
                response = await self._call_openai_simple(prompt)
            else:
                response = self._mock_focus_alert(task, current_activity)
            return response.strip()[:120]  # 安全截断
        except Exception as e:
            logger.error(f"Focus alert generation failed: {e}")
            return self._mock_focus_alert(task, current_activity)

    async def focus_generate_report(
        self, task: str, total_min: int, focused_min: int,
        distracted_min: int, away_min: int, timeline_text: str
    ) -> dict:
        """
        调用 AI 生成专注简报。

        Returns:
            {"completion_assessment": str, "summary": str, "suggestions": list[str]}
        """
        prompt = f"""用户任务: "{task}"
总时长: {total_min} 分钟
专注: {focused_min} 分钟 | 走神: {distracted_min} 分钟 | 离开: {away_min} 分钟

时间线:
{timeline_text}

请生成一份任务简报。用 JSON 回答（仅 JSON）:
{{"completion_assessment": "任务完成度评估(1-2句)",
  "summary": "专注情况总结(1-2句)",
  "suggestions": ["建议1", "建议2"]}}

要求: 温暖鼓励; 如果专注度好要真诚表扬; 如果走神多要温和给建议。"""

        if self._provider == "mock":
            return self._mock_focus_report(task, total_min, focused_min, distracted_min, away_min)

        try:
            if self._provider == "anthropic":
                result_text = await self._call_anthropic_simple(prompt)
            elif self._provider == "openai":
                result_text = await self._call_openai_simple(prompt)
            else:
                return self._mock_focus_report(task, total_min, focused_min, distracted_min, away_min)

            # Parse JSON from AI response
            import re
            json_match = re.search(r'\{[\s\S]*\}', result_text)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    "completion_assessment": result.get("completion_assessment", ""),
                    "summary": result.get("summary", ""),
                    "suggestions": result.get("suggestions", []),
                }
        except Exception as e:
            logger.error(f"Focus report generation failed: {e}")

        return self._mock_focus_report(task, total_min, focused_min, distracted_min, away_min)

    # ── AI 提供商实现 ──

    async def _call_anthropic_focus_relevance(self, prompt: str, image_base64: str) -> dict:
        import anthropic
        client = anthropic.AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            auth_token=settings.ANTHROPIC_AUTH_TOKEN,
            base_url=settings.ANTHROPIC_BASE_URL or None,
        )
        content = [
            {"type": "text", "text": prompt},
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_base64}},
        ]
        response = await client.messages.create(
            model=settings.ANTHROPIC_MODEL, max_tokens=256,
            messages=[{"role": "user", "content": content}],
        )
        return self._parse_relevance_json(response.content[0].text)

    async def _call_openai_focus_relevance(self, prompt: str, image_base64: str) -> dict:
        import openai
        client = openai.AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL or "https://api.openai.com/v1",
        )
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL, max_tokens=256,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {
                    "url": f"data:image/jpeg;base64,{image_base64}", "detail": "low"
                }},
            ]}],
        )
        return self._parse_relevance_json(response.choices[0].message.content)

    async def _call_anthropic_simple(self, prompt: str) -> str:
        import anthropic
        client = anthropic.AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            auth_token=settings.ANTHROPIC_AUTH_TOKEN,
            base_url=settings.ANTHROPIC_BASE_URL or None,
        )
        response = await client.messages.create(
            model=settings.ANTHROPIC_MODEL, max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    async def _call_openai_simple(self, prompt: str) -> str:
        import openai
        client = openai.AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL or "https://api.openai.com/v1",
        )
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL, max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    def _parse_relevance_json(self, text: str) -> dict:
        """安全解析 AI 返回的 relevance JSON"""
        import re
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                result = json.loads(json_match.group())
                return {
                    "related": bool(result.get("related", True)),
                    "activity": str(result.get("activity", ""))[:20],
                    "confidence": float(result.get("confidence", 0.5)),
                }
            except (json.JSONDecodeError, ValueError, TypeError):
                pass
        # 解析失败 → 默认 related=true（不误判）
        return {"related": True, "activity": "无法判断", "confidence": 0.5}

    # ── Mock 降级实现 ──

    async def _mock_focus_relevance(self, image_base64: str, page_title: Optional[str]) -> dict:
        """Mock 模式: 使用关键词规则判断"""
        if not page_title:
            return {"related": True, "activity": "工作中", "confidence": 0.5}

        DISTRACTION_KW = [
            "视频", "游戏", "直播", "微博", "知乎", "贴吧", "抖音",
            "bilibili", "B站", "youtube", "YouTube", "netflix",
            "漫画", "小说", "购物", "淘宝", "京东",
        ]
        for kw in DISTRACTION_KW:
            if kw.lower() in page_title.lower():
                return {"related": False, "activity": page_title[:20], "confidence": 0.8}

        return {"related": True, "activity": page_title[:20], "confidence": 0.6}

    def _mock_focus_alert(self, task: str, current_activity: str) -> str:
        """Mock 模式: 模板化提醒文案"""
        task_brief = task[:15] + "..." if len(task) > 15 else task
        return f"看起来你去「{current_activity}」了——「{task_brief}」还在等你呢，要回来继续吗？💪"

    def _mock_focus_report(
        self, task: str, total_min: int, focused_min: int,
        distracted_min: int, away_min: int
    ) -> dict:
        """Mock 模式: 模板化简报"""
        pct = round(focused_min / max(1, total_min) * 100)
        if pct >= 80:
            assessment = f"表现优秀！{total_min} 分钟里 {pct}% 都在专注，任务推进很扎实。"
        elif pct >= 60:
            assessment = f"整体不错，{pct}% 的时间在专注任务。"
        else:
            assessment = f"这次专注度偏低，{pct}% 时间在任务上，可以试试减少干扰。"

        summary_parts = [f"在 {total_min} 分钟的专注时段中，你保持了 {focused_min} 分钟的专注。"]
        if distracted_min > 0:
            summary_parts.append(f"中间有 {distracted_min} 分钟走神。")
        if away_min > 0:
            summary_parts.append(f"离开了 {away_min} 分钟。")

        suggestions = []
        if distracted_min > 5:
            suggestions.append("开始专注前，先关闭容易分心的网页和应用")
        if away_min > 5:
            suggestions.append("可以试试番茄工作法：25 分钟专注 + 5 分钟休息")
        if pct >= 80:
            suggestions.append("专注度很棒，继续保持这个节奏！🎉")
        suggestions.append("试试在开始前把手机放到另一个房间")

        return {
            "completion_assessment": assessment,
            "summary": "".join(summary_parts),
            "suggestions": suggestions,
        }


multimodal_ai_service = MultimodalAIService()
