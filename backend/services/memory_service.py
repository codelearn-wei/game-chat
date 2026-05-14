"""
记忆压缩服务
当对话消息超过阈值时，自动将旧消息总结为摘要，保持上下文窗口在合理范围内。
"""
from __future__ import annotations

import logging
from typing import List

from models.schemas import Session, Message
from services.deepseek_client import deepseek

logger = logging.getLogger(__name__)

# 保留最近多少条消息（全文）
MEMORY_WINDOW = 10
# 总消息数超过多少时触发压缩
SUMMARIZE_THRESHOLD = 20


class MemoryService:

    async def maybe_compress(self, session: Session) -> tuple[Session, bool]:
        """
        如果消息数超过阈值，把旧消息压缩成摘要。
        返回 (更新后的 session, 是否发生了压缩)
        """
        if len(session.messages) <= SUMMARIZE_THRESHOLD:
            return session, False

        old_msgs = session.messages[:-MEMORY_WINDOW]
        recent_msgs = session.messages[-MEMORY_WINDOW:]

        logger.info(
            f"[Memory] session={session.session_id} "
            f"压缩 {len(old_msgs)} 条旧消息"
        )

        try:
            new_summary = await self._summarize(
                session=session,
                messages=old_msgs,
                existing_summary=session.memory_summary,
            )
            session.memory_summary = new_summary
            session.messages = recent_msgs
            logger.info(f"[Memory] 摘要长度: {len(new_summary)} 字")
            return session, True
        except Exception as exc:
            logger.warning(f"[Memory] 压缩失败，保留全部历史: {exc}")
            return session, False

    async def _summarize(
        self,
        session: Session,
        messages: List[Message],
        existing_summary: str,
    ) -> str:
        """使用 DeepSeek 对旧消息生成压缩摘要"""
        conv_lines = []
        for m in messages:
            name = session.persona_a.name if m.role == "A" else session.persona_b.name
            conv_lines.append(f"{name}：{m.content}")
        conv_text = "\n".join(conv_lines)

        prefix = f"【已有摘要】{existing_summary}\n\n" if existing_summary else ""
        prompt = (
            f"{prefix}"
            f"【需要总结的对话】\n{conv_text}\n\n"
            "请将以上对话内容压缩成简洁摘要（100字以内），"
            "保留关键信息、情绪变化、重要话题，供后续对话参考。"
        )

        msgs = [
            {
                "role": "system",
                "content": "你是一个对话摘要助手，请用中文输出简洁摘要。",
            },
            {"role": "user", "content": prompt},
        ]
        return await deepseek.chat(msgs, temperature=0.3, max_tokens=200)


# 全局单例
memory_service = MemoryService()
