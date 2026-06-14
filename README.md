页# DeskMate — 网页端 AI 多模态伴随助手

> V1 Demo：验证「浏览器媒体采集 → 多模态 AI 问答」核心链路

---

## 🎬 Demo 演示视频

> 📺 **点击观看 DeskMate V1 功能演示**：[![Bilibili](https://img.shields.io/badge/Bilibili-DeskMate%20Demo-blue?logo=bilibili)](https://www.bilibili.com/video/BV1f1JK6eE2X/)

🔗 视频链接：https://www.bilibili.com/video/BV1f1JK6eE2X/

---

## 项目概述

DeskMate 是一个运行在网页中的 AI 多模态伴随助手。用户主动授权摄像头、麦克风和屏幕共享后，AI 能够：

- 📺 理解用户当前电脑屏幕中的任务内容
- 📷 看到用户摄像头中的现实环境
- 🎤 听懂用户的语音问题
- 🤖 结合以上信息给出针对性回答

**V1 定位**：打通核心技术链路，证明「用户授权 → 截图 → 多模态 AI → 回答」闭环可用。

---

## 项目结构

```
PythonProject5/
├── backend/                          # FastAPI 后端服务
│   ├── app/
│   │   ├── main.py                   # 应用入口 + 生命周期
│   │   ├── config.py                 # 配置管理 (pydantic-settings)
│   │   ├── routers/
│   │   │   ├── chat.py               # 多模态对话接口
│   │   │   ├── speech.py             # 语音转文字接口
│   │   │   └── health.py             # 健康检查
│   │   ├── services/
│   │   │   ├── multimodal_ai_service.py  # 多模态 AI 调用
│   │   │   ├── speech_to_text_service.py # STT 服务
│   │   │   ├── image_service.py          # 图片压缩与预处理
│   │   │   ├── session_context_service.py# 会话上下文管理
│   │   │   └── privacy_service.py        # 隐私与日志脱敏
│   │   └── schemas/
│   │       ├── chat.py               # 对话数据模型
│   │       ├── media.py              # 媒体数据模型
│   │       └── session.py            # 会话数据模型
│   ├── requirements.txt
│   └── .env                          # 环境配置
├── frontend/                         # 单页 Web 应用
│   ├── index.html                    # 主页面
│   ├── css/
│   │   └── style.css                 # 完整样式 (暗色主题)
│   └── js/
│       ├── app.js                    # 主应用编排
│       ├── camera.js                 # 摄像头管理
│       ├── screen.js                 # 屏幕共享管理
│       ├── mic.js                    # 麦克风 + 录音
│       ├── chat.js                   # 对话管理 + API 调用
│       └── utils.js                  # 图片压缩 + 工具函数
├── docs/
│   └── New_Web_AI_Companion_Requirements.md  # 完整产品需求文档
├── Tech_Feasibility.md               # 技术可行性报告
├── run_demo.py                       # 启动脚本
└── README.md                         # 本文件
```

---

## 快速开始

### 1. 安装后端依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置 API Key (可选)

编辑 `backend/.env`：

- **不配置**（默认）：使用 Demo 模式，返回模拟回答
- **使用火山方舟**：设置 `AI_PROVIDER=openai` + `OPENAI_API_KEY` + `OPENAI_MODEL` + `OPENAI_BASE_URL=https://ark.cn-beijing.volces.com/api/v3`
- **使用 Claude**：设置 `AI_PROVIDER=anthropic` + `ANTHROPIC_API_KEY`
- **使用 GPT-4o**：设置 `AI_PROVIDER=openai` + `OPENAI_API_KEY`

### 3. 启动后端

```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

API 文档自动生成在：http://localhost:8000/docs

### 4. 打开前端

> ⚠️ 需要浏览器支持 `getDisplayMedia`（Chrome/Edge 72+, Firefox 66+）

**方式 A**：直接用浏览器打开 `frontend/index.html`

**方式 B**：启动本地 HTTP 服务器
```bash
cd frontend
python -m http.server 3000
# 然后访问 http://localhost:3000
```

### 5. 开始使用

1. 点击「屏幕共享」→ 选择要共享的窗口或标签页
2. （可选）点击「摄像头」开启摄像头预览
3. （可选）点击「麦克风」开启语音输入
4. 在输入框输入问题，点击「发送」
5. AI 会截取当前屏幕画面并给出回答

---

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/chat/multimodal` | 多模态对话（文本 + 图片） |
| POST | `/api/speech/transcribe` | 语音转文字 |
| POST | `/api/chat/clear` | 清除会话 |

### 多模态对话请求示例

```json
{
  "session_id": "uuid",
  "user_text": "你看一下我屏幕，这个报错是什么意思？",
  "mode": "coding",
  "input_sources": {
    "screen": true,
    "camera": false,
    "microphone": true
  },
  "images": [
    {
      "type": "screen",
      "mime_type": "image/jpeg",
      "data": "base64..."
    }
  ]
}
```

### 多模态对话响应示例

```json
{
  "answer": "从你的屏幕截图看，这是一个 NameError...",
  "used_sources": ["screen", "voice"],
  "uncertainty": "截图中文字较小，部分行号可能不准确。",
  "suggestions": ["请放大终端区域后重新截图"]
}
```

---

## V1 DEMO 功能清单

### ✅ 已实现 (P0)

| 功能 | 状态 |
|------|------|
| 摄像头授权与预览 | ✅ |
| 屏幕共享授权与预览 | ✅ |
| 麦克风授权 | ✅ |
| 用户提问时截取屏幕帧 | ✅ |
| 用户提问时截取摄像头帧 | ✅ |
| 图片压缩（前端 Canvas） | ✅ |
| 语音录音与转写 | ✅ (需 STT API) |
| 多模态 AI 问答 | ✅ (Mock/Claude/GPT-4o) |
| 文本回复展示 | ✅ |
| 一键停止全部采集 | ✅ |
| 输入源状态实时展示 | ✅ |
| 场景模式切换 | ✅ (通用/学习/办公/编程) |
| 回答依据标注 | ✅ |

### 🔜 后续版本 (P1/P2)

- 流式回答输出（SSE）
- AI 回复语音播报（TTS）
- 多轮对话上下文
- 专注模式
- 高清截图模式
- 敏感内容自动检测

---

## 技术架构

```
┌─────────────────────────┐     ┌─────────────────────────┐
│   前端 (Browser APIs)    │     │    后端 (FastAPI)        │
│                         │     │                         │
│  getDisplayMedia() ─────┼──→  │  /api/chat/multimodal   │
│  getUserMedia()   ──────┼──→  │  /api/speech/transcribe │
│  Canvas 截图     ───────┼──→  │                         │
│  MediaRecorder   ───────┼──→  │  → Anthropic Claude     │
│  image/jpeg 压缩 ──────┼──→  │  → OpenAI GPT-4o        │
│                         │     │  → Mock (Demo)          │
└─────────────────────────┘     └─────────────────────────┘
```

**核心设计原则**：
- 默认**按需分析**，不持续上传视频流
- 图片在**前端压缩**后上传
- 用户始终知道 AI 正在使用哪些输入源
- 一键即可停止所有采集

---

## 隐私与安全

- ✅ 截图仅在上传时存在于内存，服务器不永久保存
- ✅ 所有采集必须由用户主动授权
- ✅ 屏幕共享前有隐私提示
- ✅ 用户可以随时停止任一输入源
- ✅ 后端日志禁止记录图片 base64 和完整音频
- ✅ 回答标注使用了哪些输入源

---

## 场景模式

| 模式 | 回答策略 |
|------|---------|
| 🌐 通用 | 标准问答 |
| 📚 学习 | 优先讲思路，引导推导 |
| 💼 办公 | 优先总结、结构和行动建议 |
| 💻 编程 | 优先解释代码、报错和修改方案 |

---

## 迭代路线

- **V1** (当前): 屏幕 + 语音问答 → 验证技术闭环
- **V2** (计划): 学习/办公场景助手 → 场景化建议
- **V3** (计划): 专注陪伴 → 定时提醒 + 进展总结
