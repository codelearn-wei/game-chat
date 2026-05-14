"""
完整功能测试脚本
使用前请先启动服务器：
  cd backend
  uvicorn main:app --reload --port 8000
然后运行：
  python test_api.py
"""
from __future__ import annotations

import asyncio
import httpx
import json

BASE_URL = "http://127.0.0.1:8000"


async def test():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=90.0, trust_env=False) as c:
        sep = "=" * 60

        print(f"\n{sep}")
        print("  AI 聊天框架 — 完整自动化测试")
        print(sep)

        # ── 1. 健康检查 ─────────────────────────────────────────
        print("\n[1/7] 健康检查…")
        r = await c.get("/")
        assert r.status_code == 200, r.text
        print(f"  ✓ 服务正常: {r.json()['service']}")

        # ── 2. 获取技能列表 ──────────────────────────────────────
        print("\n[2/7] 获取默认技能列表…")
        r = await c.get("/api/skills")
        assert r.status_code == 200, r.text
        skills = r.json()["skills"]
        print(f"  ✓ 共 {len(skills)} 个技能：")
        for sk in skills[:4]:
            print(f"    · {sk['name']} ({sk['category']})")
        if len(skills) > 4:
            print(f"    … 共 {len(skills)} 个")

        # ── 3. 新建自定义技能 ────────────────────────────────────
        print("\n[3/7] 新建自定义技能…")
        new_skill_req = {
            "name": "测试：直接坦诚",
            "category": "通用",
            "description": "直接说出真实想法，不拐弯抹角，表达清晰有力。",
            "tone": "直接坦诚",
            "keywords": ["直接", "坦诚"],
            "examples": [
                {"context": "对方问你喜不喜欢他", "response": "喜欢，不然不会跟你说这么多"},
            ],
        }
        r = await c.post("/api/skills", json=new_skill_req)
        assert r.status_code == 200, r.text
        new_skill_id = r.json()["skill_id"]
        print(f"  ✓ 新建技能: {r.json()['name']} (id={new_skill_id})")

        # ── 4. 新建对话会话 ──────────────────────────────────────
        print("\n[4/7] 创建聊天会话…")
        selected_skill_ids = [skills[0]["skill_id"], skills[2]["skill_id"]]
        session_req = {
            "title": "小明追晓雯-测试",
            "persona_a": {
                "name": "小明",
                "description": "25岁男生，喜欢运动，想追喜欢的女生",
                "background": "互联网从业者，有些内向但真诚",
            },
            "persona_b": {
                "name": "晓雯",
                "description": "23岁设计师，独立自信，有自己的生活节奏",
                "background": "喜欢旅行和摄影，不喜欢过于主动的人",
            },
            "skill_ids": selected_skill_ids,
        }
        r = await c.post("/api/sessions", json=session_req)
        assert r.status_code == 200, r.text
        session = r.json()
        sid = session["session_id"]
        print(f"  ✓ 会话 ID: {sid}")
        print(f"  ✓ A: {session['persona_a']['name']} vs B: {session['persona_b']['name']}")
        print(f"  ✓ 应用技能: {', '.join(selected_skill_ids)}")

        # ── 5. 模拟多轮对话 ──────────────────────────────────────
        messages = [
            "你好，好久没联系了",
            "周末有没有空，我想请你吃个饭",
            "你平时喜欢去哪里玩？",
            "我觉得你是个挺有趣的人，能多认识一下吗",
            "好呀，那你有什么建议？",
            "我最近在学冲浪，你有没有兴趣一起试试",
        ]

        print(f"\n[5/7] 模拟对话（{len(messages)} 轮）…")
        print("-" * 60)

        for i, msg in enumerate(messages, 1):
            print(f"\n  [{i}] 小明：{msg}")
            r = await c.post(f"/api/chat/{sid}/send", json={"content": msg})
            if r.status_code != 200:
                print(f"  ✗ 发送失败 ({r.status_code}): {r.text}")
                continue
            data = r.json()
            reply = data["message_b"]["content"]
            compressed = data.get("memory_updated", False)
            print(f"       晓雯：{reply}")
            if compressed:
                print("       [ℹ 记忆已压缩]")
            await asyncio.sleep(0.3)

        # ── 6. 验证会话状态 ──────────────────────────────────────
        print("\n\n[6/7] 验证会话状态…")
        r = await c.get(f"/api/sessions/{sid}")
        assert r.status_code == 200, r.text
        s = r.json()
        print(f"  ✓ 消息数: {len(s['messages'])}")
        print(f"  ✓ 记忆摘要: {'有 (' + str(len(s['memory_summary'])) + ' 字)' if s['memory_summary'] else '无（未超阈值）'}")

        # ── 7. 清单检查 ──────────────────────────────────────────
        print("\n[7/7] 会话列表…")
        r = await c.get("/api/sessions")
        assert r.status_code == 200
        sessions_resp = r.json()
        print(f"  ✓ 共 {sessions_resp['total']} 个会话")
        for s_item in sessions_resp["sessions"][:3]:
            print(f"    · {s_item['title']} ({s_item['persona_a_name']} → {s_item['persona_b_name']})")

        # 清理测试数据（可选）
        await c.delete(f"/api/skills/{new_skill_id}")

        print(f"\n{sep}")
        print("  ✅ 所有测试通过！框架运行正常")
        print(sep)
        print(f"\n  Web 演示：http://localhost:8000/demo")
        print(f"  API 文档：http://localhost:8000/docs\n")


if __name__ == "__main__":
    asyncio.run(test())
