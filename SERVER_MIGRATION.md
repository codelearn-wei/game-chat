# 服务器迁移指南

本项目后端为 FastAPI + Python 3.11，数据库为 SQLite。
更换服务器只需修改 **1 个前端文件** + 在新服务器部署后端即可。

---

## 第一步：修改前端 API 地址

打开 `miniprogram/utils/config.js`，将 `BASE_URL` 改为新服务器地址：

```js
// miniprogram/utils/config.js
const BASE_URL = 'https://你的新服务器地址';   // ← 只改这一行
```

改完后在微信开发者工具重新「编译」，再上传体验版/正式版即可。

---

## 第二步：在新服务器部署后端

### 方式 A — Render（免费，当前方案）
1. 登录 https://render.com → 进入现有 Web Service
2. Settings → 修改 Git 仓库或 Build/Start 命令（一般不需要改）
3. 如需迁移到新账号：New Web Service → Connect GitHub → 选 `codelearn-wei/game-chat`
   - Build Command: `pip install -r backend/requirements.txt`
   - Start Command: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Root Directory: 留空（从仓库根目录开始）

### 方式 B — 阿里云 / 腾讯云 / 华为云 ECS
```bash
# 1. 安装 Python 3.11
sudo apt update && sudo apt install -y python3.11 python3.11-venv

# 2. 克隆代码
git clone https://github.com/codelearn-wei/game-chat.git
cd game-chat/backend

# 3. 安装依赖
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. 启动（生产环境推荐用 systemd 或 supervisor 守护进程）
uvicorn main:app --host 0.0.0.0 --port 8000
```
服务器安全组记得放行 **8000** 端口（或你指定的端口）。

### 方式 C — 宝塔面板（最简单的国内方案）
1. 安装宝塔 → Python 项目管理器 → 新建项目
2. 框架选 `FastAPI`，Python 版本选 `3.11`
3. 项目目录指向 `game-chat/backend`
4. 启动文件 `main.py`，启动命令 `uvicorn main:app --host 0.0.0.0 --port 8000`

---

## 第三步：配置环境变量

| 变量名 | 说明 | 默认值（代码内已写） |
|--------|------|------------------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key | `sk-1e19d9bf59884dae8612fa4a46769b21` |
| `BAIDU_OCR_API_KEY` | 百度 OCR API Key | `V3G6boOFIr1uMhgQY50qeRzu` |
| `BAIDU_OCR_SECRET_KEY` | 百度 OCR Secret Key | `c3ZGfYtbv7J2kBne2to44MJRgq7lxJhn` |

> 生产环境**强烈建议**通过平台的环境变量设置，不要把 Key 写在代码里。

---

## 第四步：微信小程序合法域名更新

在微信公众平台（AppID: `wx33df3c190fa3ba56`）→ 开发 → 开发设置 → **request 合法域名**，
把旧服务器地址换成新地址（必须 HTTPS）。

---

## 迁移检查清单

- [ ] `miniprogram/utils/config.js` 中 `BASE_URL` 已更新
- [ ] 新服务器后端正常启动，访问 `https://新地址/docs` 可见 API 文档
- [ ] 微信公众平台 request 合法域名已更新
- [ ] 微信开发者工具重新编译并上传新体验版
- [ ] 测试截图识别、消息分析功能正常

---

## 数据库迁移（可选）

SQLite 数据库文件位于 `backend/data/conversations.db`。
如需保留历史数据，将此文件复制到新服务器相同路径即可。
