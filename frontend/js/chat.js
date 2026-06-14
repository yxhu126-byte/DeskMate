/**
 * 对话管理模块
 * 负责：消息展示、API 调用、会话管理
 */
const ChatManager = {
  sessionId: null,
  messages: [],
  chatPanelEl: null,
  currentMode: 'general',
  inputSources: {
    screen: false,
    camera: false,
    microphone: false,
  },

  /**
   * 初始化对话
   */
  init(chatPanelElement) {
    this.chatPanelEl = chatPanelElement;
    this.sessionId = Format.uuid();
    this.messages = [];
    this._renderWelcome();
  },

  /**
   * 发送一条消息 (文本 + 可选图片)
   */
  async sendMessage(userText, images = []) {
    if (!userText.trim() && images.length === 0) return;

    // 添加用户消息到界面
    this._addMessageToUI('user', userText, images);

    // 显示加载状态
    const loadingMsg = this._addLoadingMessage();

    try {
      // 调用后端 API
      const response = await apiClient.multimodalChat({
        sessionId: this.sessionId,
        userText: userText,
        mode: this.currentMode,
        inputSources: this.inputSources,
        images: images.map(img => ({
          type: img.type,
          mime_type: img.mime_type,
          data: img.data,
        })),
      });

      // 移除加载状态
      this._removeLoadingMessage(loadingMsg);

      // 显示 AI 回答
      this._addMessageToUI('assistant', response.answer, [], response.used_sources, response.uncertainty);

      // 更新输入源状态
      this._updateSourceIndicators(response.used_sources);

      return response;
    } catch (err) {
      this._removeLoadingMessage(loadingMsg);
      this._addMessageToUI('assistant', `❌ 出错了: ${err.message}`);
      console.error('对话请求失败:', err);
      throw err;
    }
  },

  /**
   * 发送语音消息
   */
  async sendVoice(audioBlob) {
    // 添加临时消息
    const tempMsg = this._addMessageToUI('user', '🎤 正在识别语音...');

    try {
      // 先转写
      const transcribeResult = await apiClient.transcribeSpeech(this.sessionId, audioBlob);
      const transcribedText = (transcribeResult.text || '').trim();

      if (!transcribedText) {
        App._showError(transcribeResult.message || '语音转写未配置或未识别到内容，请手动输入问题');
        return null;
      }

      // 将转写文本填入输入框，让用户确认后发送
      const input = document.getElementById('chatInput');
      input.value = transcribedText;
      input.focus();
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 120) + 'px';

      if (typeof App?.markPendingVoiceTranscript === 'function') {
        App.markPendingVoiceTranscript();
      }

      return transcribedText;
    } catch (err) {
      App._showError('语音转写失败，请手动输入问题');
      err.userNotified = true;
      console.error('语音转写失败:', err);
      throw err;
    } finally {
      this._removeLoadingMessage(tempMsg);
    }
  },

  /**
   * 设置当前模式
   */
  setMode(mode) {
    this.currentMode = mode;
    document.querySelectorAll('.mode-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.mode === mode);
    });
  },

  /**
   * 添加专注模式系统消息（开启/结束通知）
   */
  addFocusSystemMessage(text) {
    // 移除欢迎页
    const welcome = this.chatPanelEl.querySelector('.welcome-screen');
    if (welcome) welcome.remove();

    const msgDiv = document.createElement('div');
    msgDiv.className = 'message message-system';
    msgDiv.innerHTML = `
      <div class="message-avatar">🎯</div>
      <div class="message-content">
        <div class="message-text"><p>${Format.markdown(text)}</p></div>
      </div>
    `;
    this.chatPanelEl.appendChild(msgDiv);
    this.chatPanelEl.scrollTop = this.chatPanelEl.scrollHeight;
  },

  /**
   * 显示专注模式走神提醒消息
   */
  addFocusAlertMessage(alertText) {
    const welcome = this.chatPanelEl.querySelector('.welcome-screen');
    if (welcome) welcome.remove();

    const msgDiv = document.createElement('div');
    msgDiv.className = 'message message-focus-alert';
    msgDiv.innerHTML = `
      <div class="message-avatar">🔔</div>
      <div class="message-content">
        <div class="message-header">
          <span class="message-role">专注提醒</span>
          <span class="message-time">${Format.time()}</span>
        </div>
        <div class="message-text"><p>${Format.markdown(alertText)}</p></div>
      </div>
    `;
    this.chatPanelEl.appendChild(msgDiv);
    this.chatPanelEl.scrollTop = this.chatPanelEl.scrollHeight;
  },

  /**
   * 展示专注简报卡片
   */
  addFocusReportCard(reportData) {
    const welcome = this.chatPanelEl.querySelector('.welcome-screen');
    if (welcome) welcome.remove();

    const msgDiv = document.createElement('div');
    msgDiv.className = 'message message-focus-report';

    const pct = reportData.total_minutes > 0
      ? Math.round(reportData.focused_minutes / reportData.total_minutes * 100)
      : 0;

    const timelineHTML = reportData.segments && reportData.segments.length > 0
      ? reportData.segments.map(s => {
          const icons = { focused: '🟢', distracted: '🟡', away: '⚪' };
          const labels = { focused: '专注', distracted: '走神', away: '离开' };
          const icon = icons[s.status] || '●';
          const label = labels[s.status] || s.status;
          return `<div class="report-timeline-item">
            <span class="report-timeline-icon">${icon}</span>
            <span class="report-timeline-time">${s.start_time} - ${s.end_time || '?'}</span>
            <span class="report-timeline-status">${label}</span>
            <span class="report-timeline-note">${s.note || ''}</span>
          </div>`;
        }).join('')
      : '<div class="report-timeline-empty">(无详细时间线)</div>';

    const suggestionsHTML = reportData.suggestions && reportData.suggestions.length > 0
      ? reportData.suggestions.map(s => `<li>${s}</li>`).join('')
      : '<li>继续保持！</li>';

    msgDiv.innerHTML = `
      <div class="report-card">
        <div class="report-header">
          <span class="report-icon">📊</span>
          <span class="report-title">专注简报</span>
          <span class="report-task">${this._escapeHtml(reportData.task || '未记录')}</span>
        </div>

        <div class="report-stats">
          <div class="report-stat focused">
            <span class="stat-value">${reportData.focused_minutes}</span>
            <span class="stat-label">分钟专注</span>
          </div>
          <div class="report-stat distracted">
            <span class="stat-value">${reportData.distracted_minutes}</span>
            <span class="stat-label">分钟走神</span>
          </div>
          <div class="report-stat away">
            <span class="stat-value">${reportData.away_minutes}</span>
            <span class="stat-label">分钟离开</span>
          </div>
        </div>

        <div class="report-section">
          <div class="report-section-title">📋 时间线</div>
          <div class="report-timeline">${timelineHTML}</div>
        </div>

        ${reportData.completion_assessment ? `
        <div class="report-section">
          <div class="report-section-title">📝 任务评估</div>
          <div class="report-text">${this._escapeHtml(reportData.completion_assessment)}</div>
        </div>` : ''}

        ${reportData.summary ? `
        <div class="report-section">
          <div class="report-section-title">🤖 AI 总结</div>
          <div class="report-text">${this._escapeHtml(reportData.summary)}</div>
        </div>` : ''}

        <div class="report-section">
          <div class="report-section-title">💡 小建议</div>
          <ul class="report-suggestions">${suggestionsHTML}</ul>
        </div>
      </div>
    `;

    this.chatPanelEl.appendChild(msgDiv);
    this.chatPanelEl.scrollTop = this.chatPanelEl.scrollHeight;
  },

  _escapeHtml(text) {
    if (!text) return '';
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  },

  /**
   * 更新输入源状态
   */
  updateInputSources(sources) {
    this.inputSources = sources;
  },

  /**
   * 清除会话
   */
  async clearSession() {
    try {
      await apiClient.clearSession(this.sessionId);
    } catch (e) {
      console.warn('清除会话失败:', e);
    }

    this.sessionId = Format.uuid();
    this.messages = [];
    this.chatPanelEl.innerHTML = '';
    this._renderWelcome();
  },

  // ── 内部方法 ──

  _renderWelcome() {
    this.chatPanelEl.innerHTML = `
      <div class="welcome-screen">
        <div class="welcome-icon">🖥️</div>
        <h2>欢迎使用桌面伴侣</h2>
        <p>你的网页端 AI 多模态伴随助手</p>
        <div class="welcome-tips">
          <div class="tip-item">
            <span class="tip-icon">📺</span>
            <span>先开启</span><strong>屏幕共享</strong><span>，让 AI 看到你的屏幕内容</span>
          </div>
          <div class="tip-item">
            <span class="tip-icon">🎤</span>
            <span>开启</span><strong>麦克风</strong><span>，用语音自然提问</span>
          </div>
          <div class="tip-item">
            <span class="tip-icon">📷</span>
            <span>可选开启</span><strong>摄像头</strong><span>，AI 同时理解你的现实环境</span>
          </div>
        </div>
        <div class="welcome-examples">
          <p>试试问我：</p>
          <button class="example-btn" onclick="document.getElementById('chatInput').value='你看一下我屏幕，这个是什么意思？'; document.getElementById('sendBtn').click();">
            "你看一下我屏幕，这个是什么意思？"
          </button>
          <button class="example-btn" onclick="document.getElementById('chatInput').value='帮我总结一下当前屏幕的内容'; document.getElementById('sendBtn').click();">
            "帮我总结一下当前屏幕的内容"
          </button>
          <button class="example-btn" onclick="document.getElementById('chatInput').value='这个报错是什么意思？'; document.getElementById('sendBtn').click();">
            "这个报错是什么意思？"
          </button>
        </div>
      </div>
    `;
  },

  _addMessageToUI(role, text, images = [], sources = [], uncertainty = null) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message message-${role}`;

    const avatar = role === 'user' ? '👤' : '🤖';
    const time = Format.time();

    let html = `
      <div class="message-avatar">${avatar}</div>
      <div class="message-content">
        <div class="message-header">
          <span class="message-role">${role === 'user' ? '你' : '桌面伴侣'}</span>
          <span class="message-time">${time}</span>
    `;

    // 输入源标签
    if (role === 'assistant' && sources.length > 0) {
      const sourceLabels = sources.map(s => {
        const icons = { screen: '📺', camera: '📷', voice: '🎤' };
        const labels = { screen: '屏幕截图', camera: '摄像头画面', voice: '语音问题' };
        return `${icons[s] || ''} ${labels[s] || s}`;
      });
      html += `<span class="message-sources" title="本次回答基于">基于: ${sourceLabels.join(', ')}</span>`;
    }

    html += `</div>`;

    // 图片预览 (用户消息)
    if (images.length > 0) {
      html += '<div class="message-images">';
      for (const img of images) {
        html += `<img src="data:image/jpeg;base64,${img.data}" class="message-img-preview" alt="截图预览">`;
      }
      html += '</div>';
    }

    html += `<div class="message-text">${Format.markdown(text)}</div>`;

    // 不确定性提示
    if (uncertainty) {
      html += `<div class="uncertainty-note">⚠️ ${uncertainty}</div>`;
    }

    html += '</div></div>';

    msgDiv.innerHTML = html;

    // 移除欢迎页
    const welcome = this.chatPanelEl.querySelector('.welcome-screen');
    if (welcome) welcome.remove();

    this.chatPanelEl.appendChild(msgDiv);
    this.chatPanelEl.scrollTop = this.chatPanelEl.scrollHeight;

    this.messages.push({ role, text, images, sources });
    return msgDiv;
  },

  _updateLastUserMessage(text) {
    const userMessages = this.chatPanelEl.querySelectorAll('.message-user');
    const lastMsg = userMessages[userMessages.length - 1];
    if (lastMsg) {
      const textEl = lastMsg.querySelector('.message-text');
      if (textEl) {
        textEl.innerHTML = Format.markdown(text);
      }
    }
  },

  _addLoadingMessage() {
    const div = document.createElement('div');
    div.className = 'message message-assistant message-loading';
    div.innerHTML = `
      <div class="message-avatar">🤖</div>
      <div class="message-content">
        <div class="typing-indicator">
          <span></span><span></span><span></span>
        </div>
      </div>
    `;
    this.chatPanelEl.appendChild(div);
    this.chatPanelEl.scrollTop = this.chatPanelEl.scrollHeight;
    return div;
  },

  _removeLoadingMessage(el) {
    if (el && el.parentNode) {
      el.remove();
    }
  },

  _updateSourceIndicators(sources) {
    // 更新顶部状态栏
    const sourceEl = document.getElementById('lastUsedSources');
    if (sourceEl) {
      const labels = sources.map(s => {
        const map = { screen: '屏幕', camera: '摄像头', voice: '语音' };
        return map[s] || s;
      });
      sourceEl.textContent = labels.length > 0 ? `最近回答基于: ${labels.join(' + ')}` : '';
    }
  },
};
