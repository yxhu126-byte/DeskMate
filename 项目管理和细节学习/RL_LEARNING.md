# DeskMate 强化学习学习与落地文档

> 本文档用于说明 DeskMate 项目中哪些部分适合使用强化学习，并以这个项目为案例，系统学习强化学习从问题建模、数据集构建、算法选择、框架设计、调参、评估到可视化的完整流程。

---

## 0. 文档目标

你希望通过 DeskMate 项目重新学习强化学习。因此本文档不只回答“哪里用 RL”，还会把项目问题拆成强化学习的标准组件：

- Agent 是什么？
- Environment 是什么？
- State 是什么？
- Action 是什么？
- Reward 怎么设计？
- 数据从哪里来？
- 用什么算法？
- 如何调参？
- 如何评估？
- 如何可视化？
- 常见坑在哪里？

---

## 1. 结论先行：DeskMate 哪些地方适合用强化学习？

DeskMate 的核心产品目标是：

> 在合适的时间、以合适的方式、给用户合适的建议，同时尽量减少打扰。

这个问题天然适合强化学习，因为它不是一次性分类问题，而是一个连续决策问题。

### 1.1 最适合用 RL 的模块

| 模块 | 是否适合 RL | 原因 | 建议阶段 |
|---|---:|---|---|
| 通知策略 / 打扰控制 | 非常适合 | 需要在“帮助用户”和“不打扰用户”之间长期权衡 | MVP 后期 / v0.5 |
| 建议展示时机 | 非常适合 | 同一建议早说、晚说、不说都会影响用户反馈 | v0.5 |
| 个性化频率控制 | 非常适合 | 不同用户对提醒频率容忍度不同 | v0.5 |
| 建议类型排序 | 适合 | 多个建议候选时选择哪一个最有价值 | v0.5 / v1.0 |
| 休息 / 久坐提醒策略 | 适合 | 可以根据用户采纳习惯调整提醒间隔 | v0.5 |
| 休闲时长管控 | 适合 | 提醒过早烦，提醒过晚无效 | v1.0 |
| 模型调用成本控制 | 适合 | 何时调用 VLM、调用哪个模型、是否跳过，是成本收益决策 | v1.0 |
| UI 弹窗样式选择 | 适合 | 文案、按钮、展示强度可根据反馈优化 | v1.0 |

### 1.2 不建议早期用 RL 的模块

| 模块 | 不建议原因 |
|---|---|
| 屏幕场景识别 | 更像监督学习 / VLM 分类，不是 RL 起点 |
| 情绪识别 | 隐私和伦理风险高，且标签难定义 |
| 摄像头人脸模糊 | 是计算机视觉任务，不是 RL |
| 日历事件读取 | 是规则/接口工程，不需要 RL |
| VLM JSON 解析 | 是工程容错问题，不需要 RL |
| 数据库存储 | 普通后端工程，不需要 RL |

### 1.3 最推荐的 RL 切入点

最推荐从这个问题开始：

> 当 VLM 产生一个建议候选时，DeskMate 应该选择：立即弹窗、轻提示、静默记录、稍后提醒，还是完全忽略？

这就是一个很标准的强化学习问题。

---

## 2. 用 DeskMate 理解强化学习基本概念

### 2.1 强化学习一句话解释

强化学习研究的是：

> 一个智能体在环境中不断做决策，通过奖励反馈学习长期最优策略。

在 DeskMate 中：

```text
智能体 Agent：DeskMate 的通知决策模块
环境 Environment：用户 + 桌面状态 + 时间 + 当前任务上下文
状态 State：当前用户状态、场景、历史反馈、时间、建议类型等
动作 Action：弹窗 / 轻提示 / 静默 / 稍后 / 不提醒
奖励 Reward：用户点击、有用反馈、忽略、关闭、继续专注等
策略 Policy：在什么状态下选择什么提醒动作
```

---

## 3. DeskMate 的 RL 问题建模

## 3.1 任务一：通知策略优化

### 问题描述

VLM 每隔一段时间或在用户手动触发时，会产生一个建议候选：

