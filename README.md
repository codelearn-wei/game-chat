# Game Chat — 高价值回复顾问

基于 DeepSeek AI 的聊天回复助手，支持多会话管理、AI 摘要、深度分析与微信小程序使用。

---

## 核心功能

| 功能 | 说明 |
|------|------|
| **多会话管理** | 同时维护多个聊天对象，每个会话独立存储历史记录 |
| **5风格回复建议** | 极简冷感 / 反客为主 / 幽默调侃 / 温柔推进 / 深度连接 |
| **实时反馈重生成** | 对回复不满意时，输入提示词让 AI 重新生成 |
| **AI 关系摘要** | 定期将聊天历史压缩为关键画像，指导后续回复风格 |
| **深度分析** | 基于 game_master.md 框架，给出关系热度评分、行动建议 |
| **Web + 小程序** | 本地 Web 界面 + 微信小程序双端使用 |

---

## 快速启动（本地）

### 1. 启动后端

```bash
d:\code\conda\python.exe -m uvicorn main:app --port 8000 
  --app-dir "D:\code\WJY_workspace\chat_game\game_chat\backend" --reload
```

### 2. 打开 Web 界面

浏览器访问：[http://127.0.0.1:8000/demo](http://127.0.0.1:8000/demo)

### 3. API 文档

[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 微信小程序使用

1. 下载 [微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)
2. 导入项目 → 目录选 `miniprogram/`（本仓库根下的 `../miniprogram/`）
3. **详情 → 本地设置 → 勾选「不校验合法域名」**（本地开发必须）
4. 修改 `miniprogram/app.js` 中的 `apiBase`：
   - 本地测试：`http://192.168.x.x:8000`（手机和电脑同一局域网）
   - 服务器部署后：`https://your-domain.com`
5. 编译运行即可

---

## 项目结构

```
game_chat/
├── game_master.md             ← 核心框架（所有 AI 回复的最高优先级指导）
├── start.bat                  # 一键启动脚本
├── README.md                  # 本文档
├── backend/
│   ├── main.py                # FastAPI 入口
│   ├── requirements.txt       # Python 依赖
│   ├── data/
│   │   └── conversations.db   # SQLite 会话数据库（自动创建）
│   ├── models/
│   │   └── schemas.py         # Pydantic 数据模型
│   ├── services/
│   │   ├── advisor_service.py    # 回复生成核心逻辑
│   │   ├── conversation_service.py # SQLite 会话 CRUD
│   │   ├── summary_service.py    # AI 摘要 + 深度分析
│   │   └── deepseek_client.py    # DeepSeek API 客户端
│   └── routers/
│       ├── advisor.py         # POST /api/advisor/analyze、/feedback
│       └── conversations.py   # CRUD /api/conversations/*
└── web_demo/
    └── index.html             # Web 演示界面（单文件，无需额外部署）
```

---

## API 接口一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/conversations` | 获取所有会话列表 |
| POST | `/api/conversations` | 创建新会话（name, goal, notes）|
| GET | `/api/conversations/{id}` | 获取会话详情 + 消息历史 |
| PATCH | `/api/conversations/{id}` | 更新会话信息 |
| DELETE | `/api/conversations/{id}` | 删除会话及所有历史 |
| POST | `/api/conversations/{id}/record` | 记录已发送的回复到历史 |
| POST | `/api/conversations/{id}/summarize` | 触发 AI 生成关系摘要 |
| GET | `/api/conversations/{id}/analysis` | 获取深度分析报告 |
| POST | `/api/advisor/analyze` | 分析消息，生成5风格回复 |
| POST | `/api/advisor/feedback` | 根据反馈重新生成回复 |

---

## game_master.md 框架说明

文件位置：`game_chat/game_master.md`（**可直接编辑**，后端自动读取最新版本）

框架包含 5 大模块：
1. **核心底层原则**：不暴露需求感 / 情绪稳定 / 强主体性
2. **对话能力**：反差感语言 / 冷读能力 / 奶狗×狼狗双模式
3. **关系推进**：框架突破 / 目标匹配 / 三步节奏（聊你→聊我→聊我们）
4. **价值展现**：自然展示优势 / 高价值信号 / 强应变能力
5. **执行检查**：四问自检 + 禁忌红线

---

## 技术栈

- **后端**：FastAPI + Uvicorn + httpx（`trust_env=False`）
- **AI**：DeepSeek Chat API
- **数据库**：SQLite3（内置，无需额外安装）
- **前端**：原生 HTML/JS（Web）+ 微信小程序（WXML/WXSS/JS）

---

## 服务器部署

详见根目录 [`DEPLOY.md`](../DEPLOY.md)，包含 Docker 部署、Nginx HTTPS 配置和微信小程序域名注册全流程。


## 快速启动

### 1. 启动后端

```bash
# 双击 start.bat，或执行：
d:\code\conda\python.exe -m uvicorn main:app --reload --port 8000 --app-dir backend
```

### 2. 访问 Web 演示界面

打开浏览器访问：http://127.0.0.1:8000/demo

### 3. API 文档

http://127.0.0.1:8000/docs

### 4. 运行测试

```bash
# 服务器启动后执行：
d:\code\conda\python.exe backend/test_api.py
```

## 项目结构

```
game_chat/
├── start.bat                  # 一键启动脚本
├── backend/
│   ├── main.py                # FastAPI 入口
│   ├── requirements.txt       # Python 依赖
│   ├── test_api.py            # 自动化测试
│   ├── models/
│   │   └── schemas.py         # Pydantic 数据模型
│   ├── services/
│   │   ├── chat_service.py    # 核心业务逻辑（Skills/Session/Chat）
│   │   ├── deepseek_client.py # DeepSeek API 客户端
│   │   └── memory_service.py  # 记忆压缩服务
│   ├── routers/
│   │   ├── chat.py            # POST /{session_id}/send
│   │   ├── skills.py          # CRUD /api/skills
│   │   └── sessions.py        # CRUD /api/sessions
│   └── data/
│       ├── default_skills.json # 12 个默认技能
│       ├── skills.json         # 运行时技能（自动生成）
│       └── sessions/           # 会话 JSON 文件（自动生成）
├── web_demo/
│   └── index.html             # Web 演示界面（无需部署）
└── miniprogram/               # 微信小程序
    ├── app.js / app.json / app.wxss
    ├── utils/
    │   ├── api.js             # 封装 wx.request
    │   └── config.js          # API 地址配置
    └── pages/
        ├── index/             # 会话列表
        ├── chat/              # 聊天界面
        ├── skills/            # 技能库
        └── create-session/    # 新建会话
```

## 微信小程序使用说明

1. 打开**微信开发者工具**，导入 `miniprogram/` 目录
2. 修改 `utils/config.js` 中的 `BASE_URL` 为本机局域网 IP（如 `http://192.168.1.100:8000`）
3. 在微信开发者工具中：**详情 → 本地设置 → 勾选「不校验合法域名」**
4. 可用**游客模式 AppID**（`touristappid`）运行

## 技能说明

| 技能 | 分类 | 语调 |
|------|------|------|
| 若即若离 | 情感策略 | 高冷随性 |
| 高价值展示 | 吸引力建设 | 自信从容 |
| 幽默破冰 | 互动技巧 | 轻松幽默 |
| 情感共鸣 | 深度连接 | 温暖理解 |
| 制造好奇 | 吸引力建设 | 神秘有趣 |
| 温柔边界 | 价值维护 | 温柔坚定 |
| 约会推进 | 关系推进 | 随意自然 |
| 话题主导 | 互动技巧 | 主动掌控 |
| 适度撩拨 | 情感策略 | 暧昧轻松 |
| 女生视角 | 认知提升 | 感性理解 |
| 冷淡回暖 | 情感策略 | 淡定自信 |
| 深度共鸣 | 深度连接 | 真诚深沉 |

## 技术栈

- **后端**：FastAPI 0.111 + Uvicorn 0.29 + httpx 0.27
- **AI**：DeepSeek Chat API
- **存储**：JSON 文件（无数据库）
- **前端**：原生 HTML/JS + 微信小程序
