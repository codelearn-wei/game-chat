"""
ocr.py — 聊天截图 OCR 路由
流程：Baidu OCR 识别原始文字 → DeepSeek 清洗成干净对话 + 角色标注
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

from services.deepseek_client import DeepSeekClient

logger = logging.getLogger(__name__)
router = APIRouter()
_deepseek = DeepSeekClient()

BAIDU_API_KEY = os.environ.get("BAIDU_OCR_API_KEY", "V3G6boOFIr1uMhgQY50qeRzu")
BAIDU_SECRET_KEY = os.environ.get("BAIDU_OCR_SECRET_KEY", "c3ZGfYtbv7J2kBne2to44MJRgq7lxJhn")
BAIDU_TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
BAIDU_OCR_URL   = "https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic"

MAX_B64_LEN = 7 * 1024 * 1024
_token_cache: dict = {"token": "", "expires_at": 0.0}

# DeepSeek 清洗 prompt
_CLEAN_PROMPT = """以下是从聊天截图中OCR识别出的原始文字，每行是截图中一个文字块：

---
{raw}
---

请完成：
1. 删除所有时间戳（10:30、昨天、今天等）、广告、系统通知、状态栏、表情包描述等无关内容
2. 识别对话双方：用 "她" 表示对方，用 "我" 表示用户自己（通常截图中右侧气泡是自己）
3. 只返回 JSON 数组，格式：[{{"role":"girl","content":"..."}},{{"role":"me","content":"..."}}]
4. 无法区分发送者时统一标注为 "girl"
5. 不要输出任何解释，只返回 JSON 数组"""


async def _get_access_token() -> str:
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"] - 300:
        return _token_cache["token"]
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            BAIDU_TOKEN_URL,
            params={"grant_type": "client_credentials",
                    "client_id": BAIDU_API_KEY,
                    "client_secret": BAIDU_SECRET_KEY},
        )
        resp.raise_for_status()
        data = resp.json()
        if "access_token" not in data:
            raise RuntimeError(f"获取百度 token 失败: {data}")
        _token_cache["token"] = data["access_token"]
        _token_cache["expires_at"] = now + data.get("expires_in", 2592000)
    return _token_cache["token"]


async def _baidu_ocr(b64: str) -> list[str]:
    """调用百度 OCR，返回识别到的文字行列表。"""
    token = await _get_access_token()
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            BAIDU_OCR_URL,
            params={"access_token": token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            content=f"image={urllib.parse.quote_plus(b64)}".encode(),
        )
        resp.raise_for_status()
        data = resp.json()
    if "error_code" in data:
        raise RuntimeError(f"百度 OCR 错误 {data['error_code']}: {data.get('error_msg')}")
    return [item["words"] for item in data.get("words_result", [])]


async def _deepseek_clean(raw_lines: list[str]) -> list[dict]:
    """用 DeepSeek 把 OCR 原始行清洗成 [{role, content}] 对话列表。"""
    raw_text = "\n".join(raw_lines)
    prompt = _CLEAN_PROMPT.format(raw=raw_text)
    reply = await _deepseek.chat(
        [{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=2000,
    )
    # 提取 JSON 数组
    match = re.search(r'\[.*\]', reply, re.DOTALL)
    if not match:
        raise RuntimeError("DeepSeek 返回格式异常，无法解析对话")
    messages = json.loads(match.group())
    # 只保留 role + content 字段
    result = []
    for m in messages:
        role = m.get("role", "girl")
        if role not in ("girl", "me"):
            role = "girl"
        content = (m.get("content") or "").strip()
        if content:
            result.append({"role": role, "content": content})
    return result


class ExtractRequest(BaseModel):
    image_base64: str
    mime_type: str = "image/jpeg"
    conv_id: str = ""


@router.post("/extract")
async def extract_screenshot(req: ExtractRequest):
    """
    流程：Baidu OCR → DeepSeek 清洗 → 返回结构化对话

    返回：
    {
      messages: [{role: 'girl'|'me', content: str}],
      last_girl_msg: str,   // 最后一条女生的消息，用于分析
      conv_id: str
    }
    """
    if len(req.image_base64) > MAX_B64_LEN:
        raise HTTPException(status_code=413, detail="图片过大，请上传 5MB 以内的截图")

    try:
        # Step 1: 百度 OCR
        raw_lines = await _baidu_ocr(req.image_base64)
        if not raw_lines:
            return {"messages": [], "last_girl_msg": "", "conv_id": req.conv_id}

        # Step 2: DeepSeek 清洗
        messages = await _deepseek_clean(raw_lines)

        # Step 3: 找最后一条女生的消息
        last_girl_msg = ""
        for m in reversed(messages):
            if m["role"] == "girl":
                last_girl_msg = m["content"]
                break

        logger.info(f"[OCR] 识别 {len(raw_lines)} 行 → 清洗为 {len(messages)} 条对话")
        return {"messages": messages, "last_girl_msg": last_girl_msg, "conv_id": req.conv_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OCR 提取失败: {e}")
        raise HTTPException(status_code=500, detail=f"截图识别失败：{e}")

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

# ── 百度 OCR 配置（可通过环境变量覆盖）──
BAIDU_API_KEY = os.environ.get("BAIDU_OCR_API_KEY", "V3G6boOFIr1uMhgQY50qeRzu")
BAIDU_SECRET_KEY = os.environ.get("BAIDU_OCR_SECRET_KEY", "c3ZGfYtbv7J2kBne2to44MJRgq7lxJhn")
BAIDU_TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
BAIDU_OCR_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic"

# access_token 缓存（有效期 30 天，运行期内复用）
_token_cache: dict = {"token": "", "expires_at": 0.0}

MAX_B64_LEN = 7 * 1024 * 1024  # ~5MB 原图上限（base64 后约 6.7MB）


async def _get_access_token() -> str:
    """获取百度 access_token，自动缓存复用，过期前 5 分钟刷新。"""
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
    从聊天截图中提取文字。

    - 接收 JSON: { image_base64, mime_type, conv_id }
    - 调用百度 OCR 通用文字识别（每天免费 50,000 次）
    - 返回 { extracted_text: str, conv_id: str }
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
            raise RuntimeError(f"百度 OCR 错误 {data['error_code']}: {data.get('error_msg')}")

        words = [item["words"] for item in data.get("words_result", [])]
        extracted = "\n".join(words).strip()

        if not extracted:
            extracted = "未识别到文字，请换一张更清晰的截图"

        logger.info(f"[Baidu OCR] 识别 {len(words)} 行文字")
        return {"extracted_text": extracted, "conv_id": req.conv_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OCR 提取失败: {e}")
        raise HTTPException(status_code=500, detail=f"截图识别失败：{e}")
