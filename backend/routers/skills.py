import uuid
from fastapi import APIRouter, HTTPException
from models.schemas import Skill, CreateSkillRequest, SkillsListResponse
from services.chat_service import chat_service

router = APIRouter()


@router.get("", response_model=SkillsListResponse)
def get_skills():
    """获取全部技能列表"""
    skills = chat_service.get_all_skills()
    return SkillsListResponse(skills=skills, total=len(skills))


@router.post("", response_model=Skill)
def create_skill(req: CreateSkillRequest):
    """新建技能"""
    skill = Skill(skill_id=str(uuid.uuid4()).replace("-", "")[:8], **req.model_dump())
    return chat_service.add_skill(skill)


@router.get("/reset", response_model=SkillsListResponse)
def reset_skills():
    """重置为默认技能"""
    skills = chat_service.reset_skills()
    return SkillsListResponse(skills=skills, total=len(skills))


@router.get("/{skill_id}", response_model=Skill)
def get_skill(skill_id: str):
    skill = chat_service.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")
    return skill


@router.put("/{skill_id}", response_model=Skill)
def update_skill(skill_id: str, req: CreateSkillRequest):
    skill = Skill(skill_id=skill_id, **req.model_dump())
    updated = chat_service.update_skill(skill_id, skill)
    if not updated:
        raise HTTPException(status_code=404, detail="技能不存在")
    return updated


@router.delete("/{skill_id}")
def delete_skill(skill_id: str):
    if not chat_service.delete_skill(skill_id):
        raise HTTPException(status_code=404, detail="技能不存在")
    return {"message": "技能已删除"}
