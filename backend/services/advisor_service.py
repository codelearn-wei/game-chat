"""
advisor_service.py - 回复顾问核心逻辑

1. analyze_message()      - 分析女方消息，结合会话历史，生成 5 种风格回复建议
2. feedback_regenerate()  - 用户反馈不满意，重新生成优化版建议
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path

from models.schemas import AnalyzeRequest, AnalyzeResponse, FeedbackRequest, ReplyStyle
from services.deepseek_client import deepseek

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent / "data"
# 优先读取项目根目录 game_chat/game_master.md，回退到 data/ 目录
_GAME_MASTER_PATHS = [
    Path(__file__).parent.parent.parent / "game_master.md",  # game_chat/game_master.md
    _DATA_DIR / "game_master.md",                            # game_chat/backend/data/game_master.md
]


def _load_game_master() -> str:
    for p in _GAME_MASTER_PATHS:
        if p.exists():
            return p.read_text(encoding="utf-8")
    return "(game_master.md 未找到)"


def _load_skills_reference() -> str:
    """从 skills.json 加载技能库，返回简洁提示词片段"""
    skills_path = _DATA_DIR / "skills.json"
    if not skills_path.exists():
        return ""
    try:
        data = json.loads(skills_path.read_text(encoding="utf-8"))
        skills = data.get("skills", [])
        lines = ["【可用技能库（在 reasoning 说明使用了哪个技能，used_skill 填技能名称）】"]
        for s in skills:
            exs = s.get("examples", [])
            ex_text = f'示例回复: "{exs[0]["response"]}"' if exs else ""
            lines.append(f"• {s['name']}（{s['category']}）: {s['description'][:60]} {ex_text}")
        return "\n".join(lines)
    except Exception:
        return ""


_STYLES_JSON = """[
  {
    "style_name": "极简冷感款", "style_icon": "🧊",
    "style_desc": "话少有态度，降低需求感，制造追逐动力",
    "replies": ["回复1", "回复2", "回复3"],
    "reasoning": "说明：呼应了 GM 哪条原则 + 使用了哪个技能 + 为何这样回有效（2-3句）",
    "used_skill": "技能名"
  },
  {
    "style_name": "反客为主款", "style_icon": "♟️",
    "style_desc": "夺回主导权，推动三步节奏向「聊我们」迈进",
    "replies": ["回复1", "回复2", "回复3"],
    "reasoning": "说明：呼应了 GM 哪条原则 + 使用了哪个技能 + 为何这样回有效（2-3句）",
    "used_skill": "技能名"
  },
  {
    "style_name": "幽默调侃款", "style_icon": "😏",
    "style_desc": "反差制造情绪张力，冷读回应显示「我懂你」",
    "replies": ["回复1", "回复2", "回复3"],
    "reasoning": "说明：呼应了 GM 哪条原则 + 使用了哪个技能 + 为何这样回有效（2-3句）",
    "used_skill": "技能名"
  },
  {
    "style_name": "温柔推进款", "style_icon": "🌊",
    "style_desc": "奶狗模式给安全感，同时锚定目标推进关系",
    "replies": ["回复1", "回复2", "回复3"],
    "reasoning": "说明：呼应了 GM 哪条原则 + 使用了哪个技能 + 为何这样回有效（2-3句）",
    "used_skill": "技能名"
  },
  {
    "style_name": "深度连接款", "style_icon": "🔗",
    "style_desc": "情感共鸣+高价值展示，传递「值得被重视」信号",
    "replies": ["回复1", "回复2", "回复3"],
    "reasoning": "说明：呼应了 GM 哪条原则 + 使用了哪个技能 + 为何这样回有效（2-3句）",
    "used_skill": "技能名"
  }
]"""

_OUTPUT_SCHEMA = """{
  "overall_strategy": "当前局势判断：她的意图/情绪+我方优劣势（2-3句，直接给结论）",
  "next_direction": "本轮回复后下一步推进方向（1-2句，具体可执行）",
  "styles": """ + _STYLES_JSON + """
}"""


def _build_context_blocks(girl_message: str, conversation_id: str | None,
                          context_override: str) -> tuple[str, str]:
    """返回 (goal_str, context_block)"""
    goal_str = "自然推进"
    context_block = ""

    if conversation_id:
        from services.conversation_service import get_conversation
        conv = get_conversation(conversation_id)
        if conv:
            goal_str = conv.get("goal") or "自然推进"

            # AI 摘要画像
            raw_summary = conv.get("context_summary", "")
            if raw_summary:
                try:
                    s = json.loads(raw_summary)
                    if isinstance(s, dict):
                        context_block += (
                            "\n【AI 总结的关系画像】\n"
                            f"- 关系阶段：{s.get('relationship_stage', '未知')}\n"
                            f"- 她的特点：{', '.join(s.get('her_traits', []))}\n"
                            f"- 她的兴趣：{', '.join(s.get('her_interests', []))}\n"
                            f"- 关键事件：{', '.join(s.get('key_events', []))}\n"
                            f"- 推荐风格：{s.get('recommended_style', '根据情况')}\n"
                            f"- 关系势头：{s.get('momentum', '平稳')}\n"
                        )
                except Exception:
                    context_block += f"\n【关系摘要】\n{raw_summary[:300]}\n"

            # 近期对话
            recent = conv.get("messages", [])[-12:]
            if recent:
                lines = [
                    f"{'她' if m['role'] == 'girl' else '我'}: {m['content']}"
                    for m in recent
                ]
                context_block += "\n【近期对话记录】\n" + "\n".join(lines) + "\n"

    # 手动上下文覆盖
    if context_override.strip():
        context_block = "\n【聊天上下文】\n" + context_override.strip() + "\n"

    return goal_str, context_block


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
    raise ValueError(f"无法解析 LLM 返回的 JSON：{raw[:200]}")


def _build_response(data: dict) -> AnalyzeResponse:
    styles = []
    for s in data.get("styles", []):
        styles.append(ReplyStyle(
            style_name=s.get("style_name", ""),
            style_icon=s.get("style_icon", "💬"),
            style_desc=s.get("style_desc", ""),
            replies=s.get("replies", []),
            reasoning=s.get("reasoning", ""),
            used_skill=s.get("used_skill"),  # 来自 skills.json 的技能名称
        ))
    return AnalyzeResponse(
        overall_strategy=data.get("overall_strategy", ""),
        next_direction=data.get("next_direction", ""),
        styles=styles,
    )


async def analyze_message(req: AnalyzeRequest) -> AnalyzeResponse:
    """分析女方消息，生成 5 种风格的高价值回复建议"""
    # 保存女方消息到会话历史
    if req.conversation_id:
        from services.conversation_service import add_message, get_message_count
        add_message(req.conversation_id, "girl", req.girl_message)
        # 每 20 条消息自动触发摘要
        count = get_message_count(req.conversation_id)
        if count >= 10 and count % 20 == 0:
            from services.summary_service import summarize_conversation
            asyncio.create_task(summarize_conversation(req.conversation_id))

    goal_str, context_block = _build_context_blocks(
        req.girl_message, req.conversation_id, req.context
    )
    game_master = _load_game_master()
    skills_ref = _load_skills_reference()

    system = f"""你是顶级恋爱聊天回复导师，严格基于「GameMaster 框架」生成高价值回复建议。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【GAMEMASTER 核心原则】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

