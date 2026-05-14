"""
practice.py - 聊天练习路由
"""
from fastapi import APIRouter, HTTPException
from models.schemas import (
    StartPracticeRequest, StartPracticeResponse,
    PracticeReplyRequest, PracticeReplyResponse,
)

router = APIRouter()


@router.post("/start", response_model=StartPracticeResponse)
async def start_practice(req: StartPracticeRequest):
    """开始一次聊天练习"""
    try:
        from services.practice_service import start_practice as _start
        return await _start(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动练习失败：{e}")


@router.post("/reply", response_model=PracticeReplyResponse)
async def practice_reply(req: PracticeReplyRequest):
    """用户发送回复，获取女生反应 + 阶段评价"""
    try:
        from services.practice_service import practice_reply as _reply
        return await _reply(req)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"回复失败：{e}")


@router.get("/girl-types")
def list_girl_types():
    """获取所有可用的女生类型"""
    from services.practice_service import list_girl_types
    return {"girl_types": list_girl_types()}


@router.get("/scenarios")
def list_scenarios():
    """获取所有可用的练习情境"""
    from services.practice_service import list_scenarios
    return {"scenarios": list_scenarios()}
