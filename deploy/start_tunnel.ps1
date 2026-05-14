# ============================================================
# start_tunnel.ps1 - 一键启动后端 + Cloudflare 穿透
# 每次运行会生成新的公网地址，并自动更新 config.js
# ============================================================

$BackendPath    = "D:\code\WJY_workspace\chat_game\game_chat\backend"
$ConfigFile     = "D:\code\WJY_workspace\chat_game\game_chat\miniprogram\utils\config.js"
$CloudflaredExe = "D:\code\tools\cloudflared.exe"
$PythonExe      = "d:\code\conda\python.exe"

Write-Host "=== GameChat 启动脚本 ===" -ForegroundColor Cyan

# --- 1. 启动后端 ---
Write-Host ""
Write-Host "[1/3] 启动 FastAPI 后端..." -ForegroundColor Yellow
$backend = Start-Process -FilePath $PythonExe `
    -ArgumentList "-m uvicorn main:app --port 8000 --app-dir `"$BackendPath`"" `
    -PassThru -WindowStyle Minimized
Write-Host "    后端进程 PID: $($backend.Id)" -ForegroundColor Green
Start-Sleep -Seconds 3

$backendOk = $false
try {
    $null = Invoke-RestMethod "http://127.0.0.1:8000/api/conversations" -TimeoutSec 5
    $backendOk = $true
} catch {
    $backendOk = $false
}
if (-not $backendOk) {
    Write-Host "    后端启动失败，请检查 Python 环境" -ForegroundColor Red
    exit 1
}
Write-Host "    后端已就绪 OK" -ForegroundColor Green

# --- 2. 启动 Cloudflare 穿透 ---
Write-Host ""
Write-Host "[2/3] 启动 Cloudflare 公网穿透..." -ForegroundColor Yellow

# 用固定路径避免 %TEMP% 短路径问题，出/错分开两个文件
$tunnelOut = "D:\code\WJY_workspace\chat_game\game_chat\deploy\tunnel_stdout.log"
$tunnelErr = "D:\code\WJY_workspace\chat_game\game_chat\deploy\tunnel_stderr.log"
Remove-Item $tunnelOut, $tunnelErr -ErrorAction SilentlyContinue

$tunnel = Start-Process -FilePath $CloudflaredExe `
    -ArgumentList "tunnel --url http://localhost:8000" `
    -PassThru -WindowStyle Hidden `
    -RedirectStandardOutput $tunnelOut `
    -RedirectStandardError  $tunnelErr

$publicUrl = $null
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 500
    # cloudflared 把 URL 输出到 stderr，用 Select-String 搜索更可靠
    foreach ($f in @($tunnelErr, $tunnelOut)) {
        if (-not (Test-Path $f)) { continue }
        $hit = Select-String -Path $f -Pattern "https://[a-z0-9\-]+\.trycloudflare\.com" -ErrorAction SilentlyContinue
        if ($hit) {
            $publicUrl = $hit.Matches[0].Value
            break
        }
    }
    if ($publicUrl) { break }
}

if (-not $publicUrl) {
    Write-Host "    无法获取公网地址，请手动查看 cloudflared 输出" -ForegroundColor Red
    exit 1
}
Write-Host "    公网地址: $publicUrl OK" -ForegroundColor Green

# --- 3. 更新 config.js ---
Write-Host ""
Write-Host "[3/3] 更新小程序 config.js..." -ForegroundColor Yellow
$config = Get-Content $ConfigFile -Raw
$config = $config -replace "const BASE_URL = 'https?://[^']+';", "const BASE_URL = '$publicUrl';"
Set-Content $ConfigFile $config -Encoding UTF8
Write-Host "    config.js 已更新 OK" -ForegroundColor Green

Write-Host ""
Write-Host "=== 全部就绪 ===" -ForegroundColor Cyan
Write-Host "  公网地址 : $publicUrl" -ForegroundColor White
Write-Host "  下一步   : 微信开发者工具 -> 编译 -> 预览 -> 扫码" -ForegroundColor White
Write-Host ""
Write-Host "关闭方法: 直接关闭本窗口，或按 Ctrl+C" -ForegroundColor DarkGray
Write-Host ""

# 保持脚本运行，每 5 秒检查一次穿透是否还活着
while ($true) {
    Start-Sleep -Seconds 5
    if ($tunnel.HasExited) {
        Write-Host "穿透进程已退出，请重新运行脚本" -ForegroundColor Red
        break
    }
}
