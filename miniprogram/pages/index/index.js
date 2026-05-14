// pages/index/index.js — 会话列表页
const api = require('../../utils/api');

function relTime(iso) {
  if (!iso) return '';
  const d = (Date.now() - new Date(iso)) / 1000;
  if (d < 60) return '刚刚';
  if (d < 3600) return `${Math.floor(d / 60)}分钟前`;
  if (d < 86400) return `${Math.floor(d / 3600)}小时前`;
  return `${Math.floor(d / 86400)}天前`;
}

Page({
  data: {
    convList: [],
    loading: true,
  },

  onShow() {
    this.loadList();
  },

  async loadList() {
    this.setData({ loading: true });
    try {
      const res = await api.listConversations();
      const convs = (res.conversations || []).map(c => {
        let stage = '';
        if (c.context_summary) {
          try { stage = JSON.parse(c.context_summary).relationship_stage || ''; } catch (e) {}
        }
        const goalMap = { '恋爱': 'love', '玩伴': 'friend', '普通朋友': 'normal' };
      return {
          id: c.id,
          name: c.name,
          goal: c.goal,
          goalKey: goalMap[c.goal] || 'normal',
          initial: (c.name || '?')[0].toUpperCase(),
          stage,
          timeStr: relTime(c.last_message_at),
        };
      });
      this.setData({ convList: convs });
    } catch (e) {
      wx.showToast({ title: e.message, icon: 'none' });
    } finally {
      this.setData({ loading: false });
    }
  },

  goCreate() {
    wx.navigateTo({ url: '/pages/create-session/create-session' });
  },

  goAdvisor(e) {
    const { id, name } = e.currentTarget.dataset;
    wx.navigateTo({
      url: `/pages/chat/chat?id=${id}&name=${encodeURIComponent(name)}`,
    });
  },

  deleteConv(e) {
    const { id } = e.currentTarget.dataset;
    wx.showModal({
      title: '确认删除',
      content: '删除后所有记录不可恢复',
      confirmColor: '#ef4444',
      success: async (res) => {
        if (!res.confirm) return;
        try {
          await api.deleteConversation(id);
          wx.showToast({ title: '已删除', icon: 'success' });
          this.loadList();
        } catch (e) {
          wx.showToast({ title: e.message, icon: 'none' });
        }
      },
    });
  },
});
