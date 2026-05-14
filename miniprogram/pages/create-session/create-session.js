// pages/create-session/create-session.js
const api = require('../../utils/api');

Page({
  data: {
    goal: '恋爱',
    creating: false,
  },

  // 用实例变量存输入值，避免受控输入导致的光标跳动/中文重复 bug
  _name: '',
  _notes: '',

  onNameInput(e) { this._name = e.detail.value; },
  onNotesInput(e) { this._notes = e.detail.value; },
  selectGoal(e) { this.setData({ goal: e.currentTarget.dataset.goal }); },

  async confirm() {
    const name = this._name;
    const notes = this._notes;
    const { goal } = this.data;
    if (!name.trim()) {
      wx.showToast({ title: '请填写她的名字', icon: 'none' });
      return;
    }
    if (this.data.creating) return;
    this.setData({ creating: true });
    try {
      const conv = await api.createConversation({
        name: name.trim(),
        goal,
        notes: notes.trim() || undefined,
      });
      wx.redirectTo({
        url: `/pages/chat/chat?id=${conv.id}&name=${encodeURIComponent(conv.name)}`,
      });
    } catch (e) {
      wx.showToast({ title: e.message, icon: 'none' });
      this.setData({ creating: false });
    }
  },
});
