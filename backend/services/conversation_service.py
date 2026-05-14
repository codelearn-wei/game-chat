"""
conversation_service.py - 多会话管理（SQLite 持久化存储）

支持一对多聊天管理：每个女生对应一个 conversation，存储完整消息历史和 AI 摘要。
"""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

_DB_PATH = Path(__file__).parent.parent / "data" / "conversations.db"


# ─── 连接 & 初始化 ─────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init_db() -> None:
    """建表（首次启动时调用）"""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id              TEXT PRIMARY KEY,
                name            TEXT NOT NULL,
                goal            TEXT DEFAULT '恋爱',
                notes           TEXT DEFAULT '',
                context_summary TEXT DEFAULT '',
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id              TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role            TEXT NOT NULL,
                content         TEXT NOT NULL,
                timestamp       TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);
        """)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _uid() -> str:
    return str(uuid.uuid4()).replace("-", "")[:12]


# ─── 会话 CRUD ─────────────────────────────────────────────

def create_conversation(name: str, goal: str = "恋爱", notes: str = "") -> Dict[str, Any]:
    cid = _uid()
    now = _now()
    with _conn() as con:
        con.execute(
            "INSERT INTO conversations (id, name, goal, notes, context_summary, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (cid, name, goal, notes or "", "", now, now),
        )
    return get_conversation(cid)  # type: ignore[return-value]


def list_conversations() -> List[Dict[str, Any]]:
    with _conn() as con:
        rows = con.execute("""
            SELECT c.*,
                   COUNT(m.id)      AS message_count,
                   MAX(m.timestamp) AS last_message_at
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            GROUP BY c.id
            ORDER BY c.updated_at DESC
        """).fetchall()
    return [dict(r) for r in rows]


def get_conversation(cid: str) -> Optional[Dict[str, Any]]:
    with _conn() as con:
        row = con.execute("SELECT * FROM conversations WHERE id=?", (cid,)).fetchone()
        if row is None:
            return None
        conv = dict(row)
        msgs = con.execute(
            "SELECT * FROM messages WHERE conversation_id=? ORDER BY timestamp ASC",
            (cid,),
        ).fetchall()
        conv["messages"] = [dict(m) for m in msgs]
        conv["message_count"] = len(conv["messages"])
        conv["last_message_at"] = conv["messages"][-1]["timestamp"] if conv["messages"] else None
    return conv


def update_conversation(cid: str, **kwargs) -> Optional[Dict[str, Any]]:
    allowed = {"name", "goal", "notes", "context_summary"}
    fields = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not fields:
        return get_conversation(cid)
    fields["updated_at"] = _now()
    set_clause = ", ".join(f"{k}=?" for k in fields)
    values = list(fields.values()) + [cid]
    with _conn() as con:
        con.execute(f"UPDATE conversations SET {set_clause} WHERE id=?", values)  # noqa: S608
    return get_conversation(cid)


def delete_conversation(cid: str) -> bool:
    with _conn() as con:
        con.execute("DELETE FROM messages WHERE conversation_id=?", (cid,))
        cur = con.execute("DELETE FROM conversations WHERE id=?", (cid,))
        return cur.rowcount > 0


# ─── 消息 ──────────────────────────────────────────────────

def add_message(conversation_id: str, role: str, content: str) -> Dict[str, Any]:
    mid = _uid()
    now = _now()
    with _conn() as con:
        con.execute(
            "INSERT INTO messages (id, conversation_id, role, content, timestamp) VALUES (?,?,?,?,?)",
            (mid, conversation_id, role, content, now),
        )
        con.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now, conversation_id))
    return {
        "id": mid,
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "timestamp": now,
    }


def get_recent_messages(conversation_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM messages WHERE conversation_id=? ORDER BY timestamp DESC LIMIT ?",
            (conversation_id, limit),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def get_message_count(conversation_id: str) -> int:
    with _conn() as con:
        row = con.execute(
            "SELECT COUNT(*) AS cnt FROM messages WHERE conversation_id=?",
            (conversation_id,),
        ).fetchone()
    return row["cnt"] if row else 0
