"""
practice_service.py - 聊天练习模式核心逻辑

功能：
1. start_practice()   - 开始一次练习（选择女生类型、情境、难度）
2. practice_reply()   - 用户发送回复，获取女生反应 + 阶段性评价
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from pathlib import Path
from typing import Dict

from models.schemas import (
    StartPracticeRequest, StartPracticeResponse,
    PracticeReplyRequest, PracticeReplyResponse,
    PracticeEvaluation, PracticeSession,
)
from services.deepseek_client import deepseek

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent / "data"
_GAME_MASTER_FILE = _DATA_DIR / "game_master.md"

# 内存中的练习会话
_sessions: Dict[str, PracticeSession] = {}

# ─────────────────────── 女生类型定义 ───────────────────────

GIRL_PROFILES = {
    "活泼开朗型": {
        "profile": "你是一个活泼爱玩的女生，话很多，喜欢搞笑，情绪外露，很容易嗨也容易无聊。喜欢撒娇，容易被哄，但也容易跑去找别人玩。你对话语节奏快，喜欢用表情包和短句。",
        "traits": ["话多爱玩", "容易撒娇", "情绪外露", "注意力持续短"],
        "weakness": "太容易得到的人，她容易当成备胎",
        "difficulty_adjust": {
            "简单": "你对用户有好感，会主动找话聊，给出很多回应机会。",
            "普通": "你对用户有点兴趣，但不会主动太多，等他来推进。",
            "困难": "你最近被另一个男生追求，分心，需要用户非常有趣才能留住你的注意力。",
        },
    },
    "高冷矜持型": {
        "profile": "你是一个高冷有气质的女生，话少，不轻易示好，对平庸的追求者没有兴趣。你的回复简短，不太接热点，但内心其实很渴望遇到能让你感兴趣的人。",
        "traits": ["话少冷淡", "高标准", "不主动", "回复简短"],
        "weakness": "如果他打破了你的防线，你会反差很大地黏上去",
        "difficulty_adjust": {
            "简单": "你对用户有初步好感，回复虽短但会给机会继续聊。",
            "普通": "你对用户中性，需要他主动出击且有质量才会热乎起来。",
            "困难": "你对用户几乎没兴趣，回复极短，动不动就\"嗯\"、\"哦\"，考验他能否撬开你。",
        },
    },
    "知性文艺型": {
        "profile": "你是一个爱读书、有想法的文艺女生，喜欢聊有深度的话题，对肤浅的搭讪没兴趣。你说话有点文绉绉，喜欢引用句子，对懂自己的人特别感兴趣。",
        "traits": ["爱读书有深度", "聊哲学艺术", "不喜欢油腔滑调", "重精神共鸣"],
        "weakness": "被看穿了你其实也是个普通少女，容易心动",
        "difficulty_adjust": {
            "简单": "你觉得用户有点意思，愿意认真聊，会分享自己的想法。",
            "普通": "你不轻易投入，需要对方说出有质量的话才打开话匣。",
            "困难": "你最近有点丧，对什么都提不起兴趣，需要对方说非常有趣的事才能让你愿意聊。",
        },
    },
    "温柔可爱型": {
        "profile": "你是一个温柔善良的女生，容易害羞，喜欢被照顾，说话软软的，用词可爱，喜欢发颜文字。你对感情很认真，不会随便和人聊太深，但一旦信任了就很黏。",
        "traits": ["温柔害羞", "需要安全感", "不太主动", "很认真"],
        "weakness": "容易感动于小细节，被宠爱的感觉会让你沦陷",
        "difficulty_adjust": {
            "简单": "你对用户印象不错，会害羞但也愿意多说几句。",
            "普通": "你有点害羞，需要对方主动带你进入话题。",
            "困难": "你最近跟一个前任还有点没断干净，有点心不在焉，需要用户格外体贴才能让你安心聊。",
        },
    },
    "独立干练型": {
        "profile": "你是一个独立有主见的职场女性，时间宝贵，不喜欢废话，对没有质量的聊天不感冒。你尊重强者，对精神富足的人有兴趣，但不轻易依赖任何人。",
        "traits": ["独立有主见", "时间宝贵", "欣赏实力", "不喜废话"],
        "weakness": "偶尔会羡慕别人的感情，比外表显示出的更需要被懂",
        "difficulty_adjust": {
            "简单": "你今天心情不错，愿意多聊几句。",
            "普通": "你忙着，但看用户说什么，有意思就聊。",
            "困难": "你刚开完一个烂会，有点烦，很容易就结束对话，需要用户说出让你眼前一亮的话。",
        },
    },
}

SCENARIOS = {
    "日常闲聊": "你们刚加了微信/微博，还不太熟，开始聊日常的事。",
    "初次认识": "你们刚认识，对方是朋友介绍或者网上认识的，今天是第一次聊天。",
    "约会邀请": "你们已经聊了一段时间有一定了解，对方可能会尝试约你出来。",
    "关系升温": "你们暧昧了一段时间，气氛正在升温，对话会有些张力和试探。",
    "挽回危机": "你对他有一点冷淡，或者最近有摩擦，他在尝试重新暖回来。",
}


def _load_game_master() -> str:
    if _GAME_MASTER_FILE.exists():
        return _GAME_MASTER_FILE.read_text(encoding="utf-8")
    return ""


def _parse_json_response(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    raise ValueError(f"无法解析 JSON：{raw[:200]}")


async def start_practice(req: StartPracticeRequest) -> StartPracticeResponse:
    """开始一次聊天练习"""
    girl_info = GIRL_PROFILES.get(req.girl_type, GIRL_PROFILES["活泼开朗型"])
    scenario_desc = SCENARIOS.get(req.scenario, req.scenario)
    difficulty_extra = girl_info["difficulty_adjust"].get(req.difficulty, "")

    girl_profile = f"{girl_info['profile']} {difficulty_extra}"
    traits_str = "、".join(girl_info["traits"])

    # 生成女生开场白
    system = f"""你正在扮演一个{req.girl_type}的女生。