▌一、底层铁律（每条回复的硬约束）
① 绝不暴露需求感 — 保持"可得但非必须"，不秒回感、不讨好、不单向付出
② 情绪稳定松弛 — 不因冷淡/试探而焦虑，始终"沉得住气"
③ 强主体性自信 — 对话主动权始终掌握在自己手中，不迎合不卑微

▌二、语言与沟通风格
④ 反差感语言 — 幽默/正经灵活切换，通过反差制造情绪张力，避免单一乏味
⑤ 冷读潜沟通 — 读懂她的小心思与情绪波动，回应传递「我懂你」而非直接点破
⑥ 奶狗×狼狗双模式 — 她脆弱时温柔给安全感；推进关系时展现果断主导权

▌三、关系推进逻辑
⑦ 突破框架 — 合适时机从「朋友框架」转入「暧昧/男女框架」
⑧ 目标锚定 — 恋爱目标侧重情感共鸣+价值观；玩伴目标侧重暧昧张力+轻松氛围
⑨ 守住边界 — 不被当情绪垃圾桶/被养鱼，不接受模糊关系定位
⑩ 三步节奏：「聊你」→「聊我」→「聊我们」
   · 聊你：引导她分享，建立舒适感
   · 聊我：展示个人价值，不做话题工具人
   · 聊我们：引入共同场景/话题，构建「我们」的共同预期 ← 闭环必达

