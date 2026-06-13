# PRD：专注陪伴模式（Focus Companion）— 防走神 + 任务简报

> 文档版本：v2.0（重写）  
> 所属产品：DeskMate — 网页端 AI 多模态伴随助手  
> 核心场景：用户设定任务后，AI 定期检查屏幕，判断是否在专心完成任务，走神时提醒，结束后生成任务简报。

---

## 1. 产品一句话

> 用户告诉 AI「我要做什么、做多久」，AI 在这段时间里定期看一眼屏幕，发现用户在摸鱼/玩手机/切到无关页面时温和提醒，结束时给出专注/走神时间线和任务完成简报。

---

## 2. 核心用户故事

### US-F01 设定专注任务

> 作为用户，我打开屏幕共享后，点击「开始专注」，输入「我要完成 Python 项目的数据库模块，预计 40 分钟」。AI 确认任务后开始定期观察我的屏幕。

### US-F02 走神检测与提醒

> 作为用户，当我从 VS Code 切到 B 站刷视频超过 2 分钟，或者离开电脑超过 3 分钟时，AI 在聊天面板发消息提醒我：「你设定的任务是写数据库模块，现在屏幕上是 B 站——要回来继续吗？」

### US-F03 静默专心期

> 作为用户，当我的屏幕内容持续与任务相关时（在 IDE 里写代码、在查技术文档），AI 保持安静，不打扰我。只在检测到明显偏离任务时才出声。

### US-F04 任务完成简报

> 作为用户，当我点击结束（或设定的时间到）后，AI 生成一份简报：总时长、专注时段/走神时段的可视化列表、任务完成度判断、基于观察给出的小建议。

---

## 3. 产品行为模型

### 3.1 AI 角色定义

> AI 是一个「轻度 accountability 伙伴」，不是严厉的监工。提醒语气是「朋友式关心」，不是「家长式指责」。

| 场景 | AI 行为 |
|---|---|
| 屏幕内容与任务相关 | 🔇 静默。30 分钟内最多主动鼓励 1 次 |
| 屏幕内容与任务无关（>2 分钟） | 🔔 温和提醒："看起来你切到 XX 了，还在做 [任务] 吗？" |
| 屏幕长时间无变化（>5 分钟） | 🟡 关心："这个页面停留好一会了，卡住了吗？还是去休息了？" |
| 再次检测到偏离 | 🔔 比上次略强："又看到你切出去了哦，[任务] 还剩 XX 分钟" |
| 用户回到任务 | 🟢 简短肯定："看到你回来了，继续加油！" |
| 任务时间到 | ✅ 自动提醒 + 生成简报 |

### 3.2 走神判定规则

```
走神判定 = 连续 N 次 tick 中屏幕内容被 AI 判定为「与任务无关」

阈值：
  - 频率 15s → 连续 8 次 tick（约 2 分钟）触发提醒
  - 频率 30s → 连续 4 次 tick（约 2 分钟）触发提醒
  - 频率 60s → 连续 2 次 tick（约 2 分钟）触发提醒

且：距上次提醒 > 5 分钟（避免唠叨）
```

### 3.3 离开检测

```
离开检测 = 屏幕画面连续 N 次 tick 完全无变化（hash 距离 < 3）

阈值：
  - 连续 10 次 tick 画面完全不变 → 判定为「用户离开」
  - 画面恢复变化 → 判定为「用户回来」
  - 离开 > 3 分钟 → 不计入专注时间
```

---

## 4. 交互流程

```
用户打开页面
  │
  ├─ 开启屏幕共享
  │
  ├─ 点击「🎯 开始专注」
  │     └─ 弹出设置面板
  │           ├─ 任务描述："写完数据库模块的 CRUD 接口"
  │           ├─ 预计时长：[30分钟] [45分钟] [60分钟] [自定义]
  │           └─ 点击「开始专注」
  │
  ├─ 专注运行中
  │     ├─ 状态栏：🎯 专注中 · 数据库模块 · 剩余 32 分钟
  │     ├─ 前端每 N 秒截帧 → 感知哈希变化？→ 上传
  │     ├─ 后端接收 → AI 判断「与任务相关吗？」→ 更新状态
  │     │
  │     ├─ 场景 A：相关 → 静默，记录「专注」
  │     ├─ 场景 B：不相关 + 超阈值 → AI 发出提醒消息
  │     ├─ 场景 C：画面不动 + 超阈值 → AI 询问是否离开
  │     └─ 场景 D：用户回来 → AI 简短欢迎
  │
  └─ 用户点击「结束专注」（或时间到）
        ├─ 后端生成简报
        └─ 聊天面板展示简报卡片：
              ├─ 📊 专注统计：专注 28 分钟 / 走神 7 分钟 / 离开 5 分钟
              ├─ 📋 时间线：每个时段的状态标记
              ├─ 📝 AI 总结：任务完成度 + 观察
              └─ 💡 小建议
```

