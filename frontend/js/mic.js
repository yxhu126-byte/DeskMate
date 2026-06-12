/**
 * 麦克风管理模块
 * 负责：授权、录音、停止、获取音频 Blob
 */
const MicManager = {
  stream: null,
  mediaRecorder: null,
  audioChunks: [],
  isActive: false,
  isRecording: false,
  audioBlob: null,

  /**
   * 请求麦克风权限并初始化
   */
  async start() {
    if (this.isActive) {
      console.warn('麦克风已在运行中');
      return;
    }

    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      this.isActive = true;
      console.log('✅ 麦克风已授权');
      return true;
    } catch (err) {
      console.error('麦克风授权失败:', err);
      this.isActive = false;

      if (err.name === 'NotAllowedError') {
        throw new Error('麦克风权限被拒绝，请在浏览器设置中允许麦克风访问');
      } else if (err.name === 'NotFoundError') {
        throw new Error('未检测到麦克风设备');
      } else {
        throw new Error(`麦克风启动失败: ${err.message}`);
      }
    }
  },

  /**
   * 开始录音
   */
  startRecording() {
    if (!this.isActive || !this.stream) {
      throw new Error('麦克风未激活，请先开启麦克风');
    }

    this.audioChunks = [];
    this.audioBlob = null;

    // 检查支持的 MIME 类型
    const mimeType = this._getSupportedMimeType();

    try {
      this.mediaRecorder = new MediaRecorder(this.stream, {
        mimeType: mimeType,
      });
    } catch (e) {
      this.mediaRecorder = new MediaRecorder(this.stream);
    }

    this.mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        this.audioChunks.push(event.data);
      }
    };

    this.mediaRecorder.onstop = () => {
      this.audioBlob = new Blob(this.audioChunks, { type: this.mediaRecorder.mimeType });
      console.log(`录音完成: ${Format.bytes(this.audioBlob.size)}`);
    };

    this.mediaRecorder.start();
    this.isRecording = true;
    console.log('🎤 开始录音...');
  },

  /**
   * 停止录音，返回音频 Blob
   */
  stopRecording() {
    return new Promise((resolve, reject) => {
      if (!this.mediaRecorder || this.mediaRecorder.state === 'inactive') {
        reject(new Error('录音未在运行'));
        return;
      }

      this.mediaRecorder.onstop = () => {
        this.audioBlob = new Blob(this.audioChunks, { type: this.mediaRecorder.mimeType });
        this.isRecording = false;
        console.log(`录音完成: ${Format.bytes(this.audioBlob.size)}`);
        resolve(this.audioBlob);
      };

      this.mediaRecorder.stop();
    });
  },

  /**
   * 停止麦克风
   */
  stop() {
    if (this.isRecording) {
      this.mediaRecorder?.stop();
    }
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop());
      this.stream = null;
    }
    this.mediaRecorder = null;
    this.isActive = false;
    this.isRecording = false;
    console.log('🎤 麦克风已关闭');
  },

  /**
   * 检查麦克风是否就绪
   */
  isReady() {
    return this.isActive;
  },

  /**
   * 获取当前录音时长 (秒)
   */
  getRecordingDuration() {
    if (!this.audioChunks.length) return 0;
    return this.audioChunks.reduce((total, chunk) => total + chunk.size, 0) / 16000; // 估算
  },

  /**
   * 获取浏览器支持的录音格式
   */
  _getSupportedMimeType() {
    const types = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/ogg;codecs=opus',
      'audio/mp4',
      'audio/mpeg',
    ];
    for (const type of types) {
      if (MediaRecorder.isTypeSupported(type)) {
        return type;
      }
    }
    return 'audio/webm';
  },
};
