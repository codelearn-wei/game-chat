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
        if (errMsg.includes('domain') || errMsg.includes('not in domain list')) {
          reject(new Error('网络配置错误，请联系开发者'));
        } else if (errMsg.includes('ERR_CONNECTION_REFUSED')) {
          reject(new Error('无法连接服务器，请稍后重试'));
        } else {
          reject(new Error('网络请求失败，请检查网络后重试'));
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
  analyzeMessage: (girlMessage, conversationId, context) =>
    request('POST', '/api/advisor/analyze', {
      girl_message: girlMessage,
      conversation_id: conversationId || undefined,
      context: context || '',
    }),
  feedbackRegen: (girlMessage, feedback, conversationId) =>
    request('POST', '/api/advisor/feedback', {
      girl_message: girlMessage,
      feedback: feedback,
      conversation_id: conversationId || undefined,
    }),

  // ── 截图 OCR（读文件转 base64，用普通 request 发送，无需配置 uploadFile 域名）──
  uploadScreenshot(convId, filePath) {
    return new Promise((resolve, reject) => {
      wx.getFileSystemManager().readFile({
        filePath: filePath,
        encoding: 'base64',
        success(fileRes) {
          const lower = filePath.toLowerCase();
          let mimeType = 'image/jpeg';
          if (lower.endsWith('.png')) mimeType = 'image/png';
          else if (lower.endsWith('.webp')) mimeType = 'image/webp';

          wx.request({
            url: BASE_URL + '/api/ocr/extract',
            method: 'POST',
            header: { 'Content-Type': 'application/json' },
            data: {
              image_base64: fileRes.data,
              mime_type: mimeType,
              conv_id: convId || '',
            },
            success(res) {
              if (res.statusCode >= 200 && res.statusCode < 300) {
                resolve(res.data);
              } else {
                const detail = (res.data && res.data.detail) || `识别失败 (${res.statusCode})`;
                reject(new Error(detail));
              }
            },
            fail() {
              reject(new Error('网络请求失败，请检查网络后重试'));
            },
          });
        },
        fail(err) {
          reject(new Error('读取图片失败：' + (err.errMsg || '')));
        },
      });
    });
  },

  skillTrigger: (skillName, skillDesc, girlMessage, conversationId) =>
    request('POST', '/api/advisor/skill-trigger', {
      skill_name: skillName,
      skill_desc: skillDesc || '',
      girl_message: girlMessage,
      conversation_id: conversationId || undefined,
    }),
};

module.exports = api;