---

## 5. 数据模型

### 5.1 前端状态

```javascript
App.state.focus = {
  active: false,
  task: '',              // 任务描述
  duration: 45,          // 预计时长（分钟）
  frequency: 30,         // 截图频率（秒）
  tickCount: 0,
  lastHash: null,
  intervalId: null,
  // 本地记录的时段标记（供后端不可用时的降级简报）
  localSegments: [],     // [{startTime, endTime, status: 'focused'|'distracted'|'away'}]
};
```

### 5.2 后端数据模型

```python
# ── 专注 Tick 请求 ──
class FocusTickRequest(BaseModel):
    session_id: str
    task: str                                    # 用户设定的任务
    screen_frame: ImageInput                     # 当前屏幕帧
    metadata: FocusTickMetadata

class FocusTickMetadata(BaseModel):
    tick_index: int
    seconds_elapsed: int
    page_title: Optional[str] = None
    frame_hash: str
    idle_seconds: int = 0                        # 用户无操作秒数

# ── 专注 Tick 响应 ──
class FocusTickResponse(BaseModel):
    status: str                                  # "focused" | "distracted" | "away" | "returned"
    should_alert: bool                           # 是否需要提醒用户
    alert_message: Optional[str] = None          # 提醒文本
    ai_note: Optional[str] = None                # AI 内部记录（不展示给用户）

# ── 专注时段记录 ──
class FocusSegment(BaseModel):
    start_time: str                              # ISO time
    end_time: Optional[str] = None
    status: str                                  # "focused" | "distracted" | "away"
    note: Optional[str] = None                   # AI 备注（如"在看 B 站"）

# ── 简报请求 ──
class FocusReportRequest(BaseModel):
    session_id: str

# ── 简报响应 ──
class FocusReportResponse(BaseModel):
    task: str
    total_minutes: int
    focused_minutes: int
    distracted_minutes: int
    away_minutes: int
    segments: list[FocusSegment]
    completion_assessment: str                   # 任务完成度评估
    summary: str                                 # AI 总结
    suggestions: list[str]                       # 建议
```

---

## 6. AI 行为 Prompt

### 6.1 Tick 判断 Prompt（每次截帧调用）

```
你是一个专注陪伴助手。用户设定的任务是："{task}"

请判断当前屏幕截图的内容：
1. 这张截图显示用户正在做与「{task}」相关的事吗？
2. 如果不是，用户在做什么？

请用 JSON 格式回答：
{
  "related": true/false,
  "activity": "简短描述用户当前在做什么（10字以内）",
  "confidence": 0.0-1.0
}

注意：
- 如果截图模糊/看不清，设为 related=true（不误判）
- 查资料、看文档、搜索技术问题 → 算相关
- 社交媒体、视频、游戏、购物 → 算不相关
- 桌面/空白页面 + 长时间无变化 → 用户可能离开了
```

### 6.2 提醒生成 Prompt

```
用户设定的任务："{task}"
当前已进行：{elapsed} 分钟
用户当前在：{current_activity}（与任务不相关）
已连续偏离：{distracted_duration} 分钟

请用一句话温和提醒用户回到任务。语气：
- 朋友式关心，不是指责
- 不出现"你又在摸鱼""你总是分心"等负面表达
- 可以带一点幽默感
- 长度不超过 40 字
```

### 6.3 简报生成 Prompt

