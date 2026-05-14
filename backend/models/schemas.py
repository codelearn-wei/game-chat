from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid


def _uid(n: int = 8) -> str:
    return str(uuid.uuid4()).replace("-", "")[:n]


# ─────────────────────── 基础实体 ───────────────────────

class Persona(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    description: str = Field(default="", max_length=300)
    background: str = Field(default="", max_length=500)


class SkillExample(BaseModel):
    context: str = ""
    response: str = ""


class Skill(BaseModel):
    skill_id: str = Field(default_factory=lambda: _uid(8))
    name: str
    category: str = "通用"
    description: str = ""
    tone: str = "自然"
    keywords: List[str] = []
    examples: List[SkillExample] = []


class Message(BaseModel):
    message_id: str = Field(default_factory=lambda: _uid(8))
    role: str  # "A" 或 "B"
    content: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


class Session(BaseModel):
    session_id: str = Field(default_factory=lambda: _uid(12))
    title: str = "新对话"
    persona_a: Persona
    persona_b: Persona
    skill_ids: List[str] = []
    messages: List[Message] = []
    memory_summary: str = ""
    created_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


# ─────────────────────── 请求/响应模型 ───────────────────────

class CreateSessionRequest(BaseModel):
    title: str = "新对话"
    persona_a: Persona
    persona_b: Persona
    skill_ids: List[str] = []


class UpdateSessionSkillsRequest(BaseModel):
    skill_ids: List[str]


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)


class SendMessageResponse(BaseModel):
    message_a: Message
    message_b: Message
    session_id: str
    memory_updated: bool = False


class CreateSkillRequest(BaseModel):
    name: str
    category: str = "通用"
    description: str = ""
    tone: str = "自然"
    keywords: List[str] = []
    examples: List[SkillExample] = []


class SkillsListResponse(BaseModel):
    skills: List[Skill]
    total: int


class SessionListItem(BaseModel):
    session_id: str
    title: str
    persona_a_name: str
    persona_b_name: str
    message_count: int
    last_message: str
    updated_at: str


class SessionListResponse(BaseModel):
    sessions: List[SessionListItem]
    total: int


# ─────────────────────── 回复顾问模式 ───────────────────────

class Snapshot(BaseModel):
    """聊天快照：当前关系状态信息"""
    relationship_stage: str = "初识"        # 初识 / 暧昧期 / 追求中 / 稳定期 / 修复期
    current_goal: str = ""                  # 当前目标（如：约出来 / 升温 / 保持热度）
    girl_traits: List[str] = []             # 她的特点标签（如：高冷、黏人、文艺）
    interests: str = ""                     # 她的兴趣爱好
    notes: str = ""                         # 重要事件/记录


class AnalyzeRequest(BaseModel):
    girl_message: str = Field(..., min_length=1, max_length=2000)  # 她发的消息
    conversation_id: Optional[str] = None                          # 关联的会话 ID（自动加载历史）
    context: str = Field(default="", max_length=5000)              # 手动上下文（可选补充）


class FeedbackRequest(BaseModel):
    """用户对回复建议不满意，提供反馈重新生成"""
    girl_message: str = Field(..., min_length=1, max_length=2000)
    feedback: str = Field(..., min_length=1, max_length=500)        # 哪里不够好
    conversation_id: Optional[str] = None
    context: str = ""


class ReplyStyle(BaseModel):
    style_name: str          # 如：极简冷感款
    style_icon: str          # emoji
    style_desc: str          # 一句话描述
    replies: List[str]       # 3条具体回复
    reasoning: str           # 导师解读（为什么这么回）
    used_skill: Optional[str] = None  # 使用的技能名称（来自 skills.json）
    used_skill: Optional[str] = None  # 使用的技能名称（来自 skills.json）


class AnalyzeResponse(BaseModel):
    overall_strategy: str    # 整体策略建议
    next_direction: str      # 下一步方向
    styles: List[ReplyStyle]


class ParseContextRequest(BaseModel):
    """粘贴聊天记录，AI 自动提取快照信息"""
    raw_context: str = Field(..., min_length=10, max_length=8000)


class ParseContextResponse(BaseModel):
    summary: str
    inferred_stage: str
    inferred_traits: List[str]
    inferred_goal: str
    key_events: List[str]


# ─────────────────────── 聊天练习模式 ───────────────────────

class StartPracticeRequest(BaseModel):
    girl_type: str = "活泼开朗型"   # 活泼开朗型 / 高冷矜持型 / 知性文艺型 / 温柔可爱型 / 独立干练型
    scenario: str = "日常闲聊"     # 日常闲聊 / 初次认识 / 约会邀请 / 关系升温 / 挽回危机
    difficulty: str = "普通"       # 简单 / 普通 / 困难


class StartPracticeResponse(BaseModel):
    practice_id: str
    girl_type: str
    scenario: str
    difficulty: str
    girl_profile: str      # 女生人设描述
    opening_message: str   # 女生的开场白


class PracticeReplyRequest(BaseModel):
    practice_id: str
    user_message: str = Field(..., min_length=1, max_length=500)


class PracticeEvaluation(BaseModel):
    turn_range: str           # 如 "第1-3轮"
    score: int                # 0-100
    grade: str                # S/A/B/C/D
    highlights: List[str]     # 做得好的地方
    improvements: List[str]   # 需要改进的地方
    suggestions: List[str]    # 具体改进建议
    next_hint: str            # 下一步提示


class PracticeReplyResponse(BaseModel):
    girl_response: str
    turn_number: int
    evaluation: Optional[PracticeEvaluation] = None   # 每3轮触发一次


class PracticeSession(BaseModel):
    """练习会话（存储在内存）"""
    practice_id: str
    girl_type: str
    scenario: str
    difficulty: str
    girl_profile: str
    messages: List[dict] = []   # {"role": "user"/"girl", "content": "..."}
    turn_number: int = 0
