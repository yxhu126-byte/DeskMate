/**
 * DeskMate 主应用
 * 负责：全局状态管理、UI 交互、模块协调
 */
const App = {
  // ── 状态 ──
  state: {
    cameraOn: false,
    screenShareOn: false,
    micOn: false,
    isRecording: false,
    currentMode: 'general',
    backendOnline: false,
    // 专注陪伴模式
    focus: {
      active: false,
      task: '',
      duration: 30,          // 分钟
      frequency: 30,         // 秒
      tickCount: 0,
      lastHash: null,
      intervalId: null,
      timerId: null,         // 状态栏计时器
      startTime: null,       // 开始时间戳
    },
  },

  // ── 初始化 ──
  async init() {
    console.log('🚀 DeskMate v1.0.0-demo 初始化...');
    console.log('  浏览器:', navigator.userAgent);
    console.log('  支持 getUserMedia:', !!navigator.mediaDevices?.getUserMedia);
    console.log('  支持 getDisplayMedia:', !!navigator.mediaDevices?.getDisplayMedia);

    this._bindEvents();
    ChatManager.init(document.getElementById('chatPanel'));

    // 检查后端健康状态
    await this._checkBackend();

    // 更新状态显示
    this._updateAllStatusIndicators();

    console.log('✅ DeskMate 初始化完成');
  },

  // ── 摄像头操作 ──
  async toggleCamera() {
    if (this.state.cameraOn) {
      CameraManager.stop();
      this.state.cameraOn = false;
      document.getElementById('cameraPreview').classList.add('hidden');
    } else {
      try {
        await CameraManager.start(document.getElementById('cameraVideo'));
        this.state.cameraOn = true;
        document.getElementById('cameraPreview').classList.remove('hidden');
      } catch (err) {
        this._showError(err.message);
        this.state.cameraOn = false;
      }
    }
    this._updateInputSources();
    this._updateAllStatusIndicators();
  },

  // ── 屏幕共享操作 ──
  async toggleScreenShare() {
    if (this.state.screenShareOn) {
      ScreenShareManager.stop();
      this.state.screenShareOn = false;
      document.getElementById('screenPreview').classList.add('hidden');
    } else {
      try {
        await ScreenShareManager.start(
          document.getElementById('screenVideo'),
          () => {
            // 用户通过浏览器 UI 停止时的回调
            this.state.screenShareOn = false;
            document.getElementById('screenPreview').classList.add('hidden');
            this._updateInputSources();
            this._updateAllStatusIndicators();
          }
        );
        this.state.screenShareOn = true;
        document.getElementById('screenPreview').classList.remove('hidden');
      } catch (err) {
        this._showError(err.message);
        this.state.screenShareOn = false;
      }
    }
    this._updateInputSources();
    this._updateAllStatusIndicators();
  },

  // ── 麦克风操作 ──
  async toggleMic() {
    if (this.state.micOn) {
      if (this.state.isRecording) {
        // 先停止录音
        await this._stopRecording();
      }
      MicManager.stop();
      this.state.micOn = false;
    } else {
      try {
        await MicManager.start();
        this.state.micOn = true;
      } catch (err) {
        this._showError(err.message);
        this.state.micOn = false;
      }
    }
    this._updateInputSources();
    this._updateAllStatusIndicators();
  },

  // ── 录音操作 ──
  async toggleRecording() {
    if (!this.state.micOn) {
      this._showError('请先开启麦克风');
      return;
    }

    if (this.state.isRecording) {
      await this._stopRecording();
    } else {
      this._startRecording();
    }
  },

  _startRecording() {
    try {
      MicManager.startRecording();
      this.state.isRecording = true;

      const btn = document.getElementById('recordBtn');
      btn.classList.add('recording');
      btn.querySelector('.btn-label').textContent = '停止录音';

      document.getElementById('recordingIndicator').classList.remove('hidden');

      console.log('🎤 录音中...');
    } catch (err) {
      this._showError(err.message);
    }
  },

  async _stopRecording() {
    try {
      const audioBlob = await MicManager.stopRecording();
      this.state.isRecording = false;

      const btn = document.getElementById('recordBtn');
      btn.classList.remove('recording');
      btn.querySelector('.btn-label').textContent = '语音输入';
      document.getElementById('recordingIndicator').classList.add('hidden');

      if (audioBlob && audioBlob.size > 100) {
        // 发送语音进行转写和回答
        const textInput = document.getElementById('chatInput');
        textInput.placeholder = '正在转写语音...';
        textInput.disabled = true;

        const result = await ChatManager.sendVoice(audioBlob);

        textInput.placeholder = '输入问题，或点击语音按钮...';
        textInput.disabled = false;

        // 如果是演示模式（返回null），聚焦输入框让用户手动输入
        if (result === null) {
          textInput.focus();
        }
      } else {
        this._showError('录音内容为空，请重试');
      }
    } catch (err) {
      console.error('停止录音失败:', err);
      this.state.isRecording = false;
      document.getElementById('recordingIndicator').classList.add('hidden');
    }
  },

  // ── 发送消息 ──
  async sendMessage() {
    const input = document.getElementById('chatInput');
    const userText = input.value.trim();

    if (!userText) {
      this._showError('请输入问题');
      return;
    }

    // 收集图片
    const images = [];
    const sendScreen = document.getElementById('sendScreenCheck').checked;
    const sendCamera = document.getElementById('sendCameraCheck').checked;

    if (sendScreen && this.state.screenShareOn && ScreenShareManager.isReady()) {
      try {
        const screenFrame = ScreenShareManager.captureFrame();
        images.push(screenFrame);
        console.log(`📺 截取屏幕帧: ${screenFrame.width}x${screenFrame.height}, ${Format.bytes(screenFrame.sizeBytes)}`);
      } catch (err) {
        console.warn('屏幕截图失败:', err);
      }
    }

    if (sendCamera && this.state.cameraOn && CameraManager.isReady()) {
      try {
        const cameraFrame = CameraManager.captureFrame();
        images.push(cameraFrame);
        console.log(`📷 截取摄像头帧: ${cameraFrame.width}x${cameraFrame.height}, ${Format.bytes(cameraFrame.sizeBytes)}`);
      } catch (err) {
        console.warn('摄像头截图失败:', err);
      }
    }

    // 清空输入框
    input.value = '';
    input.style.height = 'auto';

    // 禁用发送按钮
    const sendBtn = document.getElementById('sendBtn');
    sendBtn.disabled = true;
    sendBtn.textContent = '...';

    try {
      await ChatManager.sendMessage(userText, images);
    } catch (err) {
      // 错误已在 chat.js 中处理
    } finally {
      sendBtn.disabled = false;
      sendBtn.textContent = '发送';
    }
  },

  // ── 模式切换 ──
  setMode(mode) {
    this.state.currentMode = mode;
    ChatManager.setMode(mode);
    console.log(`切换到模式: ${mode}`);
  },

  // ── 一键停止 ──
  stopAll() {
    if (this.state.cameraOn) {
      CameraManager.stop();
      this.state.cameraOn = false;
      document.getElementById('cameraPreview').classList.add('hidden');
    }
    if (this.state.screenShareOn) {
      ScreenShareManager.stop();
      this.state.screenShareOn = false;
      document.getElementById('screenPreview').classList.add('hidden');
    }
    if (this.state.micOn) {
      if (this.state.isRecording) {
        MicManager.mediaRecorder?.stop();
        this.state.isRecording = false;
      }
      MicManager.stop();
      this.state.micOn = false;
      document.getElementById('recordingIndicator').classList.add('hidden');
    }
    if (this.state.focus.active) {
      // 结束专注但不获取简报（用户是"全部停止"不是正常结束）
      this._stopFocusTimer();
      if (this.state.focus.intervalId) {
        clearInterval(this.state.focus.intervalId);
        this.state.focus.intervalId = null;
      }
      this.state.focus.active = false;
      document.getElementById('focusStatusBarItem').style.display = 'none';
    }

    this._updateInputSources();
    this._updateAllStatusIndicators();
    console.log('🛑 已停止全部输入源');
  },

  // ── 清除会话 ──
  async clearChat() {
    if (confirm('确定要清除当前对话记录吗？')) {
      await ChatManager.clearSession();
      document.getElementById('lastUsedSources').textContent = '';
    }
  },

  // ── 隐私提示 ──
  showPrivacyInfo() {
    const tips = [
      '📺 仅共享你需要 AI 查看的窗口或标签页',
      '🔒 截图仅在本次问答中使用，服务器不永久保存',
      '👁️ 你始终可以看到 AI 当前正在使用哪些输入源',
      '🛑 随时点击「全部停止」可立即关闭所有采集',
      '💡 建议关闭包含密码、聊天记录等敏感信息的窗口后再共享屏幕',
    ];
    alert('🔒 隐私与安全提示\n\n' + tips.join('\n\n'));
  },

  // ── 专注模式操作 ──

  /**
   * 打开专注设置面板
   */
  openFocusSetup() {
    if (!this.state.screenShareOn) {
      this._showError('请先开启屏幕共享，AI 需要观察你的屏幕才能进行专注陪伴');
      return;
    }
    document.getElementById('focusTaskInput').value = '';
    document.getElementById('focusModalOverlay').classList.remove('hidden');
    document.getElementById('focusTaskInput').focus();
  },

  /**
   * 关闭专注设置面板
   */
  closeFocusSetup() {
    document.getElementById('focusModalOverlay').classList.add('hidden');
  },

  /**
   * 开始专注
   */
  startFocus() {
    const task = document.getElementById('focusTaskInput').value.trim();
    if (!task) {
      this._showError('请输入任务描述，AI 需要知道你的目标才能判断是否走神');
      return;
    }

    const duration = parseInt(document.getElementById('focusDurationSelect').value);
    const frequency = parseInt(document.getElementById('focusFrequencySelect').value);

    this.state.focus.active = true;
    this.state.focus.task = task;
    this.state.focus.duration = duration;
    this.state.focus.frequency = frequency;
    this.state.focus.tickCount = 0;
    this.state.focus.lastHash = null;
    this.state.focus.startTime = Date.now();

    // 关闭设置面板
    this.closeFocusSetup();

    // 更新 UI
    document.getElementById('focusBtn').classList.add('active');
    document.getElementById('focusBtn').querySelector('.btn-label').textContent = '结束专注';

    // 显示状态栏
    const statusBarItem = document.getElementById('focusStatusBarItem');
    statusBarItem.style.display = 'flex';
    document.getElementById('focusStatusText').textContent =
      task.length > 15 ? task.substring(0, 15) + '...' : task;

    // 启动计时器
    this._startFocusTimer();

    ChatManager.addFocusSystemMessage(
      `🎯 专注模式已开启\n📋 任务：${task}\n⏱ 预计：${duration} 分钟 · 观察频率：每 ${frequency} 秒\n\nAI 会在你走神时提醒你，加油！`
    );

    console.log(`🎯 专注模式已开启: "${task}" ${duration}分钟 @${frequency}s`);
  },

  /**
   * 结束专注
   */
  stopFocus() {
    if (!this.state.focus.active) return;

    const minutes = Math.round((Date.now() - this.state.focus.startTime) / 60000);

    // 停止轮询循环（PR #6 会实现）
    if (this.state.focus.intervalId) {
      clearInterval(this.state.focus.intervalId);
      this.state.focus.intervalId = null;
    }

    // 停止计时器
    this._stopFocusTimer();

    // 重置状态
    this.state.focus.active = false;
    this.state.focus.task = '';
    this.state.focus.tickCount = 0;
    this.state.focus.lastHash = null;
    this.state.focus.startTime = null;

    // 更新 UI
    const focusBtn = document.getElementById('focusBtn');
    focusBtn.classList.remove('active');
    focusBtn.querySelector('.btn-label').textContent = '开始专注';

    // 隐藏状态栏
    document.getElementById('focusStatusBarItem').style.display = 'none';

    ChatManager.addFocusSystemMessage(
      `✅ 专注模式已结束 · 共 ${minutes} 分钟\n（任务简报将在 PR #8 实现）`
    );

    console.log(`🎯 专注模式已结束，共 ${minutes} 分钟`);
  },

  /**
   * 启动状态栏计时器
   */
  _startFocusTimer() {
    this._stopFocusTimer();
    const update = () => {
      if (!this.state.focus.active) return;
      const elapsed = Math.floor((Date.now() - this.state.focus.startTime) / 1000);
      const m = String(Math.floor(elapsed / 60)).padStart(2, '0');
      const s = String(elapsed % 60).padStart(2, '0');
      document.getElementById('focusTimer').textContent = `${m}:${s}`;
    };
    update();
    this.state.focus.timerId = setInterval(update, 1000);
  },

  /**
   * 停止状态栏计时器
   */
  _stopFocusTimer() {
    if (this.state.focus.timerId) {
      clearInterval(this.state.focus.timerId);
      this.state.focus.timerId = null;
    }
  },

  // ── 内部方法 ──

  _bindEvents() {
    // 发送按钮
    document.getElementById('sendBtn').addEventListener('click', () => this.sendMessage());

    // Enter 发送
    document.getElementById('chatInput').addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.sendMessage();
      }
    });

    // 自动调整输入框高度
    document.getElementById('chatInput').addEventListener('input', (e) => {
      e.target.style.height = 'auto';
      e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
    });

    // 模式按钮
    document.querySelectorAll('.mode-btn').forEach(btn => {
      btn.addEventListener('click', () => this.setMode(btn.dataset.mode));
    });

    // 控制按钮
    document.getElementById('cameraBtn').addEventListener('click', () => this.toggleCamera());
    document.getElementById('screenBtn').addEventListener('click', () => this.toggleScreenShare());
    document.getElementById('micBtn').addEventListener('click', () => this.toggleMic());
    document.getElementById('recordBtn').addEventListener('click', () => this.toggleRecording());
    document.getElementById('stopAllBtn').addEventListener('click', () => this.stopAll());
    document.getElementById('clearChatBtn').addEventListener('click', () => this.clearChat());
    document.getElementById('privacyBtn').addEventListener('click', () => this.showPrivacyInfo());

    // 专注模式
    document.getElementById('focusBtn').addEventListener('click', () => {
      if (this.state.focus.active) {
        this.stopFocus();
      } else {
        this.openFocusSetup();
      }
    });
    document.getElementById('focusStartBtn').addEventListener('click', () => this.startFocus());
    document.getElementById('focusCancelBtn').addEventListener('click', () => this.closeFocusSetup());
    // 点击弹窗背景关闭
    document.getElementById('focusModalOverlay').addEventListener('click', (e) => {
      if (e.target === e.currentTarget) this.closeFocusSetup();
    });
  },

  _updateInputSources() {
    ChatManager.updateInputSources({
      screen: this.state.screenShareOn,
      camera: this.state.cameraOn,
      microphone: this.state.micOn,
    });

    // 更新截图选项的可见性
    document.getElementById('sendScreenOption').style.display = this.state.screenShareOn ? 'flex' : 'none';
    document.getElementById('sendCameraOption').style.display = this.state.cameraOn ? 'flex' : 'none';
  },

  _updateAllStatusIndicators() {
    this._updateIndicator('cameraStatus', 'cameraIndicator', this.state.cameraOn);
    this._updateIndicator('screenStatus', 'screenIndicator', this.state.screenShareOn);
    this._updateIndicator('micStatus', 'micIndicator', this.state.micOn);

    // 按钮状态
    this._updateButtonState('cameraBtn', this.state.cameraOn, '摄像头', '摄像头');
    this._updateButtonState('screenBtn', this.state.screenShareOn, '屏幕共享', '屏幕共享');
    this._updateButtonState('micBtn', this.state.micOn, '麦克风', '麦克风');

    // 专注按钮状态
    const focusBtn = document.getElementById('focusBtn');
    if (this.state.focus.active) {
      focusBtn.classList.add('active');
      focusBtn.querySelector('.btn-label').textContent = '结束专注';
    } else {
      focusBtn.classList.remove('active');
      focusBtn.querySelector('.btn-label').textContent = '开始专注';
    }

    // 录音按钮
    const recordBtn = document.getElementById('recordBtn');
    if (this.state.isRecording) {
      recordBtn.classList.add('recording');
      recordBtn.querySelector('.btn-label').textContent = '停止录音';
    } else {
      recordBtn.classList.remove('recording');
      recordBtn.querySelector('.btn-label').textContent = '语音输入';
    }

    // 后端状态
    document.getElementById('backendIndicator').className =
      `status-indicator ${this.state.backendOnline ? 'online' : 'offline'}`;
    document.getElementById('backendStatus').textContent =
      this.state.backendOnline ? '后端已连接' : '后端未连接（演示模式）';
  },

  _updateIndicator(statusId, indicatorId, isOn) {
    const statusEl = document.getElementById(statusId);
    const indicatorEl = document.getElementById(indicatorId);

    if (isOn) {
      indicatorEl.classList.add('active');
      indicatorEl.classList.remove('inactive');
      statusEl.textContent = '开启';
      statusEl.classList.add('status-on');
      statusEl.classList.remove('status-off');
    } else {
      indicatorEl.classList.add('inactive');
      indicatorEl.classList.remove('active');
      statusEl.textContent = '关闭';
      statusEl.classList.add('status-off');
      statusEl.classList.remove('status-on');
    }
  },

  _updateButtonState(btnId, isOn, labelOn, labelOff) {
    const btn = document.getElementById(btnId);
    if (isOn) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  },

  async _checkBackend() {
    try {
      const health = await apiClient.healthCheck();
      this.state.backendOnline = health.status === 'ok';
      console.log(`后端状态: ${health.status === 'ok' ? '✅ 在线' : '❌ 异常'}, 提供商: ${health.ai_provider}`);
    } catch (err) {
      this.state.backendOnline = false;
      console.warn('后端未连接，将使用演示模式:', err.message);
    }
    this._updateAllStatusIndicators();
  },

  _showError(message) {
    console.error(message);

    // 创建 toast 提示
    const toast = document.createElement('div');
    toast.className = 'toast toast-error';
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
      toast.classList.add('toast-fade-out');
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  },
};


// ── 启动应用 ──
document.addEventListener('DOMContentLoaded', () => {
  App.init();
});
