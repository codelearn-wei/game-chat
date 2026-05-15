"""
ocr.py — 聊天截图 OCR 路由
图片 base64 → 百度 OCR 通用文字识别 → 返回文本
免费额度：每天 50,000 次（通用标准版）
"""
from __future__ import annotations

import logging
import os
import time
import urllib.parse

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

# ── 百度 OCR 配置（可通过 Render 环境变量覆盖）──
BAIDU_API_KEY = os.environ.get("BAIDU_OCR_API_KEY", "V3G6boOFIr1uMhgQY50qeRzu")
BAIDU_SECRET_KEY = os.environ.get("BAIDU_OCR_SECRET_KEY", "c3ZGfYtbv7J2kBne2to44MJRgq7lxJhn")
BAIDU_TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
BAIDU_OCR_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic"

# access_token 内存缓存（有效期 30 天，进程内复用）
_token_cache: dict = {"token": "", "expires_at": 0.0}

# base64 编码后比原图大约 33%，5MB 原图 ≈ 6.7MB base64
MAX_B64_LEN = 7 * 1024 * 1024


async def _get_access_token() -> str:
    """获取百度 access_token，自动缓存，过期前 5 分钟刷新。"""
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"] - 300:
        return _token_cache["token"]

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            BAIDU_TOKEN_URL,
            params={
                "grant_type": "client_credentials",
                "client_id": BAIDU_API_KEY,
                "client_secret": BAIDU_SECRET_KEY,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if "access_token" not in data:
            raise RuntimeError(f"获取百度 token 失败: {data}")
        _token_cache["token"] = data["access_token"]
        _token_cache["expires_at"] = now + data.get("expires_in", 2592000)
        logger.info("[Baidu OCR] access_token 已刷新")
        return _token_cache["token"]


class ExtractRequest(BaseModel):
    image_base64: str   # 纯 base64 字符串，不含 data:xxx; 前缀
    mime_type: str = "image/jpeg"
    conv_id: str = ""


@router.post("/extract")
async def extract_screenshot(req: ExtractRequest):
    """
    从聊天截图中提取文字（百度 OCR 通用标准版）。

    请求体: { image_base64: str, mime_type: str, conv_id: str }
    响应体: { extracted_text: str, conv_id: str }
    """
    if len(req.image_base64) > MAX_B64_LEN:
        raise HTTPException(status_code=413, detail="图片过大，请上传 5MB 以内的截图")

    try:
        token = await _get_access_token()
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                BAIDU_OCR_URL,
                params={"access_token": token},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                content=f"image={urllib.parse.quote_plus(req.image_base64)}".encode(),
            )
            resp.raise_for_status()
            data = resp.json()

        if "error_code" in data:
            raise RuntimeError(
                f"百度 OCR 错误 {data['error_code']}: {data.get('error_msg')}"
            )

        words = [item["words"] for item in data.get("words_result", [])]
        extracted = "\n".join(words).strip()

        if not extracted:
            extracted = "未识别到文字，请换一张更清晰的截图"

        logger.info(f"[Baidu OCR] 识别 {len(words)} 行")
        return {"extracted_text": extracted, "conv_id": req.conv_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Baidu OCR] 提取失败: {e}")
        raise HTTPException(status_code=500, detail=f"截图识别失败：{e}")
