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
# 标准含位置版（500次/天免费）——必须用位置版才能区分左右气泡
BAIDU_OCR_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/general"

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


# 时间戳行正则（过滤用）
_TS_PAT = re.compile(
    r'^(\d{1,2}:\d{2}(:\d{2})?'
    r'|昨天\s*\d{1,2}:\d{2}'
    r'|今天\s*\d{1,2}:\d{2}'
    r'|星期[一二三四五六日]\s*\d{1,2}:\d{2}'
    r'|\d{4}[/-]\d{1,2}[/-]\d{1,2}'
    r')$'
)


def _preprocess_ocr_words(words_result: list) -> list:
    """
    位置感知预处理（需要 general 含位置版 OCR）：
    · 过滤手机状态栏（顶部 100px 以内）
    · 过滤时间戳行
    · 过滤全宽文字块（背景文章/通知/分隔符，超图宽 68%）
    · 按 left 坐标判断左侧(other)/右侧(me)气泡
    返回 [{"text": str, "top": int, "side": "me"|"other"}, ...]
    """
    if not words_result:
        return []

    # 所有文字块右边界最大值 ≈ 图片内容宽度
    max_right = max(
        (item["location"]["left"] + item["location"]["width"]
         for item in words_result if "location" in item),
        default=1,
    )

    # WeChat 右侧绿色气泡起始位置通常超过图宽 45%
    mid = max_right * 0.45

    result = []
    for item in words_result:
        if "location" not in item:
            continue
        loc = item["location"]
        text = item["words"].strip()
        left, top, width = loc["left"], loc["top"], loc["width"]

        if not text:
            continue
        # 过滤手机状态栏（截图顶部约 100px）
        if top < 100:
            continue
        # 过滤纯时间戳行
        if _TS_PAT.match(text) and len(text) < 25:
            continue
        # 过滤全幅文字（背景文章/标题/系统消息）
        if width > max_right * 0.68:
            continue

        side = "me" if left > mid else "other"
        result.append({"text": text, "top": top, "side": side})

    return result


async def _parse_conversation_ai(chat_items: list) -> dict:
    """
    用 DeepSeek 将位置分类后的聊天行解析为结构化对话。
    chat_items: [{"text", "top", "side": "me"|"other"}, ...]
    """
    from services.deepseek_client import deepseek

    if not chat_items:
        return {"girl_name": "她", "messages": [], "last_girl_message": "", "formatted_context": ""}

    # 按 top 排序确保时序正确，构建带方向标签的文本
    chat_items_sorted = sorted(chat_items, key=lambda x: x["top"])
    lines = []
    for it in chat_items_sorted:
        tag = "[我]" if it["side"] == "me" else "[左侧]"
        lines.append(f"{tag} {it['text']}")
    annotated = "\n".join(lines)

    prompt = (
        "你是微信聊天对话解析器。以下文字来自聊天截图OCR，每行已标注来源方向：\n"
        "· [我] = 右侧绿色气泡，这是我发的\n"
        "· [左侧] = 左侧区域，可能是「对方名字标签」或「对方发的消息」\n\n"
        "解析规则：\n"
        "1. [左侧] 若内容极短（1~8个字符）且在其他[左侧]消息附近，通常是对方的名字标签，跳过\n"
        "2. [左侧] 的实质内容即对方说的话\n"
        "3. [我] 就是我说的话\n"
        "4. 忽略非对话内容（提示语、通话记录等）\n\n"
        f"待解析：\n{annotated}\n\n"
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
        return {"girl_name": "她", "messages": [], "last_girl_message": "", "formatted_context": ""}


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

        words_result = data.get("words_result", [])

        # ── 位置感知预处理：过滤背景文字，区分左右气泡 ──
        chat_items = _preprocess_ocr_words(words_result)

        # 保留原始文本用于日志 / 降级展示
        extracted = "\n".join(it["text"] for it in chat_items).strip()
        if not extracted:
            extracted = "未识别到文字，请换一张更清晰的截图"

        # ── AI 解析对话结构 ──
        if chat_items:
            parsed = await _parse_conversation_ai(chat_items)
        else:
            parsed = {"girl_name": "她", "messages": [], "last_girl_message": "", "formatted_context": extracted}

        logger.info(
            f"[Baidu OCR] 原始{len(words_result)}行 → 过滤后{len(chat_items)}行"
            f" → 解析{len(parsed['messages'])}条消息"
        )
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
