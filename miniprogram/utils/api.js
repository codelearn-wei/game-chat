/**
 * GameChat API — 封装 wx.request 为 Promise
 * 对接后端 FastAPI (conversations + advisor)
 */
const { BASE_URL } = require('./config');

// 读取图片文件为 base64 并 POST 到 OCR 接口
function _sendBase64(filePath, convId, resolve, reject) {
  wx.getFileSystemManager().readFile({
    filePath: filePath,
    encoding: 'base64',
    success(fileRes) {
      wx.request({
        url: BASE_URL + '/api/ocr/extract',
        method: 'POST',
        header: { 'Content-Type': 'application/json' },
        data: { image_base64: fileRes.data, mime_type: 'image/jpeg', conv_id: convId || '' },
        timeout: 90000,
        success(res) {
          if (res.statusCode >= 200 && res.statusCode < 300) {
            resolve(res.data);
          } else {
            reject(new Error((res.data && res.data.detail) || `识别失败 (${res.statusCode})`));
          }
        },
        fail(err) { reject(new Error('网络请求失败：' + (err.errMsg || ''))); },
      });
    },
    fail(err) { reject(new Error('读取图片失败：' + (err.errMsg || ''))); },
  });
}

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
  // ── 服务器预热（防止 Render 免费版冷启动超时）──
  ping: () => request('GET', '/api/conversations').catch(() => {}),

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

  // ── 截图 OCR（先压缩图片 → 读 base64 → 普通 request，无需 uploadFile 域名）──
  uploadScreenshot(convId, filePath) {
    return new Promise((resolve, reject) => {
      wx.compressImage({
        src: filePath,
        quality: 50,
        success(compRes) {
          _sendBase64(compRes.tempFilePath, convId, resolve, reject);
        },
        fail() {
          // 压缩失败直接用原图
          _sendBase64(filePath, convId, resolve, reject);
        },
      });
    });
  },

  // ── 批量记录截图提取的对话 ──
  batchRecord: (convId, messages) =>
    request('POST', `/api/conversations/${convId}/batch-record`, { messages }),
};

module.exports = api;
