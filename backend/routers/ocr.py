"""
ocr.py — 聊天截图 OCR 路由
图片 base64 → 百度 OCR 通用文字识别 → DeepSeek 解析对话结构
免费额度：每天 50,000 次（通用标准版）
"""
from __future__ import annotations

import json
import logging
import os
import re
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


async def _parse_conversation_ai(raw_text: str) -> dict:
    """用 DeepSeek 将原始 OCR 文本解析为结构化对话（识别谁说了什么）"""
    from services.deepseek_client import deepseek

    prompt = (
        "你是微信聊天截图OCR文本解析器，请将以下OCR原始文字解析成结构化对话。\n\n"
        "微信截图规律：\n"
        "· 第一行通常是手机状态栏时间（如 17:03），忽略\n"
        "· 第二行通常是聊天窗口名称（如 李屹坤 或 123(5)A），忽略\n"
        "· 时间分隔行（如 15:17、16:02），忽略\n"
        "· 右侧绿色气泡=我发的：OCR中直接出现消息，没有名字前缀\n"
        "· 左侧白色气泡=对方发的：OCR中先一行是对方名字，下一行是消息内容\n"
        "· 同一人连续发多条消息时，名字会在每条消息前重复出现\n\n"
        f"OCR原文：\n{raw_text}\n\n"
        "仅输出JSON，不加任何说明：\n"
        '{"girl_name":"对方名字（不确定则写她）",'
        '"messages":[{"role":"me","content":"消息"},{"role":"girl","content":"消息"}],'
        '"last_girl_message":"对方最后说的话"}'
    )

    try:
        raw = await deepseek.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=800,
        )
        try:
            result = json.loads(raw.strip())
        except json.JSONDecodeError:
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            result = json.loads(m.group(0)) if m else {}

        msgs = result.get("messages", [])
        girl_name = result.get("girl_name", "她")
        formatted = "\n".join(
            f"我: {m['content']}" if m.get("role") == "me" else f"{girl_name}: {m['content']}"
            for m in msgs
        )
        return {
            "girl_name": girl_name,
            "messages": msgs,
            "last_girl_message": result.get("last_girl_message", ""),
            "formatted_context": formatted,
        }
    except Exception as e:
        logger.warning(f"[OCR] AI对话解析失败: {e}")
        return {"girl_name": "她", "messages": [], "last_girl_message": "", "formatted_context": raw_text}


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

        # 用 AI 解析对话结构（识别谁说了什么）
        if extracted and not extracted.startswith("未识别"):
            parsed = await _parse_conversation_ai(extracted)
        else:
            parsed = {"girl_name": "她", "messages": [], "last_girl_message": "", "formatted_context": extracted}

        logger.info(f"[Baidu OCR] 识别 {len(words)} 行，解析 {len(parsed['messages'])} 条消息")
        return {
            "extracted_text": extracted,
            "conv_id": req.conv_id,
            "parsed_messages": parsed["messages"],
            "girl_name": parsed["girl_name"],
            "last_girl_message": parsed["last_girl_message"],
            "formatted_context": parsed["formatted_context"],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Baidu OCR] 提取失败: {e}")
        raise HTTPException(status_code=500, detail=f"截图识别失败：{e}")
