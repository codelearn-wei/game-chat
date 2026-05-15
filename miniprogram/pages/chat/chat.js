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
    extractedPreview: '',      // fallback 原始文本
    parsedMessages: [],        // [{ role: 'me'|'girl', content }]
    girlName: '她',
    autoFilledMsg: '',         // OCR 识别出的女生最后一句（可编辑确认）
    formattedContext: '',      // 带角色标注的完整对话（我: / 她:），传给 advisor

    // 模式 & 技能点
    mode: 'deep',          // 'quick' | 'deep'
    skillAnalyzing: false,
    skillResult: null,
    GAME_SKILLS: [
      { name: '冷读', icon: '🔮', desc: '读懂她的潜在需求' },
      { name: '推拉', icon: '⚡', desc: '情绪张力拉锅战' },
      { name: '悬念钉', icon: '🌀', desc: '勾起好奇心追问' },
      { name: '高价値展示', icon: '💎', desc: '植入个人优势' },
      { name: '奶狗模式', icon: '🐶', desc: '温柔给安全感' },
      { name: '框架翻转', icon: '🎯', desc: '从朋友转昵昧框架' },
    ],

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

  // ── 截图 OCR ──
  pickScreenshot() {
    if (this.data.extracting) return;
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      success: (res) => {
        const filePath = res.tempFiles[0].tempFilePath;
        this.setData({ extracting: true, parsedMessages: [], extractedPreview: '', autoFilledMsg: '' });
        api.uploadScreenshot(this.data.convId, filePath)
          .then((data) => {
            const msgs = data.parsed_messages || [];
            const lastGirl = (data.last_girl_message || '').trim();
            const rawText = (data.extracted_text || '').trim();

            if (msgs.length > 0) {
              // 成功解析：展示对话气泡，等待用户在确认框中核实最后一句
              // 注意：不直接设置 this._girlMsg，等用户在可编辑框确认后再设置
              this.setData({
                parsedMessages: msgs,
                girlName: data.girl_name || '她',
                autoFilledMsg: lastGirl,
                formattedContext: data.formatted_context || '',
                girlMsgLen: lastGirl.length,
                extractedPreview: '',
              });
            } else if (rawText && !rawText.startsWith('未识别')) {
              // 降级：展示原始文本
              this._girlMsg = rawText;
              this.setData({ extractedPreview: rawText, girlMsgLen: rawText.length });
            } else {
              wx.showToast({ title: '未识别到文字，请换张清晰截图', icon: 'none' });
            }
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

  // 用户在确认框中编辑了女生最后一句话
  onConfirmEdit(e) {
    const val = e.detail.value;
    this._girlMsg = val;
    this.setData({ autoFilledMsg: val, girlMsgLen: val.length });
  },

  clearExtract() {
    this._girlMsg = '';
    this.setData({
      extractedPreview: '', parsedMessages: [], girlName: '她',
      autoFilledMsg: '', formattedContext: '', girlMsgLen: 0,
    });
  },

  tapMode(e) {
    this.setData({ mode: e.currentTarget.dataset.mode, skillResult: null });
  },

  async tapSkill(e) {
    const skill = e.currentTarget.dataset.skill;
    const msg = (this._girlMsg || '').trim();
    if (!msg) {
      wx.showToast({ title: '请先输入她发的消息', icon: 'none' });
      return;
    }
    if (this.data.skillAnalyzing) return;
    this.setData({ skillAnalyzing: true, skillResult: null });
    try {
      const res = await api.skillTrigger(skill.name, skill.desc, msg, this.data.convId);
      this.setData({ skillResult: res });
    } catch (err) {
      wx.showToast({ title: err.message || '生成失败', icon: 'none' });
    } finally {
      this.setData({ skillAnalyzing: false });
    }
  },

  clearSkillResult() {
    this.setData({ skillResult: null });
  },

  onInput(e) { this._girlMsg = e.detail.value; this.setData({ girlMsgLen: e.detail.value.length }); },
  onFbInput(e) { this._feedback = e.detail.value; },

  async doAnalyze() {
    // OCR 流程：用可编辑确认框的值；手动流程：用 _girlMsg
    const msg = (
      this.data.parsedMessages.length > 0
        ? this.data.autoFilledMsg
        : this._girlMsg
    || '').trim();
    if (!msg || this.data.analyzing) return;
    const context = this.data.formattedContext || '';
    this.setData({ analyzing: true, result: null });
    try {
      const res = await api.analyzeMessage(msg, this.data.convId, context);
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