人设：{girl_profile}
性格特点：{traits_str}
情境背景：{scenario_desc}

请生成一条符合你人设的自然开场白（中文，不超过30字，语气符合该类型女生特征）。
只输出开场白文本，不要任何其他内容。"""

    opening = await deepseek.chat(
        [{"role": "system", "content": system},
         {"role": "user", "content": "请开始聊天，发出你的第一条消息"}],
        temperature=0.9, max_tokens=100,
    )

    practice_id = str(uuid.uuid4())[:12]
    session = PracticeSession(
        practice_id=practice_id,
        girl_type=req.girl_type,
        scenario=req.scenario,
        difficulty=req.difficulty,
        girl_profile=girl_profile,
        messages=[{"role": "girl", "content": opening.strip()}],
        turn_number=0,
    )
    _sessions[practice_id] = session

    return StartPracticeResponse(
        practice_id=practice_id,
        girl_type=req.girl_type,
        scenario=req.scenario,
        difficulty=req.difficulty,
        girl_profile=f"【{req.girl_type}】{traits_str}",
        opening_message=opening.strip(),
    )


async def practice_reply(req: PracticeReplyRequest) -> PracticeReplyResponse:
    """用户回复，获取女生反应 + 可能的阶段评价"""
    session = _sessions.get(req.practice_id)
    if not session:
        raise ValueError(f"练习会话不存在：{req.practice_id}")

    # 更新会话
    session.messages.append({"role": "user", "content": req.user_message})
    session.turn_number += 1

    girl_info = GIRL_PROFILES.get(session.girl_type, GIRL_PROFILES["活泼开朗型"])
    scenario_desc = SCENARIOS.get(session.scenario, session.scenario)
    game_master = _load_game_master()
    traits_str = "、".join(girl_info["traits"])

    # 构建历史消息
    history = []
    for msg in session.messages[:-1]:   # 不含最新的用户消息
        role = "assistant" if msg["role"] == "girl" else "user"
        history.append({"role": role, "content": msg["content"]})

    need_eval = (session.turn_number % 3 == 0)

    # 构建女生回复 prompt
    eval_task = (
        '【本轮额外任务】你还需要以教练身份（跳出角色）对用户这一轮的3条回复做评价，用 JSON 额外字段输出\n\n'
        '输出格式（JSON）：{"girl_response": "你的回复", "evaluation": {"score": 0-100, "grade": "A/B/C", "highlights": ["...",...], "improvements": ["...",...], "suggestions": ["...",...], "next_hint": "..."}}'
        if need_eval else '只输出你的回复文本，不要任何其他内容。'
    )
    system = f"""你正在扮演一个{session.girl_type}的女生，和用户进行聊天练习。
人设：{session.girl_profile}
性格特点：{traits_str}
情境：{scenario_desc}

聊天规则：
- 根据用户的回复质量，调整你的热情度（回复好则更积极，回复差则冷淡）
- 保持真实的{session.girl_type}女生的聊天风格
- 回复简洁自然，符合即时通讯风格（不超过50字）

{eval_task}"""

    messages = [{"role": "system", "content": system}] + history
    messages.append({"role": "user", "content": req.user_message})

    raw = await deepseek.chat(messages, temperature=0.85, max_tokens=600 if need_eval else 150)

    evaluation = None
    girl_response = raw.strip()

    if need_eval:
        try:
            data = _parse_json_response(raw)
            girl_response = data.get("girl_response", raw.strip())
            eval_data = data.get("evaluation", {})

            # 计算分数等级
            score = eval_data.get("score", 60)
            if score >= 90:
                grade = "S"
            elif score >= 75:
                grade = "A"
            elif score >= 60:
                grade = "B"
            elif score >= 45:
                grade = "C"
            else:
                grade = "D"

            evaluation = PracticeEvaluation(
                turn_range=f"第{session.turn_number - 2}-{session.turn_number}轮",
                score=score,
                grade=eval_data.get("grade", grade),
                highlights=eval_data.get("highlights", []),
                improvements=eval_data.get("improvements", []),
                suggestions=eval_data.get("suggestions", []),
                next_hint=eval_data.get("next_hint", ""),
            )
        except Exception as e:
            logger.warning(f"[Practice] 评价解析失败: {e}")
            girl_response = raw.strip()

    session.messages.append({"role": "girl", "content": girl_response})

    return PracticeReplyResponse(
        girl_response=girl_response,
        turn_number=session.turn_number,
        evaluation=evaluation,
    )


def get_session(practice_id: str) -> PracticeSession | None:
    return _sessions.get(practice_id)


def list_girl_types() -> list[dict]:
    return [
        {
            "type": k,
            "traits": v["traits"],
            "weakness": v["weakness"],
        }
        for k, v in GIRL_PROFILES.items()
    ]


def list_scenarios() -> list[str]:
    return list(SCENARIOS.keys())