```
用户任务：{task}
预计时长：{planned} 分钟
实际时长：{actual} 分钟

专注时段：{focused_minutes} 分钟
走神时段：{distracted_minutes} 分钟（主要在看：{distraction_summary}）
离开时段：{away_minutes} 分钟

时间线摘要：{timeline_text}

请生成一份简短的任务简报，包含：
1. 任务完成度评估（1-2句）
2. 专注情况总结（1-2句）
3. 2-3 条小建议（基于观察到的情况）

语气：温暖、鼓励。如果专注度好，真诚表扬。如果走神多，温和给建议。
```

---

## 7. 成本控制

| 策略 | 说明 |
|---|---|
| 前端粗筛 | 画面 hash 完全不变 → 不上传 |
| 后台暂停 | 用户切到其他标签页 → 暂停 tick |
| 低质量截图 | 专注模式用 640px / quality=0.5 |
| AI 判断结果缓存 | 相同 hash 不重复调用 AI |
| 频率上限 | 默认 30s，最快 15s |
| 提醒频率锁 | 5 分钟内最多提醒 1 次 |

预估：30s 频率、每小时 120 次 tick，前端粗筛后约 50% 上传 = 60 次/小时进入后端，变化小时可缓存判断结果。实际 AI 调用约 30-40 次/小时。

---

## 8. 成功指标

- 用户可以完成「设任务 → 专注运行 ≥ 15 分钟 → 被提醒 1-2 次 → 结束 → 收到简报」完整流程
- 走神检测相关度 ≥ 70%（不把查文档误判为走神）
- 提醒频率合理：1 小时内 1-4 次（不唠叨不沉默）
- 简报包含：专注/走神/离开时长 + 时间线 + 建议
- 每个 PR 合并后主分支均可运行

---

## 9. PR 分解

### 分解原则
1. 每个 PR 只做一件事
2. 粒度尽可能细
3. 合并后主分支必须可运行
4. 向后兼容，不破坏已有的摄像头/屏幕共享/对话功能

### 依赖关系

```
PR #1  后端：专注模式数据模型 + API 骨架（mock）
         │
         ├──→ PR #2  前端：感知哈希工具函数
         │
         ├──→ PR #3  前端：专注模式 UI 入口
         │
         ├──→ PR #4  后端：走神检测引擎
         │
         ├──→ PR #5  后端：专注模式 AI 判断 + 提醒生成
         │
         ├──→ PR #6  前端：专注轮询循环 + 提醒展示
         │
         └──→ PR #7  后端: 任务简报生成 API
                  │
                  └──→ PR #8  前端：简报卡片 + 结束体验
```

PR #2、#3、#4 可并行开发；#5 依赖 #4；#6 依赖 #2、#3、#5；#7 依赖 #4；#8 依赖 #7。

---

## 10. PR 详细规格

### PR #1：后端 — 新增专注模式数据模型与 API 骨架

**标题**：`feat: 新增专注模式数据模型、API 端点与 mock 响应`

**功能描述**：
新增专注陪伴模式所需的全部 Pydantic 数据模型和两个 API 端点骨架：
- `POST /api/focus/tick`：接收前端定期发送的屏幕帧，当前返回固定 mock 响应（`status=focused`, `should_alert=false`）
- `POST /api/focus/report`：接收 session_id，当前返回固定 mock 简报

**修改文件**：
- `backend/app/schemas/chat.py` — 新增 `FocusTickMetadata`、`FocusTickRequest`、`FocusTickResponse`、`FocusSegment`、`FocusReportRequest`、`FocusReportResponse`
- `backend/app/routers/chat.py` — 新增 `POST /api/focus/tick` 和 `POST /api/focus/report` 两个路由，返回 mock 响应

**实现思路**：
- 数据模型使用 Pydantic BaseModel，严格按照第 5.2 节定义
- tick mock 响应：`{status: "focused", should_alert: false, alert_message: null, ai_note: null}`
- report mock 响应：`{task: "...", focused_minutes: 30, distracted_minutes: 5, away_minutes: 5, ...}`（固定模板）
- 此阶段不做任何真实逻辑，目的仅是定义接口契约，让前端可以并行开发

