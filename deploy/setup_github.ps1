# ============================================================
# setup_github.ps1
# 一键创建 GitHub 仓库 + 推送代码
# 使用前：在 GitHub 创建 Personal Access Token（classic），勾选 repo 权限
#   https://github.com/settings/tokens/new
# ============================================================

param(
    [string]$Token = "",
    [string]$RepoName = "game-chat"
)

Set-Location "D:\code\WJY_workspace\chat_game\game_chat"

if (-not $Token) {
    Write-Host ""
    Write-Host "=== GitHub 推送设置 ===" -ForegroundColor Cyan
    Write-Host "需要 GitHub Personal Access Token（classic）" -ForegroundColor Yellow
    Write-Host "创建地址：https://github.com/settings/tokens/new" -ForegroundColor Yellow
    Write-Host "  勾选权限：repo（全部）" -ForegroundColor Yellow
    Write-Host ""
    $Token = Read-Host "请粘贴你的 GitHub Token"
}

if (-not $Token) {
    Write-Host "Token 为空，退出" -ForegroundColor Red
    exit 1
}

$headers = @{
    Authorization = "token $Token"
    Accept        = "application/vnd.github.v3+json"
}

# 获取用户名
try {
    $user = Invoke-RestMethod -Uri "https://api.github.com/user" -Headers $headers
    $Username = $user.login
    Write-Host "已认证为 GitHub 用户：$Username" -ForegroundColor Green
} catch {
    Write-Host "Token 无效或网络异常：$_" -ForegroundColor Red
    exit 1
}

# 创建仓库
Write-Host "[1/3] 创建 GitHub 仓库 $RepoName ..."
$body = @{
    name        = $RepoName
    description = "GameChat - AI 聊天回复顾问（WeChat Miniprogram + FastAPI）"
    private     = $false
} | ConvertTo-Json -Compress

try {
    $repo = Invoke-RestMethod -Uri "https://api.github.com/user/repos" `
        -Method Post -Headers $headers -Body $body -ContentType "application/json"
    $RemoteUrl = $repo.clone_url
    Write-Host "    仓库已创建：$RemoteUrl" -ForegroundColor Green
} catch {
    # 可能仓库已存在
    $RemoteUrl = "https://github.com/$Username/$RepoName.git"
    Write-Host "    仓库可能已存在，使用：$RemoteUrl" -ForegroundColor Yellow
}

# 设置 remote（使用 token 内嵌认证）
Write-Host "[2/3] 设置 git remote ..."
$AuthUrl = $RemoteUrl -replace "https://", "https://$($Token)@"
git remote remove origin 2>$null
git remote add origin $AuthUrl
Write-Host "    remote 已设置" -ForegroundColor Green

# 推送
Write-Host "[3/3] 推送代码到 GitHub ..."
git branch -M main
git push -u origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "=== 推送成功！===" -ForegroundColor Green
    Write-Host "  仓库地址 : https://github.com/$Username/$RepoName" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "=== 下一步：在 Render 部署后端 ===" -ForegroundColor Yellow
    Write-Host "  1. 打开 https://render.com → New + → Web Service"
    Write-Host "  2. 连接 GitHub 仓库：$Username/$RepoName"
    Write-Host "  3. 配置（render.yaml 会自动检测，或手动填写）："
    Write-Host "       Root Directory : backend"
    Write-Host "       Build Command  : pip install -r requirements.txt"
    Write-Host "       Start Command  : uvicorn main:app --host 0.0.0.0 --port `$PORT"
    Write-Host "  4. Environment Variables 中添加："
    Write-Host "       DEEPSEEK_API_KEY = sk-你的真实key"
    Write-Host "  5. 点击 Create Web Service，等待部署完成（约 3-5 分钟）"
    Write-Host "  6. 部署成功后，复制 https://game-chat-backend-xxxx.onrender.com 地址"
    Write-Host "  7. 运行：.\deploy\set_render_url.ps1 https://game-chat-backend-xxxx.onrender.com"
} else {
    Write-Host "推送失败，请检查 Token 权限或网络" -ForegroundColor Red
}
