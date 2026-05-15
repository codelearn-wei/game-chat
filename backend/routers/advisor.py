"""
advisor.py - 回复顾问路由
"""
from fastapi import APIRouter, HTTPException
from models.schemas import AnalyzeRequest, AnalyzeResponse, FeedbackRequest, SkillTriggerRequest

router = APIRouter()


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    """分析女方消息，结合会话历史，生成 5 种风格回复建议 + 导师解读"""
    try:
        from services.advisor_service import analyze_message
        return await analyze_message(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析失败：{e}")


@router.post("/feedback", response_model=AnalyzeResponse)
async def feedback(req: FeedbackRequest):
    """对回复建议不满意，提供反馈，重新生成优化版建议"""
    try:
        from services.advisor_service import feedback_regenerate
        return await feedback_regenerate(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重新生成失败：{e}")


@router.post("/skill-trigger", response_model=AnalyzeResponse)
async def skill_trigger(req: SkillTriggerRequest):
    """使用指定 Game 技能生成专属话术 + 技能原理深度解析（授人以渔）"""
    try:
        from services.advisor_service import skill_trigger_analyze
        return await skill_trigger_analyze(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"技能分析失败：{e}")
