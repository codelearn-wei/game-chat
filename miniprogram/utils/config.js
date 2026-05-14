// 全局 API 地址配置
// 模式A（本地调试）: 运行 start_tunnel.ps1，脚本自动更新此文件
// 模式B（体验版，当前）: Render 稳定后端，地址不会变，关机后测试者仍可用
// 切换方式: 将 BASE_URL 改为对应地址后，微信开发者工具重新「编译」

const BASE_URL = 'RENDER_URL_PLACEHOLDER';

module.exports = {
  BASE_URL,
};