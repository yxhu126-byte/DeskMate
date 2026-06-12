/**
 * 工具模块：图片压缩、API 客户端、通用工具函数
 */

// ── API 客户端 ──
const API_BASE = 'http://localhost:8000';

const apiClient = {
  /**
   * 多模态对话请求
   */
  async multimodalChat({ sessionId, userText, mode, inputSources, images }) {
    const response = await fetch(`${API_BASE}/api/chat/multimodal`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        user_text: userText,
        mode: mode,
        input_sources: inputSources,
        images: images,
      }),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(err.detail || `HTTP ${response.status}`);
    }

    return response.json();
  },

  /**
   * 语音转文字
   */
  async transcribeSpeech(sessionId, audioBlob) {
    const formData = new FormData();
    formData.append('session_id', sessionId);
    formData.append('audio', audioBlob, 'recording.webm');

    const response = await fetch(`${API_BASE}/api/speech/transcribe`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(err.detail || `HTTP ${response.status}`);
    }

    return response.json();
  },

  /**
   * 清除会话
   */
  async clearSession(sessionId) {
    const response = await fetch(`${API_BASE}/api/chat/clear?session_id=${sessionId}`, {
      method: 'POST',
    });
    return response.json();
  },

  /**
   * 健康检查
   */
  async healthCheck() {
    const response = await fetch(`${API_BASE}/api/health`);
    return response.json();
  },
};


// ── 图片压缩 ──
const ImageCompressor = {
  /**
   * 从 video 元素截取当前帧，压缩后返回 base64
   */
  captureFrame(videoEl, maxWidth = 1280, maxHeight = 1280, quality = 0.75) {
    if (!videoEl || videoEl.readyState < 2) {
      throw new Error('视频流未就绪');
    }

    const canvas = document.createElement('canvas');
    let { videoWidth, videoHeight } = videoEl;

    // 计算缩放比例
    let scale = 1;
    if (videoWidth > maxWidth || videoHeight > maxHeight) {
      scale = Math.min(maxWidth / videoWidth, maxHeight / videoHeight);
    }

    canvas.width = Math.round(videoWidth * scale);
    canvas.height = Math.round(videoHeight * scale);

    const ctx = canvas.getContext('2d');
    ctx.drawImage(videoEl, 0, 0, canvas.width, canvas.height);

    // 转为 JPEG base64
    const dataUrl = canvas.toDataURL('image/jpeg', quality);

    // 计算压缩后大小
    const base64 = dataUrl.split(',')[1];
    const sizeBytes = Math.round((base64.length * 3) / 4);

    return {
      data: base64,
      dataUrl: dataUrl,
      width: canvas.width,
      height: canvas.height,
      sizeBytes: sizeBytes,
    };
  },

  /**
   * 压缩已有的 base64 图片
   */
  compressImage(dataUrl, maxWidth = 1280, maxHeight = 1280, quality = 0.75) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        let { width, height } = img;

        let scale = 1;
        if (width > maxWidth || height > maxHeight) {
          scale = Math.min(maxWidth / width, maxHeight / height);
        }

        canvas.width = Math.round(width * scale);
        canvas.height = Math.round(height * scale);

        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

        const compressed = canvas.toDataURL('image/jpeg', quality);
        resolve({
          data: compressed.split(',')[1],
          dataUrl: compressed,
          width: canvas.width,
          height: canvas.height,
          sizeBytes: Math.round((compressed.split(',')[1].length * 3) / 4),
        });
      };
      img.onerror = reject;
      img.src = dataUrl;
    });
  },
};


// ── 格式化工具 ──
const Format = {
  bytes(n) {
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
    return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  },

  time() {
    const now = new Date();
    return now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  },

  markdown(text) {
    // 简单的 markdown 转 HTML (加粗、代码块、列表)
    let html = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/`(.+?)`/g, '<code>$1</code>')
      .replace(/\n\n/g, '</p><p>')
      .replace(/\n/g, '<br>');

    // 简单的列表处理
    html = html.replace(/^(\d+\.\s.*?)(?=<br>|$)/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>)/s, '<ol>$1</ol>');

    return `<p>${html}</p>`;
  },

  uuid() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  },
};
