"""
summary_service.py - 对话摘要与深度分析

1. summarize_conversation() - 对消息记录做 AI 摘要，存入 context_summary 字段
2. analyze_conversation()   - 基于 game_master.md 框架进行深度分析，返回完整评估
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional

from services.deepseek_client import deepseek

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent / "data"
_GAME_MASTER_PATHS = [
    Path(__file__).parent.parent.parent / "game_master.md",  # game_chat/game_master.md
    _DATA_DIR / "game_master.md",
]


def _load_game_master() -> str:
    for p in _GAME_MASTER_PATHS:
        if p.exists():
            return p.read_text(encoding="utf-8")
    return ""


def _extract_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return {}


# ─── 摘要 ──────────────────────────────────────────────────

async def summarize_conversation(conversation_id: str) -> Optional[str]:
    """
    对整段对话进行 AI 摘要，提炼关键信息，存入 context_summary。
    返回摘要 JSON 字符串，若消息不足则返回 None。
    """
    from services.conversation_service import get_conversation, update_conversation

    conv = get_conversation(conversation_id)
    if not conv or not conv.get("messages"):
        return None

    messages = conv["messages"]
    if len(messages) < 4:
        return None

    chat_lines = [
        f"{'她' if m['role'] == 'girl' else '我'}: {m['content']}"
        for m in messages
    ]
    chat_text = "\n".join(chat_lines)
    name = conv.get("name", "她")
    goal = conv.get("goal", "恋爱")

    user_msg = f"""分析和 {name}（聊天目标：{goal}）的对话记录：

{chat_text}

请严格输出以下 JSON，不要任何其他文字：
{{
  "summary": "关系进展总结（3-5句）",
  "her_traits": ["性格特点1", "特点2", "特点3"],
  "her_interests": ["兴趣1", "兴趣2"],
  "relationship_stage": "当前阶段（陌生/初识/暧昧/升温/热度/稳定/冷却）",
  "key_events": ["关键事件1", "事件2"],
  "recommended_style": "当前最适合的回复风格（极简冷感款/反客为主款/幽默调侃款/温柔推进款/深度连接款）",
  "momentum": "关系势头（上升/平稳/下降）"
}}"""

    try:
        raw = await deepseek.chat(
            [
                {"role": "system", "content": "你是专业的人际关系分析师，善于从聊天记录中提炼关键信息。"},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.3,
            max_tokens=800,
        )
        data = _extract_json(raw)
        summary_str = json.dumps(data, ensure_ascii=False)
        update_conversation(conversation_id, context_summary=summary_str)
        logger.info(f"[Summary] conversation {conversation_id} summarized ({len(messages)} messages)")
        return summary_str
    except Exception as exc:
        logger.error(f"[Summary] Failed for {conversation_id}: {exc}")
        return None


# ─── 深度分析 ─────────────────────────────────────────────

async def analyze_conversation(conversation_id: str) -> Dict[str, Any]:
    """
    基于 game_master.md 框架对整段对话进行深度分析。
    返回阶段评估、行动建议、风格推荐等。
    """
    from services.conversation_service import get_conversation

    conv = get_conversation(conversation_id)
    if not conv:
        raise ValueError(f"会话 {conversation_id} 不存在")

    messages = conv.get("messages", [])
    game_master = _load_game_master()
    name = conv.get("name", "她")
    goal = conv.get("goal", "恋爱")

    if len(messages) < 2:
        return {
            "conversation_id": conversation_id,
            "stage_assessment": "对话记录不足，无法分析。请先进行聊天再分析。",
            "momentum_score": 50,
            "style_recommendations": [],
            "key_patterns": [],
            "strengths": [],
            "weaknesses": [],
            "action_items": ["先积累更多对话记录（至少 10 轮）再进行深度分析"],
            "next_move": "继续对话，积累更多数据",
            "summary": "暂无充足数据",
        }

    # 构建对话文本（最近 30 条）
    recent = messages[-30:]
    chat_lines = [
        f"{'她' if m['role'] == 'girl' else '我'}: {m['content']}"
        for m in recent
    ]
    chat_text = "\n".join(chat_lines)

    existing_summary = conv.get("context_summary", "")
    summary_block = ""
    if existing_summary:
        try:
            s = json.loads(existing_summary)
            if isinstance(s, dict):
                summary_block = f"\n【AI 历史摘要】\n关系阶段：{s.get('relationship_stage','未知')}，势头：{s.get('momentum','未知')}，推荐风格：{s.get('recommended_style','无')}\n"
        except Exception:
            summary_block = f"\n【历史摘要】{existing_summary[:200]}\n"

    user_msg = f"""请基于 GAME MASTER 框架，深度分析以下和 {name}（目标：{goal}）的对话：
{summary_block}
【近期对话（最多30条）】
{chat_text}

严格输出以下 JSON，不要任何其他文字：
{{
  "stage_assessment": "当前关系阶段评估和整体走向（3-4句）",
  "momentum_score": 75,
  "style_recommendations": ["当前应优先使用的风格及原因1", "建议2"],
  "key_patterns": ["发现的对话规律1", "规律2", "规律3"],
  "strengths": ["你做得好的地方1", "优势2"],
  "weaknesses": ["需要改进的问题1", "不足2"],
  "action_items": ["具体可执行的行动建议1", "建议2", "建议3"],
  "next_move": "当前最应该做的一件事（一句话，具体可操作）",
  "summary": "总体评价（2-3句）"
}}"""

    try:
        raw = await deepseek.chat(
            [
                {"role": "system", "content": f"你是顶级恋爱教练，严格基于以下 GAME MASTER 框架进行分析：\n\n{game_master}"},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.5,
            max_tokens=1500,
        )
        data = _extract_json(raw)
        return {
            "conversation_id": conversation_id,
            "stage_assessment": data.get("stage_assessment", ""),
            "momentum_score": int(data.get("momentum_score", 50)),
            "style_recommendations": data.get("style_recommendations", []),
            "key_patterns": data.get("key_patterns", []),
            "strengths": data.get("strengths", []),
            "weaknesses": data.get("weaknesses", []),
            "action_items": data.get("action_items", []),
            "next_move": data.get("next_move", ""),
            "summary": data.get("summary", ""),
        }
    except Exception as exc:
        logger.error(f"[Analysis] Failed for {conversation_id}: {exc}")
        raise