```json
{
  "scene": "coding",
  "suggestion_type": "bug_hint",
  "priority": 3,
  "confidence": 0.78,
  "suggestion": "这里可能缺少异常处理，要不要看一下？"
}
```

RL 模块要决定：

```text
现在要不要打扰用户？如果要，用什么方式？
```

---

### MDP 建模

强化学习通常把问题建模为 MDP：Markov Decision Process，马尔可夫决策过程。

一个 MDP 包含：

```text
S：状态空间
A：动作空间
P：状态转移概率
R：奖励函数
γ：折扣因子
```

对应到 DeskMate：

### State 状态

一个状态可以包含：

```json
{
  "scene": "coding",
  "suggestion_type": "bug_hint",
  "vlm_confidence": 0.78,
  "priority": 3,
  "time_of_day": "afternoon",
  "minutes_since_last_notification": 42,
  "notifications_today": 6,
  "same_type_notifications_today": 1,
  "user_activity_level": "paused",
  "foreground_app": "IDE",
  "is_fullscreen": false,
  "recent_ignore_rate": 0.35,
  "recent_accept_rate": 0.22
}
```

学习重点：

- 状态不是越多越好。
- 早期可以用离散特征，后期再用连续特征。
- 状态应尽量包含影响决策的关键信息。

---

### Action 动作

动作空间可以从简单开始：

#### v1：三动作

```text
0 = 不提醒，只记录
1 = 轻提示，例如托盘闪烁
2 = 弹窗提醒
```

#### v2：五动作

```text
0 = 丢弃建议
1 = 静默记录
2 = 轻提示
3 = 立即弹窗
4 = 稍后提醒
```

#### v3：加入文案和样式

```text
动作 = 提醒方式 × 文案风格 × 延迟时间
```

例如：

```text
立即弹窗 + 温和文案 + 两个按钮
稍后 5 分钟 + 简短文案
静默记录 + 日报汇总
```

学习建议：先从三动作开始，否则动作空间太大，学习会变慢。

---

### Reward 奖励

奖励是整个 RL 系统最关键、也最容易出问题的部分。

DeskMate 的奖励可以这样设计：

| 用户行为 | 奖励 |
|---|---:|
| 用户点击“有用” | +5 |
| 用户点击“展开看看” | +3 |
| 用户接受建议并执行 | +8 |
| 用户点击“稍后提醒” | +1 |
| 用户直接忽略 | -1 |
| 用户点击“不再提醒此类” | -5 |
| 用户关闭 DeskMate | -10 |
| 当天通知过多 | -2 到 -8 |
| 用户保持专注且无打扰 | +1 |

但需要注意：

> 奖励不是越复杂越好。早期奖励应该简单、稳定、可解释。

建议初始 reward：

```text
有用 / 展开：+3
忽略：-1
不再提醒此类：-5
静默记录且无负反馈：0
当日通知超过阈值：额外 -2
```

---

### Policy 策略

策略就是：

```text
π(a|s) = 在状态 s 下选择动作 a 的概率
```

例子：

```text
如果用户正在 IDE 中停顿，建议类型是 bug_hint，置信度高，距离上次提醒超过 30 分钟，则弹窗概率高。

如果用户正在全屏会议，或者今天已经提醒很多次，则静默记录概率高。
```

---

## 4. DeskMate 强化学习数据集设计

RL 不像普通监督学习那样一开始就有完整标签。DeskMate 的数据要从用户交互中逐步积累。

### 4.1 数据来源

| 数据类型 | 来源 | 是否需要用户授权 |
|---|---|---|
| 场景识别结果 | VLM 输出 | 是 |
| 建议候选 | VLM / 规则生成 | 是 |
| 通知动作 | 决策模块 | 否，本地记录即可 |
| 用户反馈 | 点击、忽略、关闭、稍后 | 是，需说明 |
| 时间上下文 | 本地系统时间 | 否 |
| 前台应用类型 | 本地检测 | 建议说明 |
| 成本与延迟 | API 调用日志 | 否 |
| 原始截图 | 不建议默认保存 | 必须显式授权 |

---

### 4.2 单条训练样本格式

建议记录为 JSONL：

