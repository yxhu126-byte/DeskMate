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
