/**
 * 摄像头管理模块
 * 负责：授权、开启、预览、关闭、关键帧截取
 */
const CameraManager = {
  stream: null,
  videoEl: null,
  isActive: false,

  /**
   * 请求摄像头权限并开始预览
   */
  async start(videoElement) {
    if (this.isActive) {
      console.warn('摄像头已在运行中');
      return;
    }

    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 },
          facingMode: 'user',
        },
        audio: false,
      });

      this.videoEl = videoElement;
      this.videoEl.srcObject = this.stream;
      this.videoEl.style.transform = 'scaleX(-1)'; // 镜像效果
      this.isActive = true;

      console.log('✅ 摄像头已授权并启动');
      return true;
    } catch (err) {
      console.error('摄像头授权失败:', err);
      this.isActive = false;

      if (err.name === 'NotAllowedError') {
        throw new Error('摄像头权限被拒绝，请在浏览器设置中允许摄像头访问');
      } else if (err.name === 'NotFoundError') {
        throw new Error('未检测到摄像头设备');
      } else {
        throw new Error(`摄像头启动失败: ${err.message}`);
      }
    }
  },

  /**
   * 停止摄像头
   */
  stop() {
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop());
      this.stream = null;
    }
    if (this.videoEl) {
      this.videoEl.srcObject = null;
    }
    this.isActive = false;
    console.log('📷 摄像头已关闭');
  },

  /**
   * 截取当前摄像头帧
   */
  captureFrame(maxWidth = 640, maxHeight = 640, quality = 0.7) {
    if (!this.isActive || !this.videoEl) {
      throw new Error('摄像头未激活，请先开启摄像头');
    }

    const result = ImageCompressor.captureFrame(this.videoEl, maxWidth, maxHeight, quality);
    return {
      type: 'camera',
      mime_type: 'image/jpeg',
      data: result.data,
      width: result.width,
      height: result.height,
      sizeBytes: result.sizeBytes,
    };
  },

  /**
   * 检查摄像头是否就绪
   */
  isReady() {
    return this.isActive && this.videoEl && this.videoEl.readyState >= 2;
  },
};