```json
{
  "episode_id": "2026-06-01-userlocal-001",
  "step": 12,
  "timestamp": "2026-06-01T14:32:05",
  "state": {
    "scene": "coding",
    "suggestion_type": "bug_hint",
    "vlm_confidence": 0.78,
    "priority": 3,
    "minutes_since_last_notification": 42,
    "notifications_today": 6,
    "user_activity_level": "paused",
    "is_fullscreen": false,
    "recent_ignore_rate": 0.35
  },
  "action": "popup",
  "reward": 3,
  "next_state": {
    "scene": "coding",
    "minutes_since_last_notification": 0,
    "notifications_today": 7,
    "recent_ignore_rate": 0.32
  },
  "done": false,
  "user_feedback": "expanded",
  "cost_usd": 0.003,
  "latency_ms": 1800
}
```

---

### 4.3 Episode 怎么定义？

强化学习通常按 episode 组织数据。

DeskMate 可以有几种 episode 定义方式：

| Episode 定义 | 适合阶段 | 说明 |
|---|---|---|
| 一天一个 episode | 推荐 | 每天从第一次使用到结束 |
| 一次专注 session 一个 episode | 适合工作节奏优化 | 从开始编码到休息 |
| 一个建议候选一个 episode | 适合 contextual bandit | 只看单次决策 |

早期建议：

> 先把每次建议决策看作一个独立样本，用 Contextual Bandit；等数据多了再升级到完整 RL。

---

## 5. 从简单到复杂：算法学习路径

### Level 1：规则策略 Baseline

难度：★☆☆☆☆

先不用 RL，写一个可解释规则系统。

示例：

```text
if priority <= 2:
    静默记录
elif minutes_since_last_notification < 30:
    静默记录
elif is_fullscreen:
    轻提示
else:
    弹窗
```

为什么要先做规则？

- 提供 baseline。
- 方便对比 RL 是否真的有提升。
- 避免一开始陷入算法复杂度。

学习目标：理解状态、动作、奖励在工程中的位置。

---

### Level 2：Contextual Bandit

难度：★★☆☆☆

Contextual Bandit 是最适合 DeskMate 早期的 RL 简化版本。

它只关心：

```text
当前状态下，哪个动作期望奖励最高？
```

不太关心长远状态转移。

适合场景：

- 推荐系统。
- 广告点击。
- 通知策略。
- 文案选择。

DeskMate 中非常适合：

```text
在当前上下文下，选择不提醒 / 轻提示 / 弹窗 中哪一个？
```

推荐算法：

| 算法 | 难度 | 说明 |
|---|---:|---|
| ε-greedy | ★★☆☆☆ | 偶尔探索，平时选当前最优 |
| UCB | ★★☆☆☆ | 对不确定动作给予探索机会 |
| Thompson Sampling | ★★★☆☆ | 用概率分布平衡探索与利用 |
| LinUCB | ★★★☆☆ | 适合带上下文特征的动作选择 |

推荐从 ε-greedy 开始。

---

### Level 3：Q-Learning

难度：★★★☆☆

Q-Learning 学习的是：

```text
Q(s, a) = 在状态 s 下采取动作 a 的长期价值
```

更新公式：

```text
Q(s,a) ← Q(s,a) + α [r + γ max Q(s',a') - Q(s,a)]
```

对应 DeskMate：

```text
某个场景下弹窗虽然当下可能有点击，但可能导致用户后面关闭通知。
Q-Learning 可以学习长期收益，而不是只看当前点击。
```

适合在有较多序列数据后使用。

---

### Level 4：Deep Q-Network, DQN

难度：★★★★☆

当状态空间很大，不能用表格 Q-Learning 时，可以用神经网络近似 Q 函数。

适合后期：

- 状态特征很多。
- 用户画像复杂。
- 动作空间变大。
- 数据量较多。

但不建议早期上 DQN。

原因：

- 数据量不够。
- 调参复杂。
- 可解释性差。
- 容易学到奇怪策略。

---

### Level 5：Policy Gradient / PPO

难度：★★★★★

PPO 等策略梯度算法适合复杂连续控制和大规模 RL。

DeskMate 不是游戏，也不是机器人控制，早期没有必要直接用 PPO。

可能适合的后期场景：

