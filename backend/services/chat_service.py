"""
核心业务服务层：Skills 管理 + Session 管理 + Chat 逻辑
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from models.schemas import (
    Session, Message, Skill, SkillExample,
    SendMessageResponse, CreateSessionRequest,
    SessionListItem,
)
from services.deepseek_client import deepseek
from services.memory_service import memory_service

logger = logging.getLogger(__name__)

# ─────────────────────── 存储路径 ───────────────────────

_BASE = Path(__file__).parent.parent / "data"
SESSIONS_DIR = _BASE / "sessions"
SKILLS_FILE = _BASE / "skills.json"
DEFAULT_SKILLS_FILE = _BASE / "default_skills.json"


def _ensure_dirs():
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────── Skills IO ───────────────────────

def _load_skills() -> List[Skill]:
    _ensure_dirs()
    if not SKILLS_FILE.exists():
        if DEFAULT_SKILLS_FILE.exists():
            import shutil
            shutil.copy(DEFAULT_SKILLS_FILE, SKILLS_FILE)
        else:
            return []
    with open(SKILLS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return [Skill(**s) for s in data.get("skills", [])]


def _save_skills(skills: List[Skill]):
    _ensure_dirs()
    with open(SKILLS_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {"skills": [s.model_dump() for s in skills]},
            f,
            ensure_ascii=False,
            indent=2,
        )


# ─────────────────────── Session IO ───────────────────────

def _session_path(session_id: str) -> Path:
    return SESSIONS_DIR / f"{session_id}.json"


def _load_session(session_id: str) -> Optional[Session]:
    path = _session_path(session_id)
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return Session(**json.load(f))


def _save_session(session: Session):
    _ensure_dirs()
    session.updated_at = datetime.now().isoformat(timespec="seconds")
    with open(_session_path(session.session_id), "w", encoding="utf-8") as f:
        json.dump(session.model_dump(), f, ensure_ascii=False, indent=2)


def _list_sessions() -> List[Session]:
    _ensure_dirs()
    sessions = []
    for p in sorted(
        SESSIONS_DIR.glob("*.json"),
        key=lambda x: x.stat().st_mtime,
        reverse=True,
    ):
        try:
            with open(p, encoding="utf-8") as f:
                sessions.append(Session(**json.load(f)))
        except Exception as exc:
            logger.warning(f"无法加载会话 {p.name}: {exc}")
    return sessions


# ─────────────────────── Prompt 构建 ───────────────────────

def _fmt_skills(skills: List[Skill]) -> str:
    if not skills:
        return "（未指定技能，使用自然对话风格）"
    parts = []
    for sk in skills:
        part = f"【{sk.name}】（{sk.category}，语调：{sk.tone}）\n  说明：{sk.description}"
        if sk.examples:
            part += "\n  示例："
            for ex in sk.examples[:2]:
                part += f"\n    • 情境：{ex.context}"
                part += f"\n      回复：{ex.response}"
        parts.append(part)
    return "\n\n".join(parts)


def _build_api_messages(
    session: Session,
    skills: List[Skill],
    user_message: str,
) -> List[dict]:
    system = f"""你是一个聊天回复辅助系统，你的任务是扮演角色B，根据A的消息生成真实自然的回复。

【角色设定】
• 发起方 A：{session.persona_a.name}
  {session.persona_a.description or '普通人'}
• 回复方 B：{session.persona_b.name}（你将扮演B）
  {session.persona_b.description or '普通人'}

【回复技能指导】
{_fmt_skills(skills)}

