# GameChat 部署指南

## 目录结构

```
chat_game/
├── game_chat/                        ← 项目主目录（所有开发内容在此）
│   ├── backend/                      ← FastAPI 后端
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   ├── services/
│   │   └── data/                     ← SQLite 数据库（自动创建）
│   ├── miniprogram/                  ← 微信小程序（当前版本）
│   │   ├── app.json / app.js / app.wxss
│   │   ├── pages/
│   │   └── utils/
│   │       └── config.js             ← ★ 修改 BASE_URL 的地方
│   ├── web_demo/                     ← 网页演示界面
│   ├── deploy/                       ← 部署相关文件
│   │   ├── start_tunnel.ps1          ← 本地测试一键启动脚本
│   │   ├── Dockerfile                ← Docker 镜像构建
│   │   ├── docker-compose.yml        ← 容器编排
│   │   └── nginx.conf                ← 生产服务器 Nginx 配置模板
│   ├── .env.example                  ← 环境变量示例（复制为 .env 填入真实 key）
│   ├── game_master.md
│   └── miniprogram_dev_guide.md
└── miniprogram/                      ← 旧版小程序（已废弃，可忽略）
```

---

## 阶段一：本地开发 + 手机远程测试（当前阶段）

### 前置条件
- Python 3.11（`d:\code\conda\python.exe`）
- 微信开发者工具已安装并登录
- `D:\code\tools\cloudflared.exe`（已下载）

### 一键启动

```powershell
# 在 PowerShell 中执行（项目根目录或任意位置）
D:\code\WJY_workspace\chat_game\game_chat\deploy\start_tunnel.ps1
```

脚本会自动：
1. 启动 FastAPI 后端（端口 8000）
2. 启动 Cloudflare 公网穿透，获取 `https://xxxx.trycloudflare.com` 地址
3. 自动将新地址写入 `miniprogram/utils/config.js`
4. 打印公网地址

### 手动启动（分步）

**步骤 1 — 启动后端**
```powershell
d:\code\conda\python.exe -m uvicorn main:app --port 8000 `
  --app-dir "D:\code\WJY_workspace\chat_game\game_chat\backend" --reload
```

**步骤 2 — 启动公网穿透**（新开一个 PowerShell 窗口）
```powershell
D:\code\tools\cloudflared.exe tunnel --url http://localhost:8000
```
等待输出 `https://xxxx.trycloudflare.com`，复制该地址。

**步骤 3 — 更新 config.js**

打开 `game_chat/miniprogram/utils/config.js`，将 `BASE_URL` 改为上一步的 HTTPS 地址：
```js
const BASE_URL = 'https://xxxx.trycloudflare.com';
```

**步骤 4 — 微信开发者工具重新编译**
- 工具顶部点击「编译」（或 `Ctrl+B`）
- 点击「预览」，手机扫码即可（4G / WiFi 均可）
- **不需要勾选"不校验合法域名"**（HTTPS 已合法）

> ⚠️ Quick Tunnel 地址每次重启后会变化，重新运行 `start_tunnel.ps1` 即可自动更新。

---

## 关闭与重启

### 如何关闭

**方法A — 用脚本启动时（推荐）**

在运行 `start_tunnel.ps1` 的 PowerShell 窗口按 `Ctrl+C`，脚本会自动关闭后端和穿透进程。

**方法B — 手动分步关闭**

分别找到启动后端和 cloudflared 的两个 PowerShell 窗口，各按一次 `Ctrl+C` 即可。

**方法C — 强制关闭所有相关进程**（适用于找不到窗口的情况）

打开一个新 PowerShell 窗口执行：
```powershell
# 关闭穿透（cloudflared）
Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force

# 关闭后端（uvicorn / python）
# 注意：如果有其他 Python 程序在运行，下面命令会一并关闭，请谨慎
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
```

---

### 如何重新启动

> 每次重启后 Cloudflare 会生成**新地址**，脚本会自动更新 config.js，之后需要在微信开发者工具重新编译。

**一键重启（推荐）**

```powershell
D:\code\WJY_workspace\chat_game\game_chat\deploy\start_tunnel.ps1
```

等待脚本打印 `=== 全部就绪！===` 及公网地址后：
1. 打开微信开发者工具
2. 点击顶部「编译」（或 `Ctrl+B`）
3. 点击「预览」，手机扫码即可