```text
同时优化提醒时机、提醒方式、文案风格、模型调用频率和长期留存。
```

但在真实产品中，PPO 的实验成本、风险控制和可解释性都是问题。

---

## 6. 推荐技术框架

### 6.1 早期最小实现

难度：★☆☆☆☆

建议自己实现：

- 规则策略。
- ε-greedy。
- 简单 bandit。
- 日志记录。

不急着上复杂框架。

可用技术：

```text
Python
SQLite / JSONL
pandas
matplotlib / plotly
pytest
```

---

### 6.2 中期实验框架

难度：★★★☆☆

如果要系统做实验：

| 工具 | 用途 |
|---|---|
| Gymnasium | 自定义 RL 环境 |
| Stable-Baselines3 | DQN / PPO 等现成算法 |
| PyTorch | 自定义模型 |
| Weights & Biases | 实验追踪 |
| TensorBoard | 训练曲线可视化 |
| pandas | 离线日志分析 |
| plotly / streamlit | 可视化 dashboard |

---

### 6.3 自定义 Gym 环境示例设计

DeskMate 可以定义一个模拟环境：

```python
class DeskMateNotifyEnv(gym.Env):
    def __init__(self, user_simulator):
        self.action_space = Discrete(3)  # 静默、轻提示、弹窗
        self.observation_space = Box(...)

    def reset(self):
        return initial_state

    def step(self, action):
        reward = user_simulator.respond(state, action)
        next_state = user_simulator.next_state(state, action)
        done = end_of_day
        return next_state, reward, done, info
```

注意：真实用户不能拿来随意探索，因此需要先做离线模拟环境。

---

## 7. 强化学习在 DeskMate 中的系统架构

建议架构：

```text
┌──────────────────────────┐
│       Capture / VLM       │
│  截屏、场景理解、建议候选   │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│     State Builder         │
│  构造 RL 状态特征          │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│     Policy Engine         │
│  规则 / Bandit / RL 策略   │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│      Action Executor      │
│  静默、轻提示、弹窗、稍后   │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│      Feedback Logger      │
│  用户反馈、奖励、下一状态   │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│      Offline Trainer      │
│  离线训练、评估、更新策略   │
└──────────────────────────┘
```

---

## 8. 数据集构建步骤

### Step 1：定义事件日志

先不要训练模型，先把数据记对。

必须记录：

- state。
- action。
- reward。
- next_state。
- timestamp。
- user_feedback。
- suggestion_type。

---

### Step 2：用规则策略收集初始数据

早期不能让未训练 RL 直接控制用户体验。

先用规则策略：

```text
低优先级静默
中优先级轻提示
高优先级弹窗
30 分钟内不重复
```

收集一段时间数据。

---

### Step 3：离线分析反馈

看这些指标：

- 哪类建议最容易被点击？
- 哪个时间段忽略率最高？
- 通知次数超过多少后关闭率上升？
- 弹窗相比轻提示是否真的更有效？
- VLM confidence 和用户采纳是否相关？

---

### Step 4：训练 Bandit / Q-Learning

用历史数据训练策略。

但要注意：历史数据只包含规则策略曾经选择过的动作，没法完全知道其他动作会怎样。

这叫 **离线策略评估问题**。

---

### Step 5：小流量在线实验

不要直接替换规则策略。

建议：

```text
90% 使用规则策略
10% 使用学习策略
```

观察是否提升：

- 采纳率。
- 忽略率。
- 关闭率。
- 日均打扰次数。

---

## 9. 调参指南

### 9.1 ε-greedy 参数

| 参数 | 含义 | 建议初始值 |
|---|---|---:|
| epsilon | 探索概率 | 0.1 |
| min_epsilon | 最小探索率 | 0.02 |
| decay | 探索衰减 | 0.995 |

说明：

- epsilon 太高：用户体验不稳定。
- epsilon 太低：学不到新策略。
- 产品场景中探索要保守。

---

### 9.2 Q-Learning 参数

| 参数 | 含义 | 建议初始值 |
|---|---|---:|
| alpha | 学习率 | 0.05 - 0.2 |
| gamma | 折扣因子 | 0.8 - 0.95 |
| epsilon | 探索率 | 0.05 - 0.1 |

