"""
ocr.py — 聊天截图 OCR 路由
接收图片 → DeepSeek Vision 提取对话内容 → 返回文本
"""
from __future__ import annotations

import base64
import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from services.deepseek_client import DeepSeekClient

logger = logging.getLogger(__name__)
router = APIRouter()
_client = DeepSeekClient()

MAX_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_MIME_PREFIXES = ("image/jpeg", "image/png", "image/webp", "image/gif")


@router.post("/extract")
async def extract_screenshot(
    file: UploadFile = File(...),
    conv_id: str = Form(default=""),
):
    """
    从聊天截图中提取对话文本。

    - 接收 multipart/form-data，字段名 `file`（图片），可选 `conv_id`
    - 调用 DeepSeek Vision 提取截图中的聊天内容
    - 返回 { extracted_text: str, conv_id: str }
    """
    content = await file.read()

    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="图片过大，请上传 5MB 以内的截图")

    mime = file.content_type or "image/jpeg"
    if not any(mime.startswith(p) for p in ALLOWED_MIME_PREFIXES):
        raise HTTPException(status_code=400, detail="仅支持 JPEG / PNG / WebP 格式的图片")

    try:
        b64 = base64.b64encode(content).decode()
        extracted = await _client.extract_chat_from_image(b64, mime)
        return {"extracted_text": extracted, "conv_id": conv_id}
    except Exception as e:
        logger.error(f"OCR 提取失败: {e}")
        raise HTTPException(status_code=500, detail=f"截图识别失败：{e}")
