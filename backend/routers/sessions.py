from fastapi import APIRouter, HTTPException
from models.schemas import (
    Session, CreateSessionRequest, UpdateSessionSkillsRequest,
    SessionListResponse,
)
from services.chat_service import chat_service

router = APIRouter()


@router.get("", response_model=SessionListResponse)
def list_sessions():
    """获取会话列表（按更新时间倒序）"""
    items = chat_service.list_sessions()
    return SessionListResponse(sessions=items, total=len(items))


@router.post("", response_model=Session)
def create_session(req: CreateSessionRequest):
    """新建对话会话"""
    return chat_service.create_session(req)


@router.get("/{session_id}", response_model=Session)
def get_session(session_id: str):
    session = chat_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session


@router.delete("/{session_id}")
def delete_session(session_id: str):
    if not chat_service.delete_session(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"message": "会话已删除"}


@router.put("/{session_id}/skills", response_model=Session)
def update_skills(session_id: str, req: UpdateSessionSkillsRequest):
    """更新会话关联的技能"""
    session = chat_service.update_session_skills(session_id, req.skill_ids)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session


@router.delete("/{session_id}/messages")
def clear_messages(session_id: str):
    """清空会话消息记录"""
    session = chat_service.clear_session_messages(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"message": "消息已清空"}