说明：

- gamma 高：更重视长期用户体验。
- gamma 低：更重视当前点击反馈。
- DeskMate 推荐 gamma 偏高，因为打扰体验是长期问题。

---

### 9.3 Reward 权重调参

初始建议：

```text
展开 / 有用：+3
稍后：+1
忽略：-1
不再提醒此类：-5
关闭应用：-10
当天超过提醒阈值：-2
```

后续可以调：

- 如果系统太保守：提高有用反馈奖励。
- 如果系统太烦人：加大忽略和关闭惩罚。
- 如果系统总是静默：给高置信建议被静默时增加机会成本。

---

### 9.4 动作空间调参

早期动作越少越好。

建议演进：

```text
3 动作：静默 / 轻提示 / 弹窗
↓
5 动作：丢弃 / 静默 / 轻提示 / 弹窗 / 稍后
↓
组合动作：方式 × 延迟 × 文案
```

如果动作空间太大，会导致：

- 探索成本上升。
- 每个动作样本不足。
- 学习不稳定。

---

## 10. 可视化设计

强化学习一定要可视化，否则很难判断是否学到了好策略。

### 10.1 基础指标面板

建议用 Streamlit 或 Plotly 做本地 dashboard。

需要展示：

| 图表 | 说明 |
|---|---|
| 每日通知次数 | 是否过度打扰 |
| 每日采纳率 | 建议是否有用 |
| 忽略率趋势 | 是否越来越烦 |
| suggestion_type 分布 | 哪类建议最多 |
| action 分布 | 策略是否过度弹窗或过度静默 |
| reward 曲线 | 策略整体收益 |
| 不同时间段 reward | 判断何时适合提醒 |
| VLM confidence vs feedback | 模型置信度是否可信 |

---

### 10.2 RL 训练曲线

常见训练图：

```text
Episode Reward 曲线
Average Reward 移动平均
Exploration Rate 曲线
Action Distribution 曲线
Policy Change 曲线
```

---

### 10.3 示例 dashboard 结构

```text
DeskMate RL Dashboard

1. 总览
   - 今日通知次数
   - 7 日采纳率
   - 7 日忽略率
   - 平均 reward

2. 策略行为
   - 静默 / 轻提示 / 弹窗占比
   - 不同场景下的动作分布

3. 用户反馈
   - 各建议类型采纳率
   - 各时间段忽略率

4. 成本与收益
   - API 调用次数
   - 单次成本
   - reward per dollar

5. 调参实验
   - 不同 epsilon / gamma / reward 权重对比
```

---

## 11. 学习路径设计

## 阶段 A：基础概念

难度：★☆☆☆☆

目标：理解 RL 的基本语言。

学习内容：

- Agent。
- Environment。
- State。
- Action。
- Reward。
- Policy。
- Episode。
- Return。
- Exploration vs Exploitation。

对应 DeskMate：

- Agent = 通知策略。
- Environment = 用户和桌面。
- Action = 是否提醒。
- Reward = 用户反馈。

练习：

> 用文字写出 DeskMate 通知策略的 State / Action / Reward。

---

## 阶段 B：规则 Baseline

难度：★☆☆☆☆

目标：先不用 RL，建立可对比的规则系统。

学习内容：

- 策略函数。
- if-else baseline。
- 指标设计。
- 日志采集。

练习：

> 实现一个 `DecisionPolicy`，根据 priority 和冷却时间决定提醒方式。

---

## 阶段 C：Contextual Bandit

难度：★★☆☆☆

目标：学习最适合推荐/通知类问题的 RL 入门算法。

学习内容：

- ε-greedy。
- UCB。
- Thompson Sampling。
- LinUCB。

练习：

> 给定不同场景和用户反馈，训练一个策略决定静默、轻提示还是弹窗。

---

## 阶段 D：Q-Learning

难度：★★★☆☆

目标：理解长期奖励。

学习内容：

- Q-table。
- Bellman Equation。
- Temporal Difference Learning。
- alpha / gamma / epsilon。

练习：

> 模拟一天的 DeskMate 通知序列，学习什么时候提醒不会导致后续忽略率升高。