**手动重启（分步）**

先开一个 PowerShell 窗口启动后端：
```powershell
d:\code\conda\python.exe -m uvicorn main:app --port 8000 `
  --app-dir "D:\code\WJY_workspace\chat_game\game_chat\backend" --reload
```

再开另一个 PowerShell 窗口启动穿透：
```powershell
D:\code\tools\cloudflared.exe tunnel --url http://localhost:8000
```

等输出 `https://xxxx.trycloudflare.com` 后，将该地址填入 `game_chat/miniprogram/utils/config.js`：
```js
const BASE_URL = 'https://xxxx.trycloudflare.com';  // 替换为实际地址
```

然后微信开发者工具点「编译」。

---

### 常见问题

| 现象 | 原因 | 解决 |
|------|------|------|
| 脚本报"端口被占用" | 上次后端没有正确关闭 | 执行方法C强制关闭，再重启 |
| 手机提示"网络错误" | config.js 地址是旧的穿透地址 | 重新运行脚本，等待自动更新后再编译 |
| 脚本启动后立即退出 | cloudflared 获取地址失败 | 检查网络，稍等片刻再重试 |

---

## 阶段1.5：远端用户 Beta 测试（让朋友试用反馈）

目前只有你自己的手机能用，是因为：
- 微信开发者工具生成的"预览二维码"有时效限制（约 25 分钟），且每次重启都会失效
- 你的手机被加入了开发者权限，其他人的手机没有
- Cloudflare Quick Tunnel 的 URL 每次重启都会变

有两种方案，按人数和便利度选择：

---

### 方案 A：预览码直发（最快，适合 1-5 人临时测试）

**优点**：5 分钟内搞定，无需部署任何东西  
**缺点**：每次你重启电脑/脚本，都需要重新发给测试者新的二维码

**步骤：**

1. 运行一键启动脚本（保持后台运行）：
   ```powershell
   D:\code\WJY_workspace\chat_game\game_chat\deploy\start_tunnel.ps1
   ```

2. 打开微信开发者工具 → 顶部点击「**预览**」→ 出现二维码

3. 把二维码**截图发给测试者**（微信/邮件均可）

4. 测试者用微信扫码即可，**不需要任何额外权限**

> ⚠️ 你的电脑必须保持开机且脚本在运行，测试者才能正常使用  
> ⚠️ 每次脚本重启后，config.js 会自动更新，但微信开发者工具需要重新「编译」才能生成新的预览码

---

### 方案 B：体验版 + 免费云后端（推荐，支持多人持续测试）

**优点**：后端部署到云端，你的电脑关机后测试者仍可使用；最多支持 2000 名体验者  
**缺点**：需要约 30 分钟完成一次性部署配置

#### B1 — 部署后端到 Render.com（永久免费）

Render 提供免费 Python 托管，无需信用卡，有稳定 HTTPS 域名。