**测试方式**：
```bash
# 启动后端
cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 测试 tick
curl -X POST http://localhost:8000/api/focus/tick \
  -H "Content-Type: application/json" \
  -d '{
    "session_id":"t1","task":"写数据库模块",
    "screen_frame":{"type":"screen","mime_type":"image/jpeg","data":"aaa"},
    "metadata":{"tick_index":1,"seconds_elapsed":30,"page_title":"VS Code","frame_hash":"abc","idle_seconds":0}
  }'
# 预期: {"status":"focused","should_alert":false,"alert_message":null,"ai_note":null}

# 测试 report
curl -X POST http://localhost:8000/api/focus/report \
  -H "Content-Type: application/json" \
  -d '{"session_id":"t1"}'
# 预期: 返回包含 task/focused_minutes/distracted_minutes/away_minutes/segments/summary/suggestions 的 JSON
```

---

### PR #2：前端 — 新增感知哈希工具函数

**标题**：`feat: 新增屏幕帧感知哈希计算与对比工具函数`

**功能描述**：
在 `utils.js` 中新增 `ImageHasher` 工具对象，提供 `computeFrameHash(videoEl)` 和 `hashDistance(hash1, hash2)` 两个函数。用于专注模式下前端粗筛：画面完全不变时跳过上传，节省带宽和 AI 调用成本。

**修改文件**：
- `frontend/js/utils.js` — 追加 `ImageHasher` 对象

**实现思路**：
- 采用 aHash（平均哈希）：复用 `ImageCompressor.captureFrame()` 获取 canvas → 缩放到 16×16 → 灰度 → 计算均值 → 逐像素比较 → 输出 256-bit hex 字符串
- `hashDistance` 计算两个 hex 哈希的汉明距离（0-256）
- 纯工具函数，不修改任何现有模块，不产生副作用
- 距离阈值参考：0-5 几乎相同（无变化），5-15 轻微（滚动/弹窗），15+ 明显变化

**测试方式**：
```javascript
// 浏览器控制台
// 1. 开启屏幕共享后
const h1 = ImageHasher.computeFrameHash(document.getElementById('screenVideo'));
// 2. 等待几秒（不做任何操作）
const h2 = ImageHasher.computeFrameHash(document.getElementById('screenVideo'));
console.log('Same screen distance:', ImageHasher.hashDistance(h1.hash, h2.hash));
// 预期: 0-3

// 3. 切换到完全不同窗口再切回来截
const h3 = ImageHasher.computeFrameHash(document.getElementById('screenVideo'));
console.log('Different screen distance:', ImageHasher.hashDistance(h1.hash, h3.hash));
// 预期: >15
```

---

### PR #3：前端 — 新增专注模式 UI 入口与设置面板

**标题**：`feat: 新增专注模式按钮、设置面板与状态栏指示`

**功能描述**：
在左侧控制面板新增「🎯 开始专注」按钮。点击弹出设置面板，用户输入任务描述和预计时长。开始后状态栏显示专注状态（任务摘要 + 已进行时间）。本 PR 仅实现 UI 交互和状态管理，不包含轮询循环。

**修改文件**：
- `frontend/index.html` — 在控制按钮区域新增专注按钮；新增设置弹窗 HTML；状态栏新增专注状态位
- `frontend/css/style.css` — 新增 `.focus-btn.active`、`.focus-modal`、`.focus-status-bar` 等样式
- `frontend/js/app.js` — 新增 `openFocusSetup()`、`startFocus(task, duration)`、`stopFocus()` 方法；扩展 `App.state.focus`

**实现思路**：
- 设计要点：设置面板足够简单——两个输入项（任务描述 textarea + 时长下拉选择）+ 两个按钮（开始/取消）
- `startFocus()` 校验：屏幕共享必须已开启，否则提示用户先开启
- 开始后：按钮变为「⏹ 结束专注」（红色/警告色），状态栏追加「🎯 专注中 · [任务摘要] · 已进行 X 分钟」（每秒更新计时器）
- `stopFocus()`：清除计时器，恢复按钮和状态栏。本 PR 中不调用后端简报 API（留给 PR #8）
- 不破坏已有功能：摄像头、麦克风、场景模式等完全不受影响

**测试方式**：
1. 打开页面 → 看到「🎯 开始专注」按钮
2. 屏幕共享未开启时点击 → 提示"请先开启屏幕共享"
3. 开启屏幕共享 → 点击「开始专注」
4. 弹出设置面板，输入"写数据库模块"、选 45 分钟 → 点「开始」
5. 验证：按钮变为红色「⏹ 结束专注」；状态栏显示「🎯 专注中 · 写数据库模块 · 已进行 00:01」
6. 验证计时器每秒递增
7. 点击「结束专注」→ 按钮和状态栏恢复
8. 重复开启/结束几次，确保无内存泄漏（定时器被正确清除）

