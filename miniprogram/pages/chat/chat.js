// pages/chat/chat.js — 顾问页（3 标签：回复建议 / 对话记录 / 关系摘要）
const api = require('../../utils/api');

function relTime(iso) {
  if (!iso) return '';
  const d = (Date.now() - new Date(iso)) / 1000;
  if (d < 60) return '刚刚';
  if (d < 3600) return `${Math.floor(d / 60)}分钟前`;
  if (d < 86400) return `${Math.floor(d / 3600)}小时前`;
  return new Date(iso).toLocaleDateString('zh-CN');
}

const STAGES = ['陌生', '初识', '暧昧', '升温', '稳定'];

Page({
  data: {
    convId: '',
    convName: '',
    convInitial: '?',
    activeTab: 'advisor',  // advisor | history | summary

    // advisor
    girlMsgLen: 0,
    analyzing: false,
    result: null,
    feedback: '',
    reging: false,

    // screenshot OCR
    extracting: false,
    ocrMessages: [],      // [{role:'girl'|'me', content:str}]

    // history
    messages: [],

    // summary
    summary: null,
    momentumIcon: '→',
    momentumColor: '#06b6d4',
    progressPct: 0,
  },

  onLoad(options) {
    const name = decodeURIComponent(options.name || '对话');
    this.setData({
      convId: options.id,
      convName: name,
      convInitial: name[0] ? name[0].toUpperCase() : '?',
    });
    wx.setNavigationBarTitle({ title: name });
    this.loadSummary();
  },

  switchTab(e) {
    const tab = e.currentTarget.dataset.tab;
    this.setData({ activeTab: tab });
    if (tab === 'history') this.refreshHistory();
    if (tab === 'summary') this.loadSummary();
  },

  // 输入存实例变量，避免受控输入光标跳动/中文重复 bug
  _girlMsg: '',
  _feedback: '',

  onInput(e) {
    this._girlMsg = e.detail.value;
    this.setData({ girlMsgLen: e.detail.value.length, ocrMessages: [] });
  },
  onFbInput(e) { this._feedback = e.detail.value; },

  // ── 截图 OCR ──
  pickScreenshot() {
    if (this.data.extracting) return;
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      success: (res) => {
        const filePath = res.tempFiles[0].tempFilePath;
        this.setData({ extracting: true, ocrMessages: [] });
        api.uploadScreenshot(this.data.convId, filePath)
          .then((data) => {
            const msgs = data.messages || [];
            if (!msgs.length) {
              wx.showToast({ title: '未识别到内容，请换张清晰截图', icon: 'none' });
              return;
            }
            // 取最后一条女生消息作为分析输入
            const lastGirl = data.last_girl_msg || '';
            this._girlMsg = lastGirl;
            this.setData({
              ocrMessages: msgs,
              girlMsgLen: lastGirl.length,
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

  clearExtract() {
    this._girlMsg = '';
    this.setData({ ocrMessages: [], girlMsgLen: 0 });
  },

  async saveOcrToHistory() {
    const msgs = this.data.ocrMessages;
    if (!msgs.length) return;
    try {
      await api.batchRecord(this.data.convId, msgs);
      wx.showToast({ title: '已存入记录', icon: 'success' });
    } catch (e) {
      wx.showToast({ title: e.message, icon: 'none' });
    }
  },

  async doAnalyze() {
    const msg = (this._girlMsg || '').trim();
    if (!msg || this.data.analyzing) return;
    this.setData({ analyzing: true, result: null });
    try {
      const res = await api.analyzeMessage(msg, this.data.convId);
      this.setData({ result: res });
    } catch (e) {
      wx.showToast({ title: e.message, icon: 'none' });
    } finally {
      this.setData({ analyzing: false });
    }
  },

  async doFeedback() {
    const fb = (this._feedback || '').trim();
    if (!fb || this.data.reging) return;
    this.setData({ reging: true });
    try {
      const res = await api.feedbackRegen(this._girlMsg || '', fb, this.data.convId);
      this.setData({ result: res, feedback: '' });
      this._feedback = '';
    } catch (e) {
      wx.showToast({ title: e.message, icon: 'none' });
    } finally {
      this.setData({ reging: false });
    }
  },

  copyReply(e) {
    wx.setClipboardData({
      data: e.currentTarget.dataset.text,
      success() { wx.showToast({ title: '已复制', icon: 'success' }); },
    });
  },

  async markSent(e) {
    const text = e.currentTarget.dataset.text;
    try {
      await api.recordMessage(this.data.convId, text);
      wx.showToast({ title: '已记录', icon: 'success' });
    } catch (e) {
      wx.showToast({ title: e.message, icon: 'none' });
    }
  },

  async refreshHistory() {
    try {
      const conv = await api.getConversation(this.data.convId);
      const msgs = (conv.messages || []).map(m => ({
        ...m,
        timeStr: relTime(m.timestamp),
      }));
      this.setData({ messages: msgs });
    } catch (e) {
      wx.showToast({ title: e.message, icon: 'none' });
    }
  },

  async doSummarize() {
    wx.showLoading({ title: '生成中...' });
    try {
      await api.summarize(this.data.convId);
      await this.loadSummary();
      wx.showToast({ title: '已更新', icon: 'success' });
    } catch (e) {
      wx.showToast({ title: e.message, icon: 'none' });
    } finally {
      wx.hideLoading();
    }
  },

  async loadSummary() {
    try {
      const data = await api.getAnalysis(this.data.convId);
      const s = data.summary || null;
      if (!s) return;
      const m = s.momentum || 'stable';
      const icon = m === 'rising' ? '↗' : m === 'falling' ? '↘' : '→';
      const color = m === 'rising' ? '#10b981' : m === 'falling' ? '#ef4444' : '#06b6d4';
      const stageIdx = STAGES.indexOf(s.relationship_stage || '');
      const pct = stageIdx < 0 ? 0 : Math.round((stageIdx / (STAGES.length - 1)) * 100);
      this.setData({ summary: s, momentumIcon: icon, momentumColor: color, progressPct: pct });
    } catch (e) {
      // summary may not exist yet — silent fail
    }
  },
});
