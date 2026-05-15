"""
DeepSeek API 客户端封装
"""
from __future__ import annotations

import logging
from typing import List, Dict

import os

import httpx

logger = logging.getLogger(__name__)

# 优先读环境变量，方便生产部署；本地开发可直接在此填写备用 key
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-1e19d9bf59884dae8612fa4a46769b21")
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-chat"


class DeepSeekClient:
    def __init__(self, api_key: str = DEEPSEEK_API_KEY):
        self.api_key = api_key
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.8,
        max_tokens: int = 800,
    ) -> str:
        """调用 DeepSeek chat completion API，返回回复文本"""
        payload = {
            "model": DEFAULT_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
            try:
                resp = await client.post(
                    DEEPSEEK_API_URL,
                    headers=self._headers,
                    json=payload,
                )
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
                logger.info(f"[DeepSeek] reply({len(content)} chars): {content[:60]}…")
                return content.strip()
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"[DeepSeek] HTTP {e.response.status_code}: {e.response.text[:200]}"
                )
                raise
            except Exception as e:
                logger.error(f"[DeepSeek] error: {e}")
                raise

    async def extract_chat_from_image(
        self,
        base64_data: str,
        mime_type: str = "image/jpeg",
    ) -> str:
        """调用 DeepSeek Vision API，从聊天截图中提取对话内容"""
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_data}"
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "这是一张聊天截图。请提取截图中的所有对话内容，"
                                "按时间顺序输出，格式为「发送者: 消息内容」，每条消息占一行。"
                                "如果无法区分发送者，直接输出消息内容即可。"
                                "只提取文字消息，忽略图片、语音、表情包等非文字内容。"
                                "不要添加任何解释或前缀，直接输出对话内容。"
                            ),
                        },
                    ],
                }
            ],
            "max_tokens": 1500,
        }
        async with httpx.AsyncClient(timeout=90.0, trust_env=False) as client:
            try:
                resp = await client.post(
                    DEEPSEEK_API_URL,
                    headers=self._headers,
                    json=payload,
                )
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
                logger.info(f"[DeepSeek Vision] extracted({len(content)} chars)")
                return content.strip()
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"[DeepSeek Vision] HTTP {e.response.status_code}: {e.response.text[:200]}"
                )
                raise
            except Exception as e:
                logger.error(f"[DeepSeek Vision] error: {e}")
                raise


# 全局单例
deepseek = DeepSeekClient()