---

### PR #4：后端 — 实现走神检测引擎

**标题**：`feat: 新增专注会话服务与走神检测状态机`

**功能描述**：
新增 `FocusService` 服务类，管理专注会话的全生命周期状态机。核心逻辑：接收每次 tick → 维护专注/走神/离开状态 → 按阈值规则决定是否触发提醒 → 记录时段分段。在本 PR 中，走神判断使用简化规则（基于 hash 变化 + 页面标题），不调用 AI。

**修改文件**：
- `backend/app/services/focus_service.py` — **新文件**，包含完整的状态机逻辑
- `backend/app/routers/chat.py` — 修改 `/api/focus/tick` 从 mock 升级为调用 `FocusService.process_tick()`

**实现思路**：

状态机：
```
                    ┌──────────────┐
         开始专注 → │   FOCUSED    │
                    └───┬─────┬────┘
            hash大变+  │     │  hash连续不变
           标题不相关  │     │  >阈值
                    ┌──▼──┐ ┌▼───┐
                    │DISTR-│ │AWAY │
                    │ACTED │ └──┬──┘
                    └──┬───┘    │
            回到任务  │   画面恢复│
                    ┌──▼──────▼─┐
                    │  FOCUSED  │ (returned)
                    └───────────┘
```

关键类结构：
```python
class FocusSession:
    session_id: str
    task: str
    start_time: datetime
    current_status: str  # "focused" | "distracted" | "away"
    status_started_at: datetime
    alert_count: int
    last_alert_at: Optional[datetime]
    segments: List[dict]  # [{start, end, status, note}]

class FocusService:
    def process_tick(request: FocusTickRequest) -> FocusTickResponse:
        # 1. 获取/创建 FocusSession
        # 2. 根据 hash 变化 + 页面标题判断当前应处于什么状态
        # 3. 状态转换时记录 segment
        # 4. 根据规则决定 should_alert
        # 5. 返回 FocusTickResponse
```

走神检测规则（非 AI 版本）：
```
标记为 DISTRACTED 条件（任一满足）：
  - hash 距离 > 20 且页面标题包含「娱乐/视频/游戏/购物/微博/知乎/贴吧」等关键词
  - hash 距离 > 20 且页面标题与 task 完全不相关（简单关键词匹配）

标记为 AWAY 条件：
  - hash 距离 < 3 且连续 > 10 次 tick

标记回 FOCUSED 条件：
  - 从 DISTRACTED 回来：hash 变化 + 标题看起来与任务相关
  - 从 AWAY 回来：hash 距离 > 3
```

**测试方式**：
```bash
# 模拟一次完整的专注→走神→回来流程
# Tick 1: 在 VS Code（专注）
curl -X POST http://localhost:8000/api/focus/tick \
  -d '{"session_id":"f1","task":"写数据库模块","screen_frame":{...},
       "metadata":{"tick_index":1,"seconds_elapsed":30,"page_title":"VS Code - db.py","frame_hash":"aaa","idle_seconds":0}}'
# 预期: {"status":"focused","should_alert":false}

# Tick 2-N: 切换到 B 站（走神），连续多次
for i in {2..6}; do
  curl -X POST http://localhost:8000/api/focus/tick \
    -d '{"metadata":{"tick_index":'$i',"seconds_elapsed":'$((i*30))',"page_title":"Bilibili - 视频","frame_hash":"zzz","idle_seconds":0}}'
done
# 连续 4 次后（>2分钟）：{"status":"distracted","should_alert":true,"alert_message":"..."}

# Tick 7: 回到 VS Code
curl ... -d '{"metadata":{"tick_index":7,...,"page_title":"VS Code - db.py","frame_hash":"bbb",...}}'
# 预期: {"status":"focused","should_alert":false}

# 验证 segments 记录了状态切换
```

---

### PR #5：后端 — 专注模式 AI 判断与提醒生成

**标题**：`feat: 专注模式集成 AI 进行任务相关度判断与提醒文案生成`

