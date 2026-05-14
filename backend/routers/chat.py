from fastapi import APIRouter, HTTPException
from models.schemas import SendMessageRequest, SendMessageResponse
from services.chat_service import chat_service

router = APIRouter()


@router.post("/{session_id}/send", response_model=SendMessageResponse)
async def send_message(session_id: str, req: SendMessageRequest):
    """发送 A 的消息，获取 B 的 AI 回复"""
    try:
        return await chat_service.send_message(session_id, req.content)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 回复失败：{e}")
