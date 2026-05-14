# GameChat 微信小程序开发指南

> 适用于已完成后端搭建、需要在微信开发者工具中调试小程序的开发者。

---

## 一、前置条件检查

| 项目 | 要求 | 状态 |
|---|---|---|
| 微信开发者工具 | 已安装（Stable 版） | ✅ 已下载 |
| 后端服务 | FastAPI 运行在 8000 端口 | 需确认 |
| 本机 IP | 局域网地址（非 localhost） | `10.116.92.78` |
| 微信账号 | 可扫码登录开发者工具 | 需准备 |

---

## 二、启动后端服务

每次调试小程序前，必须先启动后端。打开 PowerShell：

```powershell
d:\code\conda\python.exe -m uvicorn main:app --port 8000 --app-dir "D:\code\WJY_workspace\chat_game\game_chat\backend" --reload
```

看到如下输出说明启动成功：
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

**保持这个终端窗口开着，不要关闭。**

---

## 三、修改 API 地址（关键步骤）

微信小程序**不能使用 `localhost` 或 `127.0.0.1`**，必须改为本机局域网 IP。

打开文件：
```
D:\code\WJY_workspace\chat_game\game_chat\miniprogram\utils\config.js
```

将第 4 行修改为你的本机 IP：

```javascript
// 修改前（不可用）
const BASE_URL = 'http://127.0.0.1:8000';

// 修改后（可用）
const BASE_URL = 'http://10.116.92.78:8000';
```

> **如何确认你的 IP：** 在 PowerShell 运行 `ipconfig`，找到「IPv4 地址」那行，通常是 `192.168.x.x` 或 `10.x.x.x`。  
> 当前检测到你的 IP 是 `10.116.92.78`。

---

## 四、在微信开发者工具中打开项目

### 4.1 打开项目目录

1. 启动**微信开发者工具**
2. 点击左上角「+」→ **导入项目**
3. 项目目录填写：
   ```
   D:\code\WJY_workspace\chat_game\game_chat\miniprogram
   ```
4. AppID 选择「**测试号**」（无需注册，点击「使用测试号」）
5. 点击「确定」

> ⚠️ 注意：项目目录是 `miniprogram` 子目录，不是 `game_chat` 根目录。

### 4.2 界面说明

工具打开后你会看到：
- **左侧**：模拟器（手机预览）
- **中间**：代码编辑器
- **右侧**：调试面板（Console / Network / Sources）
- **顶部**：编译、预览、上传按钮

---

## 五、关闭域名校验（本地调试必须做）

1. 点击工具右上角「**详情**」
2. 切换到「**本地设置**」标签页
3. 勾选「**不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书**」

![示意：详情 → 本地设置 → 勾选不校验]

> 不做这步，所有网络请求都会报 `request:fail url not in domain list` 错误。

---

## 六、验证页面结构

项目有 3 个页面，`app.json` 已配置：

```json
"pages": [
  "pages/index/index",       ← 启动首页：会话列表
  "pages/chat/chat",         ← 顾问页：回复建议 / 对话记录 / 关系摘要
  "pages/create-session/create-session"  ← 新建会话
]
```

编译后模拟器应显示**会话列表页**（深色背景，顶部 GameChat 标题）。

---

## 七、调试流程（逐页测试）

### 第 1 步：测试首页（会话列表）

1. 工具编译后，模拟器自动显示 `pages/index/index`
2. 正常情况：显示加载动画，然后显示已有会话，或「还没有聊天」空状态
3. 如果看到「网络错误，请检查服务器是否启动」：
   - 确认后端是否运行：浏览器访问 `http://10.116.92.78:8000/api/conversations`，能看到 JSON 说明正常
   - 确认 `config.js` 的 IP 是否正确
4. 点击右下角「**+**」按钮，应跳转到新建会话页

### 第 2 步：测试新建会话页

1. 输入女生名字（例如：小红）
2. 选择目标（恋爱 / 玩伴 / 普通朋友）
3. 可选填写备注
4. 点击「✓ 开始分析」
5. 成功后自动跳转到顾问页

如果创建失败，查看右侧 **Console** 面板的报错信息。

### 第 3 步：测试顾问页（核心功能）

页面有 3 个标签：

**✦ 回复建议标签**
1. 在输入框粘贴女生发来的消息，例如：`你在干嘛呢`
2. 点击「✦ 分析回复」
3. 等待约 5-10 秒（AI 生成中）
4. 应显示：
   - 顶部策略横幅（局势判断 + 下一步方向）
   - 5 张风格卡片（🧊极简冷感、♟️反客为主、😏幽默调侃、🌊温柔推进、🔗深度连接）
   - 每张卡片有 3 条回复 + 🎯技能标签 + GM 原则推理
5. 点击回复旁「复制」直接复制文字
6. 点击「✓ 已发送」将该条记录到对话历史

**💬 对话记录标签**
1. 切换到此标签，查看已记录的对话
2. 点击「↻ 刷新」重新加载
3. 显示气泡式聊天流（她：左侧紫色，我：右侧绿色）

**📊 关系摘要标签**
1. 切换到此标签
2. 点击「更新摘要」（需至少 4 条记录才有效果）
3. 生成后显示：关系阶段、趋势箭头、进度条、她的特点、AI 总结

### 第 4 步：测试反馈重生成

1. 在回复建议页面，看完 5 种风格后觉得不满意
2. 在底部「⚡ 不满意？告诉我哪里不够好」输入框填写反馈
   - 例如：`太直白了，要更冷一点`
   - 例如：`需要更幽默，带点调侃`