**功能描述**：
将 PR #4 中的规则判断升级为 AI 判断。每次 tick 调用多模态 AI，询问「截图内容与任务相关吗？」替代关键词匹配。走神时调用 AI 生成个性化提醒文案。mock 模式下保留 PR #4 的规则逻辑作为降级。

**修改文件**：
- `backend/app/services/focus_service.py` — `process_tick()` 中新增 AI 判断分支；新增 `_ask_ai_relevance()` 和 `_generate_alert_message()` 方法
- `backend/app/services/multimodal_ai_service.py` — 新增 `focus_check_relevance()` 和 `focus_generate_alert()` 方法
- `backend/app/config.py` — 可选新增 `FOCUS_AI_ENABLED` 配置项（默认 true，mock 模式自动走规则）

**实现思路**：

AI 调用策略（控制成本）：
```
仅在以下情况调用 AI 做相关度判断：
  1. 前端 hash 变化 > 10（有明显变化）
  2. 且距上次 AI 判断 > 60 秒
  
不满足条件时：沿用上一次 AI 判断结果
```

AI 判断 Prompt（§6.1）返回 JSON `{related, activity, confidence}`：
- `related=false + confidence>0.7` → 计入走神计数
- `related=false + confidence<0.7` → 不计数（不确定时不误判）
- 截图模糊/看不清 → 默认 `related=true`

提醒文案由 AI 生成（§6.2），每次不超过 40 字。

mock 模式降级：
- 相关度判断：保留 PR #4 的关键词规则
- 提醒文案：使用模板 `"看起来你切到 {page_title} 了，还要继续 {task} 吗？"`

**测试方式**：
```bash
# Mock 模式（未配置 AI Key）
# 行为应与 PR #4 一致但提醒文案更丰富

# 真实 AI 模式（配置了 API Key）
# 1. 在 VS Code 写代码 → tick → AI 应判断 related=true
# 2. 切换到 YouTube → tick → AI 应判断 related=false
# 3. 验证 AI 返回的提醒文案是自然语言而非模板
# 4. 切换到 Stack Overflow（查技术问题） → AI 应判断 related=true（不误判）
```

---

### PR #6：前端 — 专注轮询循环 + 走神提醒展示 + 离开检测

**标题**：`feat: 实现专注模式自动轮询、走神提醒展示与用户离开检测`

**功能描述**：
在专注模式激活后启动前端轮询循环：按设定频率（默认 30s）截帧 → 感知哈希 → 变化时调用 `/api/focus/tick` → 若后端返回 `should_alert=true` 则在聊天面板展示提醒消息。集成浏览器 `visibilityState` 实现后台暂停，集成用户空闲检测（鼠标/键盘事件监听）补充离开判断。

**修改文件**：
- `frontend/js/app.js` — 新增 `_startFocusLoop()`、`_stopFocusLoop()`、`_focusTick()`、`_getIdleSeconds()` 方法；修改 `startFocus()` 和 `stopFocus()` 接入循环
- `frontend/js/chat.js` — 新增 `addFocusAlertMessage(alertText)` 方法（提醒消息使用区分样式）
- `frontend/js/utils.js` — `apiClient` 新增 `focusTick(requestBody)` 方法
- `frontend/css/style.css` — 新增提醒消息样式 `.message-focus-alert`（黄色/暖色左边框 + 铃铛图标，区分于普通 AI 消息）

**实现思路**：

轮询循环：
```javascript
_focusTick: async function() {
  // 1. 后台检测：页面不可见时跳过
  if (document.visibilityState === 'hidden') {
    this.state.focus._backgroundTicks = (this.state.focus._backgroundTicks || 0) + 1;
    return;  // 回来后根据 _backgroundTicks 补偿判断是否一直在后台
  }

  // 2. 截图 + 感知哈希
  if (!ScreenShareManager.isReady()) return;
  const frame = ScreenShareManager.captureFrame(640, 640, 0.5);
  const { hash } = ImageHasher.computeFrameHash(
    document.getElementById('screenVideo'), frame
  );

  // 3. hash 完全不变 + idle 时间递增 → 跳过上传（节省带宽）
  const idleSeconds = this._getIdleSeconds();
  if (hash === this.state.focus.lastHash && idleSeconds < 120) {
    this.state.focus.tickCount++;
    return;
  }
  this.state.focus.lastHash = hash;
  this.state.focus.tickCount++;

  // 4. 调用后端
  const response = await apiClient.focusTick({
    sessionId: ChatManager.sessionId,
    task: this.state.focus.task,
    screenFrame: frame,
    metadata: {
      tick_index: this.state.focus.tickCount,
      seconds_elapsed: this.state.focus.tickCount * this.state.focus.frequency,
      page_title: document.title,
      frame_hash: hash,
      idle_seconds: idleSeconds,
    },
  });

  // 5. 处理提醒
  if (response.should_alert && response.alert_message) {
    ChatManager.addFocusAlertMessage(response.alert_message);
  }
}
```

