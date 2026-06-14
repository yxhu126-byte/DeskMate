/**
 * 屏幕共享管理模块
 * 负责：授权、共享、停止监听、关键帧截取
 */
const ScreenShareManager = {
  stream: null,
  videoEl: null,     // 隐藏的 video 元素用于截图
  isActive: false,
  onStopCallback: null,  // 用户手动停止时的回调

  /**
   * 请求屏幕共享权限
   */
  async start(videoElement, onStopFn) {
    if (this.isActive) {
      console.warn('屏幕共享已在运行中');
      return;
    }

    try {
      this.stream = await navigator.mediaDevices.getDisplayMedia({
        video: {
          width: { ideal: 1920 },
          height: { ideal: 1080 },
          frameRate: { ideal: 5 },
        },
        audio: false,
      });

      this.videoEl = videoElement;
      this.videoEl.srcObject = this.stream;
      this.onStopCallback = onStopFn;
      this.isActive = true;

      // 监听用户通过浏览器 UI 停止共享
      this.stream.getVideoTracks()[0].addEventListener('ended', () => {
        console.log('用户通过浏览器停止了屏幕共享');
        this._handleStop();
      });

      console.log('✅ 屏幕共享已授权并启动');
      return true;
    } catch (err) {
      console.error('屏幕共享授权失败:', err);
      this.isActive = false;

      if (err.name === 'NotAllowedError') {
        throw new Error('屏幕共享权限被拒绝');
      } else if (err.name === 'AbortError') {
        throw new Error('屏幕共享请求已取消');
      } else {
        throw new Error(`屏幕共享启动失败: ${err.message}`);
      }
    }
  },

  /**
   * 手动停止屏幕共享
   */
  stop() {
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop());
      this._cleanup();
      console.log('🖥️ 屏幕共享已停止');
    }
  },

  /**
   * 截取当前屏幕帧
   */
  captureFrame(maxWidth = 1280, maxHeight = 1280, quality = 0.8) {
    if (!this.isActive || !this.videoEl) {
      throw new Error('屏幕共享未激活，请先开启屏幕共享');
    }

    const result = ImageCompressor.captureFrame(this.videoEl, maxWidth, maxHeight, quality);
    return {
      type: 'screen',
      mime_type: 'image/jpeg',
      data: result.data,
      dataUrl: result.dataUrl,
      width: result.width,
      height: result.height,
      sizeBytes: result.sizeBytes,
    };
  },

  /**
   * 检查屏幕共享是否就绪
   */
  isReady() {
    return this.isActive && this.videoEl && this.videoEl.readyState >= 2;
  },

  /**
   * 内部清理
   */
  _cleanup() {
    this.stream = null;
    if (this.videoEl) {
      this.videoEl.srcObject = null;
    }
    this.isActive = false;
  },

  /**
   * 处理停止事件
   */
  _handleStop() {
    this._cleanup();
    if (this.onStopCallback) {
      this.onStopCallback();
    }
  },
};