1. **注册 Render 账号**：[https://render.com](https://render.com)（可用 GitHub 登录）

2. **将代码推送到 GitHub**（如果还没有）：
   ```powershell
   cd D:\code\WJY_workspace\chat_game
   git init
   git add game_chat/
   git commit -m "init"
   # 在 GitHub 创建仓库后:
   git remote add origin https://github.com/你的用户名/game-chat.git
   git push -u origin main
   ```

3. **在 Render 创建 Web Service**：
   - 点击 `New +` → `Web Service`
   - 连接你的 GitHub 仓库
   - 填写以下配置：

   | 字段 | 填写内容 |
   |------|---------|
   | Name | `game-chat-backend` |
   | Root Directory | `game_chat/backend` |
   | Runtime | `Python 3` |
   | Build Command | `pip install -r requirements.txt` |
   | Start Command | `python -m uvicorn main:app --host 0.0.0.0 --port $PORT` |

   - 在 **Environment Variables** 中添加：
     ```
     DEEPSEEK_API_KEY = sk-你的真实key
     ```
   - 点击 `Create Web Service`，等待部署完成（约 3-5 分钟）

4. **获取稳定 URL**：部署完成后，Render 会给一个类似 `https://game-chat-backend-xxxx.onrender.com` 的地址

> ⚠️ Render 免费版在 15 分钟无请求后会**休眠**，第一次请求需要约 30 秒冷启动。可以接受这个延迟，正式上线再升级。

#### B2 — 更新小程序 config.js（用稳定地址）

打开 `game_chat/miniprogram/utils/config.js`，将 BASE_URL 改为 Render 地址：
```js
const BASE_URL = 'https://game-chat-backend-xxxx.onrender.com';
```

之后**不再需要**每次运行 start_tunnel.ps1（只是本地测试时才需要）。

#### B3 — 添加域名白名单

登录 [https://mp.weixin.qq.com](https://mp.weixin.qq.com) → 「开发」→「开发管理」→「服务器域名」

在 **request 合法域名** 中添加：
```
https://game-chat-backend-xxxx.onrender.com
```

保存后等待约 1 分钟生效。

#### B4 — 上传体验版并添加测试者

1. 微信开发者工具顶部点击「**上传**」，填写版本号（如 `0.1.0-beta`）

2. 登录 [https://mp.weixin.qq.com](https://mp.weixin.qq.com) → 「版本管理」→「开发版本」，可以看到刚上传的版本，点击「**设为体验版**」

3. 在「成员管理」→「体验成员」中，通过微信号添加测试者（最多 2000 人）

4. 被添加的测试者：微信扫描体验版二维码（二维码可以发给他们），即可安装并使用

> 体验版不需要审核，测试者可以即时收到更新（每次你上传新版本并设为体验版后）

---

### 方案对比

| | 方案A（预览码直发）| 方案B（体验版+Render）|
|--|--|--|
| 配置时间 | 5 分钟 | ~30 分钟（一次性）|
| 后端需要开机 | ✅ 是 | ❌ 不需要 |
| 测试者数量 | 无限制（只要发码）| 最多 2000 人 |
| 测试者使用稳定性 | 每次重启失效 | 长期稳定 |
| 费用 | 免费 | 免费 |
| 推荐场景 | 1-2 人快速验证 | 多人持续反馈 |

---

## 阶段二：长期上线，其他用户可搜索使用

要让其他用户能搜到并使用小程序，需要完成以下 6 步。

### 第 1 步：注册微信小程序正式账号

1. 打开 [https://mp.weixin.qq.com](https://mp.weixin.qq.com)
2. 点击「立即注册」→ 选「小程序」
3. 填写邮箱 → 激活 → 填写主体信息（个人开发者选「个人」）
4. 进入「开发」→「开发管理」→「开发设置」，获取 **AppID**（形如 `wx1234abcd5678efgh`）

### 第 2 步：购买云服务器

推荐：腾讯云轻量应用服务器
- 规格：2核 2GB 内存，40GB SSD（够用）
- 系统：Ubuntu 22.04 LTS
- 费用：~99 元/年（新用户优惠）
- 购买地址：[https://cloud.tencent.com/product/lighthouse](https://cloud.tencent.com/product/lighthouse)

购买后记录服务器**公网 IP**（如 `1.2.3.4`）。

### 第 3 步：申请域名 + HTTPS 证书

1. **域名**：在腾讯云「域名注册」购买一个域名（如 `gamechat.yourdomain.com`），约 50-100 元/年
2. **DNS 解析**：在域名控制台添加 A 记录，指向服务器 IP
3. **HTTPS 证书**：腾讯云免费 SSL 证书（1年），申请后下载 Nginx 版本

> 或使用 Let's Encrypt 免费证书（见第 5 步 certbot 命令）。

### 第 4 步：部署后端到服务器

SSH 连接服务器后，依次执行：

```bash
# 安装基础环境
sudo apt update && sudo apt install -y python3.11 python3-pip python3.11-venv git nginx

# 上传项目（在本机执行，将 backend 目录传到服务器）
# 方法A: scp
scp -r D:\code\WJY_workspace\chat_game\game_chat root@1.2.3.4:/opt/game-chat

# 方法B: 直接在服务器 git clone（如果代码在 GitHub）
# git clone https://github.com/你/仓库 /opt/game-chat

# 进入目录，创建虚拟环境
cd /opt/game-chat
python3.11 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt

# 创建环境变量文件
cp .env.example .env
nano .env                # 填入真实的 DEEPSEEK_API_KEY

# 测试启动
DEEPSEEK_API_KEY=$(grep DEEPSEEK_API_KEY .env | cut -d= -f2) \
  python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --app-dir backend
# 看到 "Application startup complete." 说明成功，Ctrl+C 退出
```

**配置 systemd 服务（后台自动运行）**

```bash
sudo nano /etc/systemd/system/game-chat.service
```

填入：
```ini
[Unit]
Description=GameChat FastAPI Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/game-chat/backend
EnvironmentFile=/opt/game-chat/.env
ExecStart=/opt/game-chat/venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable game-chat
sudo systemctl start game-chat
sudo systemctl status game-chat   # 应显示 active (running)
```

### 第 5 步：配置 Nginx + HTTPS

```bash
# 复制 nginx 配置（将 YOUR_DOMAIN 替换为真实域名）
sudo cp /opt/game-chat/deploy/nginx.conf /etc/nginx/sites-available/game-chat
sudo nano /etc/nginx/sites-available/game-chat
# 把所有 YOUR_DOMAIN 替换成你的域名，如 gamechat.example.com

sudo ln -s /etc/nginx/sites-available/game-chat /etc/nginx/sites-enabled/
sudo nginx -t         # 检查配置无误
sudo systemctl reload nginx

# 申请 Let's Encrypt 免费 HTTPS 证书（如不用腾讯云证书）
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d gamechat.example.com
# 按提示输入邮箱，选 agree，certbot 会自动修改 nginx 配置
sudo systemctl reload nginx
```

验证：
```bash
curl https://gamechat.example.com/api/conversations
# 应返回 {"conversations": [...]}
```

### 第 6 步：更新小程序配置并发布

**6.1 更新 config.js**

打开 `game_chat/miniprogram/utils/config.js`，改为正式域名：
```js
const BASE_URL = 'https://gamechat.example.com';
```

**6.2 更新微信开发者工具项目 AppID**

打开 `game_chat/miniprogram/project.config.json`，将 `appid` 改为第 1 步获取的真实 AppID。

**6.3 添加服务器域名白名单**

登录 [https://mp.weixin.qq.com](https://mp.weixin.qq.com) →「开发」→「开发管理」→「服务器域名」，在 **request 合法域名** 添加：
```
https://gamechat.example.com
```

**6.4 上传代码并提交审核**

1. 微信开发者工具顶部点击「上传」
2. 填写版本号（如 `1.0.0`）和备注
3. 进入 [https://mp.weixin.qq.com](https://mp.weixin.qq.com) →「版本管理」→「开发版本」，点击「提交审核」
4. 审核通过后（通常 1-3 天），点击「发布」
5. 发布后用户可在微信内搜索小程序名称找到并使用

---

## 快速参考

### 常用命令

| 操作 | 命令 |
|------|------|
| 本地一键启动 | `.\game_chat\deploy\start_tunnel.ps1` |
| 仅启动后端 | `d:\code\conda\python.exe -m uvicorn main:app --port 8000 --app-dir game_chat\backend` |
| 仅启动穿透 | `D:\code\tools\cloudflared.exe tunnel --url http://localhost:8000` |
| 查看服务器后端状态 | `sudo systemctl status game-chat` |
| 查看后端日志 | `sudo journalctl -u game-chat -f` |
| 重启后端服务 | `sudo systemctl restart game-chat` |

### 费用估算（长期上线）

| 项目 | 费用 |
|------|------|
| 腾讯云轻量服务器（2核2G）| ~99 元/年 |
| 域名（.com 或 .cn） | ~50-100 元/年 |
| HTTPS 证书（Let's Encrypt） | 免费 |
| 微信小程序账号（个人）| 免费 |
| DeepSeek API 费用 | 按调用量计费，约 1元/万tokens |

**合计约 150-200 元/年** 即可实现稳定运营。

### 数据备份

SQLite 数据库文件位于服务器 `/opt/game-chat/backend/data/conversations.db`，定期备份：
```bash
# 在服务器上设置每天自动备份
crontab -e
# 添加：
0 3 * * * cp /opt/game-chat/backend/data/conversations.db /opt/game-chat/backup/conversations_$(date +\%Y\%m\%d).db
```
