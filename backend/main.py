"""
AI Chat Framework - FastAPI 主入口
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI 聊天框架",
    description="基于 DeepSeek 的定制化聊天助手，支持 Skills 技能接口和记忆系统",
    version="1.0.0",
)

# 允许所有来源（开发环境；生产环境请限制 origins）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
from routers import chat, skills, sessions, advisor, conversations  # noqa: E402

app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(skills.router, prefix="/api/skills", tags=["Skills"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["Sessions"])
app.include_router(advisor.router, prefix="/api/advisor", tags=["Advisor"])
app.include_router(conversations.router, prefix="/api/conversations", tags=["Conversations"])

# 挂载 web_demo 静态文件（如果存在）
WEB_DEMO_DIR = Path(__file__).parent.parent / "web_demo"
if WEB_DEMO_DIR.exists():
    app.mount("/demo", StaticFiles(directory=str(WEB_DEMO_DIR), html=True), name="demo")


@app.on_event("startup")
async def startup():
    """启动时初始化数据目录、默认技能、SQLite 数据库"""
    from services.chat_service import _ensure_dirs, _load_skills
    from services.conversation_service import init_db
    _ensure_dirs()
    init_db()
    skills_list = _load_skills()
    logger.info(f"[Startup] 已加载 {len(skills_list)} 个技能")
    logger.info("[Startup] 服务器启动完成，访问 http://localhost:8000/demo 打开 Web 演示界面")


@app.get("/")
def health():
    return {
        "status": "ok",
        "service": "AI Chat Framework",
        "version": "1.0.0",
        "demo": "http://localhost:8000/demo",
        "docs": "http://localhost:8000/docs",
    }
