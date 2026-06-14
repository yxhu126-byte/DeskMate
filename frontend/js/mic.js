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

    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error('当前浏览器不支持麦克风访问，请使用 Chrome、Edge、Firefox 或 Safari 最新版本');
    }

    if (!window.MediaRecorder) {
      throw new Error('当前浏览器不支持录音功能，请使用支持 MediaRecorder 的浏览器');
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
      const options = mimeType ? { mimeType } : undefined;
      this.mediaRecorder = new MediaRecorder(this.stream, options);
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

    this.mediaRecorder.onerror = (event) => {
      const error = event.error || new Error('录音过程中发生未知错误');
      this.isRecording = false;
      console.error('录音失败:', error);
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
    if (!window.MediaRecorder?.isTypeSupported) {
      return '';
    }

    const types = [
      'audio/ogg;codecs=opus',
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/mp4',
      'audio/mpeg',
    ];
    for (const type of types) {
      if (MediaRecorder.isTypeSupported(type)) {
        return type;
      }
    }
    return '';
  },
};

// ══════════════════════════════════════════════════════════
// 浏览器内置语音识别 (Web Speech API)
// Chrome / Edge 原生支持，免费、实时、无需后端
// ══════════════════════════════════════════════════════════
const SpeechRecognizer = {
  recognition: null,
  isSupported: false,
  finalText: '',
  interimText: '',
  _onResult: null,
  _onError: null,
  _onEnd: null,
  _isActive: false,

  /**
   * 初始化（检测浏览器是否支持）
   */
  init() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SR) {
      this.isSupported = true;
      this.recognition = new SR();
      this.recognition.continuous = true;
      this.recognition.interimResults = true;
      this.recognition.lang = 'zh-CN';

      this.recognition.onresult = (event) => {
        let interim = '';
        let final = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            final += transcript;
          } else {
            interim += transcript;
          }
        }
        if (final) this.finalText += final;
        this.interimText = interim;
        if (this._onResult) {
          this._onResult(this.finalText + this.interimText, !!final);
        }
      };

      this.recognition.onerror = (event) => {
        console.error('SpeechRecognition error:', event.error, event.message);
        if (event.error === 'no-speech') {
          // 没检测到语音是正常情况，不算错误
          console.log('SpeechRecognition: 未检测到语音');
          return;
        }
        if (this._onError) this._onError(event.error, event.message);
      };

      this.recognition.onend = () => {
        this._isActive = false;
        console.log('SpeechRecognition ended, finalText:', this.finalText);
        if (this._onEnd) this._onEnd(this.finalText.trim());
      };

      console.log('✅ Web Speech API 可用 (lang: zh-CN)');
    } else {
      console.warn('⚠️ 浏览器不支持 SpeechRecognition，将使用后端 ASR');
    }
  },

  /**
   * 开始语音识别
   * @param {function} onResult - (fullText, isFinal) 回调
   * @param {function} onError  - (error, message) 回调
   */
  start(onResult, onError) {
    if (!this.isSupported || !this.recognition) return false;
    this.finalText = '';
    this.interimText = '';
    this._onResult = onResult || null;
    this._onError = onError || null;
    try {
      this.recognition.start();
      this._isActive = true;
      console.log('🎤 Web Speech 开始聆听...');
      return true;
    } catch (e) {
      // 可能已经在运行中
      console.warn('SpeechRecognition start error:', e);
      return false;
    }
  },

  /**
   * 停止语音识别，返回 Promise<finalText>
   */
  stop() {
    return new Promise((resolve) => {
      if (!this.isSupported || !this.recognition || !this._isActive) {
        resolve(this.finalText.trim());
        return;
      }
      this._onEnd = (finalText) => {
        resolve(finalText);
      };
      try {
        this.recognition.stop();
      } catch (e) {
        resolve(this.finalText.trim());
      }
    });
  },

  /**
   * 立即中止（丢弃结果）
   */
  abort() {
    if (this.recognition) {
      try { this.recognition.abort(); } catch (e) { /* ignore */ }
    }
    this.finalText = '';
    this.interimText = '';
    this._isActive = false;
  },
};