---

## 阶段 E：DQN

难度：★★★★☆

目标：当状态太多时，用神经网络近似 Q 函数。

学习内容：

- Experience Replay。
- Target Network。
- Q-network。
- Overestimation。

练习：

> 用用户行为模拟器训练 DQN，比较它和规则策略的 reward。

---

## 阶段 F：PPO / Policy Gradient

难度：★★★★★

目标：了解复杂策略优化，不作为早期落地重点。

学习内容：

- Policy Gradient。
- Advantage。
- PPO clipping。
- Actor-Critic。

练习：

> 用 Stable-Baselines3 在模拟环境中训练 PPO，但只作为学习实验，不直接用于真实用户。

---

## 12. 推荐学习顺序

建议按下面顺序学习，不要一上来就看 PPO：

```text
1. DeskMate 通知策略规则版
2. 日志与 reward 设计
3. ε-greedy Bandit
4. UCB / Thompson Sampling
5. Q-Learning
6. 自定义 Gymnasium 环境
7. DQN
8. PPO
9. 离线策略评估
10. 在线 A/B 实验
```

---

## 13. 常见问题与坑

### Q1：是不是所有智能决策都要用强化学习？

不是。

DeskMate 中很多问题不适合 RL：

- 截屏。
- 人脸模糊。
- 日历读取。
- JSON 解析。
- 基础场景识别。

RL 适合的是：

> 多次决策 + 用户反馈 + 长期收益权衡。

---

### Q2：为什么不直接用 PPO？

因为 PPO 对早期 DeskMate 太重了。

问题：

- 数据少。
- 用户不能承受大量随机探索。
- 可解释性差。
- 调参成本高。

更好的路线：

```text
规则 → Bandit → Q-Learning → DQN / PPO
```

---

### Q3：没有数据能不能做 RL？

可以先做模拟环境，但真实效果有限。

早期应该：

1. 用规则策略上线。
2. 收集用户反馈。
3. 离线训练。
4. 小流量实验。

不要让未训练模型直接控制真实通知。

---

### Q4：Reward 怎么设计才对？

没有绝对正确，只能迭代。

原则：

- 简单。
- 可解释。
- 和产品目标一致。
- 对负反馈足够敏感。

DeskMate 的产品目标不是最大化点击，而是最大化：

```text
有用建议 - 打扰成本 - API 成本
```

可以写成：

```text
reward = user_value - interruption_cost - api_cost
```

---

### Q5：RL 会不会学会永远不提醒？

会。

如果忽略惩罚太大，而有用奖励太小，策略可能学到：

> 不提醒最安全。

解决：

- 适当给高价值建议机会。
- 使用探索策略。
- 对静默策略也评估机会成本。
- 保留规则兜底。

---

### Q6：RL 会不会学会疯狂弹窗？

也会。

如果点击奖励太高，而打扰惩罚太低，策略可能学到频繁弹窗。

解决：

- 加入每日通知惩罚。
- 加入忽略率惩罚。
- 加入关闭应用惩罚。
- 设置硬性上限，例如每天最多 10 次主动提醒。

---

### Q7：真实用户能不能用于探索？

可以，但必须非常保守。

建议：

- 探索率低。
- 不探索高打扰动作。
- 用户可以关闭实验策略。
- 所有策略有规则安全边界。

例如：

```text
RL 可以在“静默”和“轻提示”之间探索，
但不能随意突破每日弹窗上限。
```

---

### Q8：如何评估 RL 策略比规则好？

看这些指标：

- 平均 reward 是否提高。
- 采纳率是否提高。
- 忽略率是否降低。
- 日均通知是否下降。
- 用户关闭率是否下降。
- reward per cost 是否提升。

不要只看点击率。

---

### Q9：离线历史数据能不能直接训练最优策略？

不能完全相信。

因为历史数据来自旧策略，你不知道旧策略没选的动作会产生什么反馈。

这叫：

> Off-policy evaluation / counterfactual evaluation 问题。

早期可以接受近似，但产品上线前要小流量 A/B。

---

### Q10：如何避免策略不可解释？

建议：

