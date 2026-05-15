"""
ocr.py — 聊天截图 OCR 路由
接收 JSON base64 图片 → DeepSeek Vision 提取对话内容 → 返回文本
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.deepseek_client import DeepSeekClient

logger = logging.getLogger(__name__)
router = APIRouter()
_client = DeepSeekClient()

# base64 编码后比原始数据大约 33%，5MB 原图 ≈ 6.7MB base64
MAX_B64_LEN = 7 * 1024 * 1024  # ~5MB 原图上限


class ExtractRequest(BaseModel):
    image_base64: str        # 纯 base64 字符串，不含 data:xxx; 前缀
    mime_type: str = "image/jpeg"
    conv_id: str = ""


@router.post("/extract")
async def extract_screenshot(req: ExtractRequest):
    """
    从聊天截图中提取对话文本。

    - 接收 JSON: { image_base64, mime_type, conv_id }
    - 调用 DeepSeek Vision 提取截图中的聊天内容
    - 返回 { extracted_text: str, conv_id: str }
    """
    if len(req.image_base64) > MAX_B64_LEN:
        raise HTTPException(status_code=413, detail="图片过大，请上传 5MB 以内的截图")

    allowed = ("image/jpeg", "image/png", "image/webp", "image/gif")
    if not any(req.mime_type.startswith(p) for p in allowed):
        raise HTTPException(status_code=400, detail="仅支持 JPEG / PNG / WebP 格式的图片")

    try:
        extracted = await _client.extract_chat_from_image(req.image_base64, req.mime_type)
        return {"extracted_text": extracted, "conv_id": req.conv_id}
    except Exception as e:
        logger.error(f"OCR 提取失败: {e}")
        raise HTTPException(status_code=500, detail=f"截图识别失败：{e}")