用户空闲检测（`_getIdleSeconds`）：
- 监听 `mousemove`、`keydown`、`click`、`scroll` 事件
- 记录最后一次活动时间戳，返回当前距最后活动的秒数
- 用于补充后端 AWAY 判定

**测试方式**：
1. 启动后端（mock 模式），开启屏幕共享
2. 开始专注：「写数据库模块」, 30 分钟, 频率 15s（测试用）
3. 观察控制台定期打印 tick 日志
4. **走神测试**：切换到 B 站并保持 → 等待约 2 分钟 → 验证聊天面板出现 AI 提醒消息（黄色边框 + 铃铛图标）
5. **静默测试**：在 VS Code 中持续操作 → 验证无提醒消息
6. **离开测试**：保持屏幕不变，不操作鼠标键盘 → 等待 3-5 分钟 → 验证出现「还在吗？」类消息
7. **切后台测试**：切到其他 Chrome 标签页 2 分钟 → 切回来 → 验证后台期间无网络请求
8. 点击「结束专注」→ 验证轮询停止

---

### PR #7：后端 — 任务简报生成

**标题**：`feat: 新增专注任务简报生成 API，输出专注/走神时间线与建议`

**功能描述**：
升级 `POST /api/focus/report` 端点，基于 `FocusService` 中记录的 segments（专注/走神/离开时段）和 tick 历史，生成结构化的任务简报。包含统计摘要、时间线、AI 生成的任务评估与建议。mock 模式下使用模板化生成。

**修改文件**：
- `backend/app/services/focus_service.py` — 新增 `generate_report(session_id)` 方法
- `backend/app/services/multimodal_ai_service.py` — 新增 `focus_generate_report()` 方法（简报专用 Prompt）
- `backend/app/routers/chat.py` — 修改 `/api/focus/report` 调用真实 report 逻辑

**实现思路**：

简报生成流程：
```
1. 获取 FocusSession 的所有 segments
2. 计算统计：
   - total_minutes = 实际总时长
   - focused_minutes = Σ focused segment 时长
   - distracted_minutes = Σ distracted segment 时长
   - away_minutes = Σ away segment 时长
3. 汇总走神时段的 AI 备注（"在看 B 站"、"刷知乎"等）→ distraction_summary
4. 构建时间线文本
5. 调用 AI 生成 completion_assessment + summary + suggestions（§6.3 Prompt）
6. mock 模式下使用模板拼装
```

简报数据结构：
```json
{
  "task": "写数据库模块",
  "total_minutes": 45,
  "focused_minutes": 32,
  "distracted_minutes": 8,
  "away_minutes": 5,
  "segments": [
    {"start_time":"14:05","end_time":"14:20","status":"focused","note":"在 VS Code 写代码"},
    {"start_time":"14:20","end_time":"14:25","status":"distracted","note":"B 站看视频"},
    {"start_time":"14:25","end_time":"14:37","status":"focused","note":"继续写代码"},
    {"start_time":"14:37","end_time":"14:42","status":"away","note":"离开电脑"},
    {"start_time":"14:42","end_time":"14:50","status":"focused","note":"调试代码"}
  ],
  "completion_assessment": "数据库模块的 CRUD 接口主体代码已完成，但测试部分似乎还没开始写。整体完成了约 70%。",
  "summary": "这 45 分钟里你大部分时间在专心写代码，中间去 B 站刷了 5 分钟视频，还离开了一小会。总的来说专注度不错！",
  "suggestions": [
    "下次可以先把 B 站关掉或设成勿扰模式",
    "数据库模块还剩测试部分，建议下一个专注时段专门写测试",
    "每 25 分钟休息 5 分钟的节奏可以试试"
  ]
}
```