- 早期用规则和 Bandit。
- 输出动作原因。
- 可视化各状态下动作分布。
- 保留人工配置上限。
- 对高风险动作使用规则兜底。

例如：

```json
{
  "action": "silent_log",
  "reason": "今天已提醒 8 次，且同类建议 30 分钟内出现过"
}
```

---

## 14. 推荐落地里程碑

### Milestone 1：无 RL，仅规则

难度：★☆☆☆☆

目标：

- 实现状态构造。
- 实现动作执行。
- 实现反馈日志。

输出：

- `StateBuilder`
- `DecisionPolicy`
- `FeedbackLogger`

---

### Milestone 2：Bandit 实验

难度：★★☆☆☆

目标：

- 用历史日志训练 ε-greedy 或 UCB。
- 比较规则策略和 bandit 策略。

输出：

- `BanditPolicy`
- `policy_eval.ipynb`
- 基础 reward 曲线

---

### Milestone 3：模拟环境

难度：★★★☆☆

目标：

- 构造一个用户模拟器。
- 用 Gymnasium 包装 DeskMate 通知环境。

输出：

- `DeskMateNotifyEnv`
- `UserSimulator`
- `train_q_learning.py`

---

### Milestone 4：Q-Learning / DQN

难度：★★★★☆

目标：

- 学习长期通知策略。
- 比较 DQN 和 Q-table。

输出：

- Q-learning 训练脚本。
- DQN 训练脚本。
- TensorBoard 曲线。

---

### Milestone 5：可视化 Dashboard

难度：★★★☆☆

目标：

- 让策略行为可解释。
- 让调参结果可比较。

输出：

- Streamlit dashboard。
- 每日通知趋势。
- reward 曲线。
- 动作分布。
- 用户反馈分析。

---

## 15. 建议新增到项目中的文档与目录

后续如果正式落地 RL，建议增加：

```text
docs/
  RL_LEARNING.md
  RL_EXPERIMENTS.md

src/deskmate/rl/
  state.py
  actions.py
  reward.py
  policy_rule.py
  policy_bandit.py
  policy_q_learning.py
  env.py
  simulator.py

notebooks/
  01_feedback_analysis.ipynb
  02_bandit_experiment.ipynb
  03_q_learning_simulation.ipynb

visualization/
  dashboard.py
```

---

## 16. 最小可行 RL 学习项目

如果你想通过 DeskMate 重新学习 RL，建议第一个学习项目不要接 VLM、不要接摄像头、不要接真实 UI。

只做一个模拟器：

```text
输入：模拟用户状态
动作：静默 / 轻提示 / 弹窗
反馈：根据规则生成 reward
目标：训练策略最大化长期 reward
```

### 模拟用户规则示例

```text
如果用户正在 coding 且 suggestion_type=bug_hint：
  弹窗有 60% 概率 +3，有 20% 概率 -1

如果用户正在 meeting：
  弹窗有 80% 概率 -3

如果今天通知超过 8 次：
  任意弹窗额外 -2

如果距离上次通知小于 10 分钟：
  任意弹窗额外 -2
```

这样你可以完整学习：

- 状态设计。
- 动作设计。
- reward 设计。
- Q-learning。
- epsilon 探索。
- reward 曲线。
- 策略可视化。

---

## 17. 当前建议下一步

建议在项目中按以下顺序推进：

1. 先完成 `docs/ITERATION.md` 中的工程骨架初始化。
2. 实现规则版 `DecisionPolicy`。
3. 设计并记录通知事件日志。
4. 创建 `docs/RL_LEARNING.md` 作为强化学习学习主文档。
5. 在 `src/deskmate/rl/` 中实现一个不依赖真实用户的模拟环境。
6. 先做 Contextual Bandit，再做 Q-Learning。
7. 最后再考虑 DQN / PPO。

---

## 18. 一句话总结

DeskMate 中最值得用强化学习的不是“看懂屏幕”，而是：

> 学会在不同用户、不同场景、不同历史反馈下，选择最合适的提醒策略，让 AI 建议既有用又不烦。

这正好覆盖了强化学习最核心的学习内容：状态、动作、奖励、策略、探索、长期收益和个性化优化。
