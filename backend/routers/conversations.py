"""
conversations.py - 会话管理路由

GET    /api/conversations          - 列出所有会话
POST   /api/conversations          - 新建会话
GET    /api/conversations/{id}     - 获取会话详情（含消息历史）
PATCH  /api/conversations/{id}     - 更新会话信息
DELETE /api/conversations/{id}     - 删除会话
POST   /api/conversations/{id}/record    - 记录用户实际发送的回复
POST   /api/conversations/{id}/summarize - 手动触发 AI 摘要
GET    /api/conversations/{id}/analysis  - 深度分析
"""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


# ─── 请求模型 ──────────────────────────────────────────────

class ConvCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    goal: str = "恋爱"   # 恋爱 / 玩伴 / 普通朋友
    notes: str = ""


class ConvUpdate(BaseModel):
    name: Optional[str] = None
    goal: Optional[str] = None
    notes: Optional[str] = None


class RecordRequest(BaseModel):
    used_reply: str = Field(..., min_length=1, max_length=500)


class BatchRecordRequest(BaseModel):
    messages: list  # [{role: 'girl'|'me', content: str}]


# ─── 路由 ─────────────────────────────────────────────────

@router.get("")
async def list_conversations():
    from services.conversation_service import list_conversations as _list
    return {"conversations": _list()}


@router.post("")
async def create_conversation(req: ConvCreate):
    from services.conversation_service import create_conversation as _create
    conv = _create(req.name, req.goal, req.notes)
    # 不返回 messages 列表
    return {k: v for k, v in conv.items() if k != "messages"}


@router.get("/{conv_id}")
async def get_conversation(conv_id: str):
    from services.conversation_service import get_conversation as _get
    conv = _get(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")
    return conv


@router.patch("/{conv_id}")
async def update_conversation(conv_id: str, req: ConvUpdate):
    from services.conversation_service import update_conversation as _update
    conv = _update(conv_id, **req.model_dump(exclude_none=True))
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {k: v for k, v in conv.items() if k != "messages"}


@router.delete("/{conv_id}")
async def delete_conversation(conv_id: str):
    from services.conversation_service import delete_conversation as _delete
    ok = _delete(conv_id)
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"ok": True}


@router.post("/{conv_id}/record")
async def record_message(conv_id: str, req: RecordRequest):
    """记录用户实际发出的那条回复（从5种风格中选用的）"""
    from services.conversation_service import get_conversation, add_message
    if not get_conversation(conv_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    msg = add_message(conv_id, "user", req.used_reply)
    return {"ok": True, "message": msg}


@router.post("/{conv_id}/batch-record")
async def batch_record_messages(conv_id: str, req: BatchRecordRequest):
    """批量记录截图提取的对话（角色：girl 或 me/user）"""
    from services.conversation_service import get_conversation, add_message
    if not get_conversation(conv_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    count = 0
    for m in req.messages:
        role = m.get("role", "girl")
        role = "user" if role == "me" else role
        content = (m.get("content") or "").strip()
        if content:
            add_message(conv_id, role, content)
            count += 1
    return {"ok": True, "count": count}


@router.post("/{conv_id}/summarize")
async def summarize(conv_id: str):
    """手动触发 AI 对话摘要（自动摘要每20条消息触发一次）"""
    from services.conversation_service import get_conversation
    if not get_conversation(conv_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    from services.summary_service import summarize_conversation
    result = await summarize_conversation(conv_id)
    if result is None:
        raise HTTPException(status_code=400, detail="对话记录不足（至少需要4条），无法生成摘要")
    return {"ok": True, "summary": result}


@router.get("/{conv_id}/analysis")
async def analysis(conv_id: str):
    """基于 game_master.md 框架的深度对话分析"""
    from services.summary_service import analyze_conversation
    try:
        return await analyze_conversation(conv_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"分析失败：{exc}")
