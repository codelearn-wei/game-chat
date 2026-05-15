// pages/quick/quick.js — 速回模式（无需建档，截图或输入即得高质量话术）
const api = require('../../utils/api');

Page({
  data: {
    inputMode: 'screenshot',  // 'screenshot' | 'text'

    // 截图模式
    extracting: false,
    parsedMessages: [],       // [{ role: 'me'|'girl', content }]
    girlName: '她',
    girlMsg: '',              // 受控：auto-filled from OCR，可编辑

    // 手动模式
    manualLen: 0,

    // 分析
    analyzing: false,
    result: null,
  },

  _manualMsg: '',  // 非受控：避免中文输入光标抖动

  goBack() {
    wx.navigateBack();
  },

  switchMode(e) {
    const mode = e.currentTarget.dataset.mode;
    if (mode === this.data.inputMode) return;
    this._manualMsg = '';
    this.setData({ inputMode: mode, parsedMessages: [], girlMsg: '', result: null, manualLen: 0 });
  },

  // ── 截图模式 ──
  pickScreenshot() {
    if (this.data.extracting) return;
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      success: (res) => {
        const filePath = res.tempFiles[0].tempFilePath;
        this.setData({ extracting: true, parsedMessages: [], girlMsg: '', result: null });
        api.uploadScreenshot('', filePath)
          .then((data) => {
            const msgs = data.parsed_messages || [];
            const lastGirl = (data.last_girl_message || '').trim();
            if (msgs.length === 0 && !lastGirl) {
              wx.showToast({ title: '未识别到对话，请换张清晰截图', icon: 'none' });
              return;
            }
            this.setData({
              parsedMessages: msgs,
              girlName: data.girl_name || '她',
              girlMsg: lastGirl,
            });
          })
          .catch((err) => {
            wx.showToast({ title: err.message || '识别失败', icon: 'none' });
          })
          .finally(() => {
            this.setData({ extracting: false });
          });
      },
      fail(err) {
        if (err.errMsg && !err.errMsg.includes('cancel')) {
          wx.showToast({ title: '选图失败，请重试', icon: 'none' });
        }
      },
    });
  },

  onGirlMsgInput(e) {
    this.setData({ girlMsg: e.detail.value });
  },

  // ── 手动模式 ──
  onManualInput(e) {
    this._manualMsg = e.detail.value;
    this.setData({ manualLen: e.detail.value.length });
  },

  // ── 分析 ──
  async doAnalyze() {
    if (this.data.analyzing || this.data.extracting) return;

    let msg = '';
    let context = '';

    if (this.data.inputMode === 'screenshot') {
      msg = (this.data.girlMsg || '').trim();
      // 将之前的对话作为上下文
      const msgs = this.data.parsedMessages;
      if (msgs.length > 1) {
        const gName = this.data.girlName;
        context = msgs.slice(0, -1).map(m =>
          m.role === 'me' ? `我: ${m.content}` : `${gName}: ${m.content}`
        ).join('\n');
      }
    } else {
      msg = (this._manualMsg || '').trim();
    }

    if (!msg) {
      wx.showToast({ title: '请输入她发的消息', icon: 'none' });
      return;
    }

    this.setData({ analyzing: true, result: null });
    try {
      const res = await api.analyzeMessage(msg, null, context);
      this.setData({ result: res });
    } catch (e) {
      wx.showToast({ title: e.message || '分析失败', icon: 'none' });
    } finally {
      this.setData({ analyzing: false });
    }
  },

  clearResult() {
    this.setData({ result: null, parsedMessages: [], girlMsg: '' });
    this._manualMsg = '';
    this.setData({ manualLen: 0 });
  },

  copyReply(e) {
    wx.setClipboardData({
      data: e.currentTarget.dataset.text,
      success() { wx.showToast({ title: '已复制', icon: 'success' }); },
    });
  },
});
