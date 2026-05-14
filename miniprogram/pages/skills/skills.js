// pages/skills/skills.js — 技能库页
const api = require('../../utils/api');

Page({
  data: {
    skills: [],
    selectedIds: new Set(),
    sessionId: '',
    loading: true,
    filterCategory: 'all',
    categories: [],
  },

  async onLoad(options) {
    if (options.session_id) {
      this.setData({ sessionId: options.session_id });
      // 加载会话已选技能
      try {
        const session = await api.getSession(options.session_id);
        this.data.selectedIds = new Set(session.skill_ids);
      } catch {}
    }
    await this.loadSkills();
  },

  async loadSkills() {
    this.setData({ loading: true });
    try {
      const res = await api.getSkills();
      const cats = [...new Set(res.skills.map(s => s.category))];
      this.setData({
        skills: res.skills,
        categories: cats,
        loading: false,
      });
    } catch (e) {
      wx.showToast({ title: e.message, icon: 'none' });
      this.setData({ loading: false });
    }
  },

  isSelected(id) {
    return this.data.selectedIds.has(id);
  },

  toggleSkill(e) {
    const { id } = e.currentTarget.dataset;
    const set = this.data.selectedIds;
    if (set.has(id)) { set.delete(id); }
    else { set.add(id); }
    this.data.selectedIds = set;
    this.setData({}); // 触发重渲染
  },

  async applySkills() {
    const { sessionId, selectedIds } = this.data;
    if (!sessionId) {
      wx.showToast({ title: '请先从聊天页进入', icon: 'none' });
      return;
    }
    try {
      await api.updateSessionSkills(sessionId, [...selectedIds]);
      wx.showToast({ title: `✓ 已应用 ${selectedIds.size} 个技能`, icon: 'none' });
      setTimeout(() => wx.navigateBack(), 1000);
    } catch (e) {
      wx.showToast({ title: e.message, icon: 'none' });
    }
  },

  async resetSkills() {
    wx.showModal({
      title: '重置技能',
      content: '确认重置为默认技能库？',
      success: async (res) => {
        if (res.confirm) {
          await api.resetSkills();
          this.loadSkills();
          wx.showToast({ title: '已重置', icon: 'success' });
        }
      },
    });
  },

  setFilter(e) {
    this.setData({ filterCategory: e.currentTarget.dataset.cat });
  },

  get filteredSkills() {
    const { skills, filterCategory } = this.data;
    if (filterCategory === 'all') return skills;
    return skills.filter(s => s.category === filterCategory);
  },
});