**测试方式**：
```bash
# 1. 先通过多次 tick 构建一个有内容的专注会话
# (至少包含 focused + distracted + away 各一段)

# 2. 请求简报
curl -X POST http://localhost:8000/api/focus/report \
  -H "Content-Type: application/json" \
  -d '{"session_id":"f1"}'

# 3. 验证响应包含：
#    - focused_minutes + distracted_minutes + away_minutes = total_minutes
#    - segments 数组至少有 2-3 个时段
#    - suggestions 至少 1 条
#    - summary 非空
```

---

### PR #8：前端 — 简报卡片展示与结束体验

**标题**：`feat: 专注结束时展示任务简报卡片，含专注/走神统计与时间线`

**功能描述**：
用户点击「结束专注」后，前端调用 `/api/focus/report` 获取简报数据，在聊天面板中渲染一张结构化的简报卡片。卡片展示：专注/走神/离开统计、分段时间线、AI 总结与小建议。同时在 `stopFocus()` 中完成状态清理。

**修改文件**：
- `frontend/js/app.js` — 修改 `stopFocus()`，增加获取简报、展示卡片、清理状态的完整流程
- `frontend/js/chat.js` — 新增 `addFocusReportCard(reportData)` 方法，渲染简报卡片 HTML
- `frontend/js/utils.js` — `apiClient` 新增 `focusReport(sessionId)` 方法
- `frontend/css/style.css` — 新增简报卡片样式 `.focus-report-card`、`.focus-stat-row`、`.focus-timeline`、`.focus-suggestion`

**实现思路**：

简报卡片视觉结构：
```
┌─────────────────────────────────────┐
│ 📊 专注简报 — 写数据库模块           │
│                                     │
│ ┌──────┐ ┌──────┐ ┌──────┐         │
│ │ 32min│ │  8min│ │  5min│         │
│ │ 专注  │ │ 走神  │ │ 离开  │         │
│ └──────┘ └──────┘ └──────┘         │
│                                     │
│ 📋 时间线                           │
│ ● 14:05-14:20  专注  VS Code写代码  │
│ ◐ 14:20-14:25  走神  B站看视频      │
│ ● 14:25-14:37  专注  继续写代码     │
│ ○ 14:37-14:42  离开  离开电脑       │
│ ● 14:42-14:50  专注  调试代码       │
│                                     │
│ 📝 AI 总结                          │
│ 这45分钟里你大部分时间在专心写代码... │
│                                     │
│ 💡 小建议                           │
│ • 下次先关掉B站或设勿扰模式          │
│ • 还剩测试部分，下个时段专门写测试    │
└─────────────────────────────────────┘
```

降级策略：
- 若后端不可用 → 使用前端本地记录的 segments 生成简化版简报（无 AI 总结和建议）
- 若后端返回但无 AI 内容（mock 模式）→ 展示统计和时间线，省去总结区

**测试方式**：
1. 完整流程：开启屏幕共享 → 开始专注（15 分钟/15s 频率） → 期间故意切换到无关页面几次 → 离开电脑一会 → 回来继续任务 → 点击结束
2. 验证聊天面板出现简报卡片
3. 验证统计数据（专注/走神/离开分钟数之和 ≈ 总时长）
4. 验证时间线正确标记了每个时段的状态（●/◐/○ 图标）
5. 验证 AI 总结和建议有实际内容
6. 再次开启新专注 → 验证旧会话已清理，新会话从零开始

---

## 11. 开发节奏建议

```
Week 1:
  Day 1-2: PR #1（后端骨架） + PR #2（前端哈希） → 并行
  Day 3:   PR #3（前端 UI）   + PR #4（后端引擎） → 并行
  Day 4-5: PR #5（AI 集成）

Week 2:
  Day 1-2: PR #6（前端循环 + 联调）← 首个可端到端演示的里程碑 🎯
  Day 3:   PR #7（后端简报）
  Day 4-5: PR #8（前端简报卡片）

Week 3:
  Day 1-2: 内部试用 + 走神阈值调优
  Day 3-5: Bug 修复 + 边缘情况处理
```

---

*文档结束*