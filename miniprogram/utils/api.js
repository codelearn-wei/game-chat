/**
 * GameChat API — 封装 wx.request 为 Promise
 * 对接后端 FastAPI (conversations + advisor)
 */
const { BASE_URL } = require('./config');

function request(method, path, data) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: BASE_URL + path,
      method: method.toUpperCase(),
      data: data || {},
      header: { 'Content-Type': 'application/json' },
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
        } else {
          const msg = (res.data && res.data.detail) || `请求失败 (${res.statusCode})`;
          reject(new Error(msg));
        }
      },
      fail(err) {
        const errMsg = err.errMsg || '';
        if (errMsg.includes('ERR_CONNECTION_REFUSED') || errMsg.includes('failed')) {
          reject(new Error('无法连接服务器，请确认：\n1. 手机和电脑在同一WiFi\n2. 后端程序正在运行'));
        } else {
          reject(new Error('网络请求失败：' + errMsg));
        }
      },
    });
  });
}

const api = {
  // ── 会话管理 ──
  listConversations: () => request('GET', '/api/conversations'),
  createConversation: (data) => request('POST', '/api/conversations', data),
  getConversation: (id) => request('GET', `/api/conversations/${id}`),
  deleteConversation: (id) => request('DELETE', `/api/conversations/${id}`),
  recordMessage: (id, usedReply) =>
    request('POST', `/api/conversations/${id}/record`, { used_reply: usedReply }),

  // ── 摘要与分析 ──
  summarize: (id) => request('POST', `/api/conversations/${id}/summarize`),
  getAnalysis: (id) => request('GET', `/api/conversations/${id}/analysis`),

  // ── 回复顾问 ──
  analyzeMessage: (girlMessage, conversationId) =>
    request('POST', '/api/advisor/analyze', {
      girl_message: girlMessage,
      conversation_id: conversationId || undefined,
    }),
  feedbackRegen: (girlMessage, feedback, conversationId) =>
    request('POST', '/api/advisor/feedback', {
      girl_message: girlMessage,
      feedback: feedback,
      conversation_id: conversationId || undefined,
    }),
};

module.exports = api;
