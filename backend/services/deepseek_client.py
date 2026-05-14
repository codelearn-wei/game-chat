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


# 全局单例
deepseek = DeepSeekClient()
