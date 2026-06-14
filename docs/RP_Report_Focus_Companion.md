# 专注陪伴模式 — Release Progress Report

> **分支**: `feature/focus-companion`  
> **基于**: `master` (`5965eea`)  
> **日期**: 2026-06-14  
> **PRD**: `docs/PRD_Companion_Mode_V2.md`

---

## 1. 概要

本轮迭代在 DeskMate V1 Demo 基础上新增 **专注陪伴模式（Focus Companion）**，实现了"用户设定任务 → AI 定期观察屏幕 → 走神时温和提醒 → 结束时生成简报"的完整闭环。

共 **8 个 PR**，**12 个文件变更**，净增 **1,731 行代码**。

---

## 2. 交付物

| 层级 | 交付内容 |
|---|---|
| **后端** | 专注模式 API（tick + report）、状态机引擎、AI 判断集成 |
| **前端** | 专注模式 UI（按钮/弹窗/状态栏）、轮询循环、感知哈希、提醒展示、简报卡片 |
| **文档** | PRD v2.0、分支声明文件、本 RP 报告 |

---

## 3. PR 列表

| # | 提交 | 内容 | 关键产出 |
|---|---|---|---|
| 1 | `9ee35a0` | 后端数据模型 + API 骨架 | 6 个 Pydantic 模型，2 个 mock 端点 |
| 2 | `0aeae0f` | 感知哈希工具函数 | `ImageHasher.computeFrameHash()` + `hashDistance()` |
| 3 | `dd795e6` | UI 入口 + 设置面板 | 按钮、弹窗、状态栏、计时器、系统消息 |
| 4 | `540945c` | 走神检测状态机 | `FocusService`，三态机（FOCUSED/DISTRACTED/AWAY） |
| 5 | `127e987` | AI 判断 + 提醒文案 | AI 相关度判断、提醒生成、简报生成，规则降级兜底 |
| 6 | `f5551d7` | 轮询循环 + 提醒展示 | 🏁 **里程碑 A** — 端到端可演示 |
| 7 | (合入 #4-5) | 简报生成 API | AI 简报 + 模板降级 |
| 8 | `1c9e0bd` | 简报卡片 + 结束体验 | 🏁 **里程碑 B** — 完整闭环 |

---

## 4. 技术架构总览

```
┌─ 前端 (Browser) ───────────────────────────────────────────┐
│                                                              │
│  App.startFocus()                                            │
│    └─ _startFocusLoop()  ─ setInterval(frequency)           │
│         └─ _focusTick()                                     │
│              1. ScreenShareManager.captureFrame(640,640,0.5)│
│              2. ImageHasher.computeFrameHash() → aHash      │
│              3. hash changed? → apiClient.focusTick()       │
│              4. response.should_alert? → addFocusAlertMsg() │
│                                                              │
│  App.stopFocus()                                             │
│    └─ _stopFocusLoop()                                      │
│    └─ apiClient.focusReport() → addFocusReportCard()        │
│                                                              │
│  ┌───────────────────┐  ┌───────────────────────┐           │
│  │ 后台暂停           │  │ 空闲检测              │           │
│  │ visibilityState    │  │ _getIdleSeconds()     │           │
│  │ === 'hidden' → skip│  │ mousemove/keydown/... │           │
│  └───────────────────┘  └───────────────────────┘           │
└──────────────────┬───────────────────────────────────────────┘
                   │ HTTP POST /api/focus/tick
                   │ HTTP POST /api/focus/report
                   ▼
┌─ 后端 (FastAPI) ────────────────────────────────────────────┐
│                                                              │
│  /api/focus/tick                                             │
│    └─ FocusService.process_tick() [async]                   │
│         ├─ hash 变化检测                                     │
│         ├─ AI: focus_check_relevance(task, frame)           │
│         │    → {related, activity, confidence}               │
│         ├─ 状态机: FOCUSED ⇄ DISTRACTED ⇄ AWAY              │
│         ├─ AI: focus_generate_alert() → 提醒文案            │
│         └─ 记录 segments                                     │
│                                                              │
│  /api/focus/report                                           │
│    └─ FocusService.generate_report() [async]                │
│         ├─ 统计 segments → 分钟估算                          │
│         ├─ AI: focus_generate_report()                      │
│         └─ FocusReportResponse {stats, timeline, summary}    │
│                                                              │
│  AI Provider: anthropic | openai | mock                      │
│  失败策略: 所有 AI 调用有 try/except → 降级规则/Mock         │
└──────────────────────────────────────────────────────────────┘
```

---

## 5. 状态机

```
                    ┌──────────────┐
         开始专注 → │   FOCUSED    │ ←─────────────┐
                    │  AI 静默      │               │
                    └───┬─────┬────┘               │
            AI判断不相关│     │hash连续不变>10次    │回到任务
            +高置信度   │     │                    │
                    ┌──▼──┐ ┌▼───┐               │
                    │DIST-│ │AWAY │               │
                    │RACT-│ │     │               │
                    │ED   │ └──┬──┘               │
                    └──┬───┘    │                  │
            连续>4次tick│  画面恢复│                  │
                    ┌──▼───┐    │                  │
                    │ 触发  │    │                  │
                    │ 提醒  │    │                  │
                    └──────┘    │                  │
            提醒冷却>5分钟       │                  │
                                └──────────────────┘
```

---

## 6. 关键指标

| 指标 | 值 |
|---|---|
| **总提交数** | 8 |
| **文件变更** | 12 文件 |
| **代码增量** | +1,731 / -139 行 |
| **新增文件** | `focus.py` (router), `focus_service.py` (engine), `FEATURE_FOCUS_COMPANION.md` |
| **API 端点** | 2 个 (`POST /api/focus/tick`, `POST /api/focus/report`) |
| **AI 方法** | 3 个 (`check_relevance`, `generate_alert`, `generate_report`) |
| **前端模块** | ImageHasher, apiClient 扩展, ChatManager 扩展, App 扩展 |
| **后端服务** | FocusService (~350 行) |

---

## 7. 里程碑验证

### 🏁 里程碑 A（PR #6 合并后）

```
用户操作:
  1. 开启屏幕共享
  2. 点击「🎯 开始专注」→ 输入"写数据库模块"，30 分钟
  3. 在 VS Code 正常写代码 → AI 静默
  4. 切换到 Bilibili → 约 2 分钟后 AI 发出提醒
  5. 切回 VS Code → AI 简短肯定

状态: ✅ 可演示
```

### 🏁 里程碑 B（PR #8 合并后）

```
用户操作:
  1-4. 同上
  5. 点击「结束专注」（或时间到）
  6. 聊天面板出现简报卡片:
     ┌──────────────────────────┐
     │ 📊 专注简报              │
     │ [32分钟] [8分钟] [5分钟] │
     │  专注     走神    离开   │
     │ 📋 时间线 (彩色标记)      │
     │ 📝 AI 评估               │
     │ 💡 小建议 x3             │
     └──────────────────────────┘

状态: ✅ 可演示
```

---

## 8. 已实现 vs 待实现

### ✅ 本轮已实现

- 专注模式完整闭环（设定 → 观察 → 提醒 → 简报）
- 三态走神检测状态机
- AI 多模态相关度判断（支持 Anthropic/OpenAI/Mock）
- AI 生成的个性化提醒文案
- AI 生成的结构化简报（评估 + 总结 + 建议）
- 感知哈希前端粗筛节约带宽
- 后台标签页自动暂停
- 用户空闲检测
- AI 调用失败降级兜底
- 简报卡片可视化

### 🔜 可继续迭代

- 提醒强度控制（温和/正常/严格）
- 浏览器系统级 Notification
- 摄像头融合检测（用户是否在桌前）
- 超时自动结束 + 倒计时
- 用户偏好本地持久化
- 专注历史与趋势对比
- 视觉摘要链缓存（降低 AI 调用频率）
- WebSocket 推送代替轮询

---

## 9. 成本预估

| 场景 | 频率 | 每小时 AI 调用 | 估算成本 |
|---|---|---|---|
| 轻量（60s 频率） | 每小时 60 tick | ~10-20 次判断 + 0-3 次提醒 | ~$0.10-0.30 |
| 标准（30s 频率） | 每小时 120 tick | ~20-40 次判断 + 0-5 次提醒 | ~$0.20-0.60 |
| 高频（15s 频率） | 每小时 240 tick | ~40-80 次判断 + 0-8 次提醒 | ~$0.40-1.00 |

> 注：以上基于 Claude Sonnet/Haiku 级的单图判断成本；前端哈希粗筛可减少约 40% 上传；实际费用以 API 提供商定价为准。

---

## 10. 与 master 差异

```bash
# 查看完整差异
git diff master..feature/focus-companion --stat

# 查看仅新增/修改的文件列表
git diff master..feature/focus-companion --name-status
```

master 分支在本次迭代中**未被修改**，所有变更均在 `feature/focus-companion` 分支。

---

*报告结束*