▌四、价值展现与应变
⑪ 自然植入优势 — 将经历/特长/成就融入对话，不生硬自夸
⑫ 高价值信号 — 传递「你是优质且值得被重视的人」
⑬ 强应变能力 — 面对拒绝/冷场保持冷静，高情商化解甚至制造张力

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【生成前必做自检——每条回复都要通过这 4 关】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✗ 是否暴露了过度需求感？（不通过 → 重写）
✗ 是否丢失了自身框架？（不通过 → 重写）
✓ 是否推进了关系或制造了张力？（无效闲聊 → 重写）
✓ 语气/模式是否匹配当前场景？（不符 → 调整）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【绝对禁忌——以下模式绝不出现在回复中】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✗ 长篇小作文 / 秒回感 / 无底线讨好
✗ 只聊她或只聊自己，未完成「聊我们」闭环
✗ 生硬自夸 / 炫富 / 暴露过度隐私
✗ 被拒后辩解道歉反复解释
✗ 廉价赞美（漂亮/善良/温柔）
✗ 连续提问（把自己变成采访者）
✗ 双重发送（发完再补，显得焦虑）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【5 种回复风格与对应原则】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧊 极简冷感款 → 核心原则①③，降低需求感，制造追逐动力
♟️ 反客为主款 → 核心原则③⑩，夺回主导权，推动「聊我们」
😏 幽默调侃款 → 核心原则④⑤，反差张力+冷读展示「我懂你」
🌊 温柔推进款 → 核心原则⑥⑦⑧，奶狗模式+目标锚定
🔗 深度连接款 → 核心原则⑤⑫，情感共鸣+高价值信号

每种风格的 reasoning 必须明确说明：
· 使用了 GM 哪条原则（写原则编号+名称）
· 匹配了哪个技能（来自技能库）
· 为什么这样回能有效推进（1-2句逻辑说明）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{skills_ref}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

输出规则：
· 每条回复 ≤20字，符合真实聊天语气，不要括号说明
· 每种风格生成 3 条不同回复供选择
· 严格输出 JSON，不加任何前缀/后缀/代码块标记

{_OUTPUT_SCHEMA}"""

    user_content = (
        f"聊天目标：{goal_str}\n"
        f"{context_block}\n"
        f"【她刚发来的消息】\n{req.girl_message}\n\n请生成回复建议。"
    )

    raw = await deepseek.chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user_content}],
        temperature=0.85,
        max_tokens=2500,
    )
    logger.info(f"[Advisor] analyze done, len={len(raw)}")
    return _build_response(_parse_json_response(raw))


async def feedback_regenerate(req: FeedbackRequest) -> AnalyzeResponse:
    """根据用户反馈，重新生成更符合需求的回复建议"""
    goal_str, context_block = _build_context_blocks(
        req.girl_message, req.conversation_id, req.context
    )
    game_master = _load_game_master()
    skills_ref = _load_skills_reference()

    system = f"""你是顶级恋爱聊天回复导师，严格基于「GameMaster 框架」重新生成更优质的建议。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【GAMEMASTER 核心原则（同样适用）】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
① 绝不暴露需求感 ② 情绪稳定松弛 ③ 强主体性自信
④ 反差感语言 ⑤ 冷读潜沟通 ⑥ 奶狗×狼狗双模式
⑦ 突破框架 ⑧ 目标锚定 ⑨ 守住边界 ⑩ 三步节奏（聊你→聊我→聊我们）
⑪ 自然植入优势 ⑫ 高价值信号 ⑬ 强应变能力

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【绝对禁忌】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✗ 长篇小作文/秒回感/无底线讨好 ✗ 未完成「聊我们」闭环
✗ 生硬自夸/炫富 ✗ 被拒后辩解道歉 ✗ 廉价赞美 ✗ 连续提问 ✗ 双重发送

{skills_ref}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【本次任务：针对用户反馈改进】
用户指出上一版的不足，请在保持 GM 框架约束的前提下，重点改进用户提到的问题。
每条回复 ≤20字，reasoning 写明使用的 GM 原则编号+技能名+改进逻辑。
严格输出 JSON，不加任何前缀/后缀：

{_OUTPUT_SCHEMA}"""

    user_content = (
        f"聊天目标：{goal_str}\n"
        f"{context_block}\n"
        f"【她发来的消息】\n{req.girl_message}\n\n"
        f"【用户反馈（上一版哪里不够好）】\n{req.feedback}\n\n"
        f"请根据反馈改进，特别注意满足用户需求。输出 JSON：\n{_OUTPUT_SCHEMA}"
    )

    raw = await deepseek.chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user_content}],
        temperature=0.9,
        max_tokens=2500,
    )
    logger.info(f"[Advisor] feedback regen done, len={len(raw)}")
    return _build_response(_parse_json_response(raw))