【严格规则】
1. 只输出B的回复内容，不要加角色名称前缀
2. 回复要简洁自然，符合日常即时通讯风格
3. 严格遵循技能指导的风格和语调
4. 不要解释你的思考过程
5. 中文回复，保持角色一致性"""

    if session.memory_summary:
        system += f"\n\n【对话历史摘要（供参考）】\n{session.memory_summary}"

    messages = [{"role": "system", "content": system}]

    # 注入最近对话历史（最多10条）
    for msg in session.messages[-10:]:
        name = session.persona_a.name if msg.role == "A" else session.persona_b.name
        if msg.role == "A":
            messages.append({"role": "user", "content": f"{name}：{msg.content}"})
        else:
            messages.append({"role": "assistant", "content": msg.content})

    messages.append({"role": "user", "content": f"{session.persona_a.name}：{user_message}"})
    return messages


# ─────────────────────── ChatService ───────────────────────

class ChatService:

    # ── Skills ──────────────────────────────────────────────

    def get_all_skills(self) -> List[Skill]:
        return _load_skills()

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        return next((s for s in _load_skills() if s.skill_id == skill_id), None)

    def add_skill(self, skill: Skill) -> Skill:
        skills = _load_skills()
        skills.append(skill)
        _save_skills(skills)
        return skill

    def update_skill(self, skill_id: str, updated: Skill) -> Optional[Skill]:
        skills = _load_skills()
        for i, s in enumerate(skills):
            if s.skill_id == skill_id:
                updated.skill_id = skill_id
                skills[i] = updated
                _save_skills(skills)
                return updated
        return None

    def delete_skill(self, skill_id: str) -> bool:
        skills = _load_skills()
        new = [s for s in skills if s.skill_id != skill_id]
        if len(new) == len(skills):
            return False
        _save_skills(new)
        return True

    def reset_skills(self) -> List[Skill]:
        """重置为默认技能列表"""
        if DEFAULT_SKILLS_FILE.exists():
            import shutil
            shutil.copy(DEFAULT_SKILLS_FILE, SKILLS_FILE)
        return _load_skills()

    # ── Sessions ─────────────────────────────────────────────

    def create_session(self, req: CreateSessionRequest) -> Session:
        session = Session(
            title=req.title,
            persona_a=req.persona_a,
            persona_b=req.persona_b,
            skill_ids=req.skill_ids,
        )
        _save_session(session)
        logger.info(f"[Session] 创建会话 {session.session_id}: {req.title}")
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        return _load_session(session_id)

    def list_sessions(self) -> List[SessionListItem]:
        sessions = _list_sessions()
        items = []
        for s in sessions:
            last_msg = ""
            if s.messages:
                last = s.messages[-1]
                prefix = "A: " if last.role == "A" else "B: "
                last_msg = prefix + last.content[:30] + ("…" if len(last.content) > 30 else "")
            items.append(SessionListItem(
                session_id=s.session_id,
                title=s.title,
                persona_a_name=s.persona_a.name,
                persona_b_name=s.persona_b.name,
                message_count=len(s.messages),
                last_message=last_msg,
                updated_at=s.updated_at,
            ))
        return items

    def delete_session(self, session_id: str) -> bool:
        path = _session_path(session_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def update_session_skills(self, session_id: str, skill_ids: List[str]) -> Optional[Session]:
        session = _load_session(session_id)
        if not session:
            return None
        session.skill_ids = skill_ids
        _save_session(session)
        return session

    def clear_session_messages(self, session_id: str) -> Optional[Session]:
        session = _load_session(session_id)
        if not session:
            return None
        session.messages = []
        session.memory_summary = ""
        _save_session(session)
        return session

    # ── Chat ─────────────────────────────────────────────────

    async def send_message(self, session_id: str, content: str) -> SendMessageResponse:
        """处理 A 的消息，生成 B 的回复"""
        session = _load_session(session_id)
        if not session:
            raise ValueError(f"会话 {session_id} 不存在")

        # 获取会话关联的技能
        all_skills = _load_skills()
        active_skills = [s for s in all_skills if s.skill_id in session.skill_ids]

        # 构建 Prompt 并调用 DeepSeek
        api_messages = _build_api_messages(session, active_skills, content)
        reply = await deepseek.chat(api_messages, temperature=0.85, max_tokens=600)

        # 创建消息对象
        msg_a = Message(role="A", content=content)
        msg_b = Message(role="B", content=reply)

        # 追加到会话
        session.messages.append(msg_a)
        session.messages.append(msg_b)

        # 尝试记忆压缩
        session, compressed = await memory_service.maybe_compress(session)

        # 持久化
        _save_session(session)

        logger.info(
            f"[Chat] session={session_id} "
            f"A: {content[:30]}… → B: {reply[:30]}…"
        )

        return SendMessageResponse(
            message_a=msg_a,
            message_b=msg_b,
            session_id=session_id,
            memory_updated=compressed,
        )


# 全局单例
chat_service = ChatService()
