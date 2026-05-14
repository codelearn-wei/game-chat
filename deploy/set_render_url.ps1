# ============================================================
# set_render_url.ps1
# 将 Render 后端 URL 写入小程序 config.js 并推送到 GitHub
# 用法: .\deploy\set_render_url.ps1 https://game-chat-xxxx.onrender.com
# ============================================================

param(
    [Parameter(Mandatory=$true)]
    [string]$RenderUrl
)

Set-Location "D:\code\WJY_workspace\chat_game\game_chat"

# 校验 URL 格式
if ($RenderUrl -notmatch "^https://") {
    Write-Host "URL 必须以 https:// 开头" -ForegroundColor Red
    exit 1
}
$RenderUrl = $RenderUrl.TrimEnd("/")

$ConfigFile = "miniprogram\utils\config.js"

Write-Host "[1/3] 更新 config.js → $RenderUrl"
$content = @"
// 全局 API 地址配置
// 模式A（本地调试）: 运行 start_tunnel.ps1，脚本自动更新此文件
// 模式B（体验版，当前）: Render 稳定后端，地址不会变，关机后测试者仍可用
// 切换方式: 将 BASE_URL 改为对应地址后，微信开发者工具重新「编译」

const BASE_URL = '$RenderUrl';

module.exports = {
  BASE_URL,
};
"@
[System.IO.File]::WriteAllText(
    (Resolve-Path $ConfigFile).Path,
    $content,
    [System.Text.Encoding]::UTF8
)
Write-Host "    config.js 已更新" -ForegroundColor Green

Write-Host "[2/3] 提交到 git ..."
git add $ConfigFile
git commit -m "config: 切换后端到 Render ($RenderUrl)"

Write-Host "[3/3] 推送到 GitHub ..."
git push

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "=== 完成！===" -ForegroundColor Green
    Write-Host "  Render 后端 : $RenderUrl" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "=== 下一步：上传小程序体验版 ===" -ForegroundColor Yellow
    Write-Host "  1. 微信开发者工具 → 编译（Ctrl+B）"
    Write-Host "  2. 登录 https://mp.weixin.qq.com → 开发 → 开发管理 → 服务器域名"
    Write-Host "     在「request 合法域名」添加：$RenderUrl"
    Write-Host "  3. 微信开发者工具 → 上传（填写版本号 0.1.0-beta）"
    Write-Host "  4. mp.weixin.qq.com → 版本管理 → 开发版本 → 设为体验版"
    Write-Host "  5. 成员管理 → 体验成员 → 添加测试者微信号"
} else {
    Write-Host "推送失败，请检查 git remote 配置" -ForegroundColor Red
    Write-Host "提示：如果是第一次推送，先运行 .\deploy\setup_github.ps1" -ForegroundColor Yellow
}