3. 点击「重新生成」
4. 5 种风格应根据反馈重新生成

---

## 八、常见问题排查

### 问题 1：`request:fail url not in domain list`
**原因**：没有关闭域名校验  
**解决**：「详情」→「本地设置」→ 勾选「不校验合法域名」

### 问题 2：`网络错误，请检查服务器是否启动`
**原因**：config.js 用了 `127.0.0.1` 或后端没启动  
**解决**：
1. 确认后端 PowerShell 窗口仍在运行
2. 将 `config.js` 的 BASE_URL 改为局域网 IP

### 问题 3：页面白屏，模拟器无内容
**原因**：JS 报错导致页面崩溃  
**解决**：查看右侧 Console 面板，找红色报错，根据行号定位问题

### 问题 4：点击新建会话报 `422 Unprocessable Entity`
**原因**：后端接口参数不匹配  
**解决**：Network 面板查看请求 body，确认包含 `name` 和 `goal` 字段

### 问题 5：分析回复一直转圈不出结果
**原因**：DeepSeek API 超时或 key 失效  
**解决**：
1. 后端终端查看是否有报错
2. 用 web demo 测试同一功能：访问 `D:\code\WJY_workspace\chat_game\game_chat\web_demo\index.html`

### 问题 6：切换标签后内容消失
**原因**：正常行为，切换到「对话记录」时会自动刷新，切换到「关系摘要」时会自动加载已有摘要

---

## 九、在真实手机上预览

开发者工具模拟后想在手机上看效果：

1. 确保手机和电脑**在同一个 WiFi 网络**
2. 点击工具顶部「**预览**」按钮
3. 用微信扫描弹出的二维码
4. 手机上会打开真实小程序预览

> 手机预览时 `config.js` 必须是局域网 IP（`10.116.92.78`），不能是 `127.0.0.1`。

---

## 十、项目文件速查

```
miniprogram/
├── app.json              ← 全局配置（页面路由、导航栏颜色）
├── app.js                ← 全局 App 初始化
├── app.wxss              ← 全局样式（含 .container / .card 等公用类）
├── utils/
│   ├── config.js         ← ⭐ API 地址（开发时修改 BASE_URL）
│   └── api.js            ← 所有后端接口封装（wx.request 的 Promise 版）
└── pages/
    ├── index/            ← 会话列表首页
    │   ├── index.js      ← 逻辑：加载列表、跳转、删除
    │   ├── index.wxml    ← 模板：列表卡片、空状态、FAB 按钮
    │   ├── index.wxss    ← 样式
    │   └── index.json    ← 页面配置（导航栏标题）
    ├── chat/             ← 顾问页（核心页）
    │   ├── chat.js       ← 逻辑：3个标签、分析、反馈、记录、摘要
    │   ├── chat.wxml     ← 模板：Tab 切换、风格卡片、气泡、摘要
    │   ├── chat.wxss     ← 样式
    │   └── chat.json
    └── create-session/   ← 新建会话页
        ├── create-session.js
        ├── create-session.wxml
        ├── create-session.wxss
        └── create-session.json
```

---

## 十一、后端接口速查

开发时遇到接口问题，可直接用浏览器或 Postman 测试：

| 功能 | 方法 | URL |
|---|---|---|
| 获取会话列表 | GET | `http://10.116.92.78:8000/api/conversations` |
| 新建会话 | POST | `http://10.116.92.78:8000/api/conversations` |
| 分析回复 | POST | `http://10.116.92.78:8000/api/advisor/analyze` |
| 反馈重生成 | POST | `http://10.116.92.78:8000/api/advisor/feedback` |
| 记录已发消息 | POST | `http://10.116.92.78:8000/api/conversations/{id}/record` |
| 生成关系摘要 | POST | `http://10.116.92.78:8000/api/conversations/{id}/summarize` |

**测试分析接口示例（PowerShell）：**
```powershell
$body = [System.Text.Encoding]::UTF8.GetBytes('{"girl_message":"你在干嘛呢"}')
Invoke-RestMethod -Uri "http://10.116.92.78:8000/api/advisor/analyze" -Method POST -ContentType "application/json; charset=utf-8" -Body $body
```

**新建会话示例：**
```powershell
$body = [System.Text.Encoding]::UTF8.GetBytes('{"name":"小红","goal":"恋爱"}')
Invoke-RestMethod -Uri "http://10.116.92.78:8000/api/conversations" -Method POST -ContentType "application/json; charset=utf-8" -Body $body
```

也可以直接访问 API 文档：`http://10.116.92.78:8000/docs`

---

## 十二、开发时的修改建议

### 修改样式
每个页面的 `.wxss` 文件控制该页面的外观。颜色变量：
- 背景：`#080810`
- 卡片：`#141428`
- 主色紫：`#7c3aed`
- 青色：`#06b6d4`
- 金色：`#f59e0b`

### 修改页面逻辑
编辑对应 `.js` 文件，修改后工具会自动热重载。

### 修改 AI Prompt
编辑后端文件：
```
D:\code\WJY_workspace\chat_game\game_chat\backend\services\advisor_service.py
```
后端开启了 `--reload`，保存后自动重启，无需手动重启。

### 添加新页面
1. 在 `pages/` 下新建目录，创建同名 `.js/.json/.wxml/.wxss` 4 个文件
2. 在 `app.json` 的 `pages` 数组中添加路径
3. 开发者工具会自动识别
