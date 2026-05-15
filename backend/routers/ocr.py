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
    轻量预处理：只做最基础的清洗，把判断权交给 AI。
    只丢弃：状态栏顶行 / 纯时间戳。
    其余全部保留，按位置软分类为 me / other / ?（居中不确定）。
    去掉原来的全幅宽度过滤——那个阈值会把女生的长消息也错误丢掉。
    """
    if not words_result:
        return []

    max_right = max(
        (item["location"]["left"] + item["location"]["width"]
         for item in words_result if "location" in item),
        default=1,
    )

    result = []
    for item in words_result:
        if "location" not in item:
            continue
        loc = item["location"]
        text = item["words"].strip()
        left, top, width = loc["left"], loc["top"], loc["width"]
        right_edge = left + width

        if not text:
            continue
        # 仅丢弃手机状态栏（截图最顶部）
        if top < 100:
            continue
        # 仅丢弃纯时间戳行
        if _TS_PAT.match(text) and len(text) < 25:
            continue

        # ── 软分类（AI 会做最终判断，这里只是辅助）──
        # WeChat 右气泡：文字右边界贴近屏幕右侧
        if right_edge > max_right * 0.85:
            side = "me"
        # WeChat 左气泡：文字左边界贴近头像右侧（屏幕左 ~20%）
        elif left < max_right * 0.22:
            side = "other"
        else:
            # 居中：可能是长气泡的延伸、背景指导文字、系统弹窗
            # 不丢弃，交给 AI 根据上下文判断
            side = "?"

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
        if it["side"] == "me":
            tag = "[我]"
        elif it["side"] == "other":
            tag = "[她]"
        else:
            tag = "[?]"
        lines.append(f"{tag} {it['text']}")
    annotated = "\n".join(lines)

    prompt = (
        "你是微信聊天截图解析专家。以下是对截图做 OCR + 位置分析后的结果，"
        "每行文字已按屏幕位置做了初步标注：\n"
        "  [我]  = 屏幕右侧气泡，确认是我发的\n"
        "  [她]  = 屏幕左侧气泡，确认是对方发的\n"
        "  [?]   = 位置居中，初步判断不确定（可能是：长气泡、背景指导文字、弹窗通知）\n\n"
        "你的任务：\n"
        "1. 阅读所有行，识别真实聊天消息，过滤干扰内容\n"
        "2. 对 [?] 行，结合上下文判断是否是真实聊天（如与前后消息语义连贯 → 归为 me 或 girl）\n"
        "3. 以下 [?] 必须丢弃：工具性词组（如「不附和」「话题加油站」「1 破冰」）、"
        "广告文案、与聊天无关的句子\n"
        "4. [她] 中极短词组（1~6字）夹在消息中间 → 是名字标签，丢弃\n"
        "5. 「好的呀」「嗯嗯」「哈哈」「好啊」等短回应 → 真实聊天，保留\n"
        "6. 同一人连续发的多条消息，每条单独列为一个 message\n\n"
        "last_girl_message：截图中对方最后说的那句话（role=girl 的最后一条）\n\n"
        f"OCR 结果（从上到下）：\n{annotated}\n\n"
        "只输出 JSON，不加 markdown 代码块，不加任何说明：\n"
        '{"girl_name":"对方名字（不确定则写她）",'
        '"messages":[{"role":"me","content":"..."},{"role":"girl","content":"..."}],'
        '"last_girl_message":"..."}'
    )

    try:
        raw = await deepseek.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1200,
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
