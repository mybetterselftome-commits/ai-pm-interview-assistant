"""Database abstraction — SQLite (local) / PostgreSQL (production)"""
import os

DATABASE_URL = os.getenv("DATABASE_URL")
DB_PATH = os.path.join(os.path.dirname(__file__), "knowledge.db")


# ── Connection ──────────────────────────────────────────────────────
if DATABASE_URL:
    import psycopg2
    import psycopg2.extras

    def _conn():
        return psycopg2.connect(DATABASE_URL)

    _p = "%s"
    _min = lambda a, b: f"LEAST({a}, {b})"

    def _insert_user(conn, device_id):
        conn.execute(
            "INSERT INTO users (device_id) VALUES (%s) "
            "ON CONFLICT (device_id) DO UPDATE SET last_visit = CURRENT_TIMESTAMP",
            (device_id,),
        )

    def _upsert_knowledge(conn, device_id, topic):
        conn.execute(
            "INSERT INTO knowledge_state (device_id, topic, familiarity, question_count, last_asked) "
            "VALUES (%s, %s, 1, 1, CURRENT_TIMESTAMP) "
            "ON CONFLICT (device_id, topic) DO UPDATE SET "
            "  question_count = knowledge_state.question_count + 1, "
            f"  familiarity = {_min('knowledge_state.familiarity + 1', '5')}, "
            "  last_asked = CURRENT_TIMESTAMP",
            (device_id, topic),
        )

else:
    import sqlite3

    def _conn():
        return sqlite3.connect(DB_PATH)

    _p = "?"

    def _insert_user(conn, device_id):
        conn.execute("INSERT OR IGNORE INTO users (device_id) VALUES (?)", (device_id,))
        conn.execute("UPDATE users SET last_visit = CURRENT_TIMESTAMP WHERE device_id = ?", (device_id,))

    def _upsert_knowledge(conn, device_id, topic):
        conn.execute(
            "INSERT INTO knowledge_state (device_id, topic, familiarity, question_count, last_asked) "
            "VALUES (?, ?, 1, 1, CURRENT_TIMESTAMP) "
            "ON CONFLICT(device_id, topic) DO UPDATE SET "
            "  question_count = question_count + 1, "
            "  familiarity = MIN(5, familiarity + 1), "
            "  last_asked = CURRENT_TIMESTAMP",
            (device_id, topic),
        )


# ── Schema ──────────────────────────────────────────────────────────
def init_db():
    conn = _conn()
    autoinc = "SERIAL" if DATABASE_URL else "INTEGER PRIMARY KEY AUTOINCREMENT"
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS users (
            device_id   TEXT PRIMARY KEY,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_visit  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS chat_history (
            id          {autoinc},
            device_id   TEXT,
            role        TEXT,
            content     TEXT,
            topics      TEXT,
            msg_type    TEXT DEFAULT 'qa',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS knowledge_state (
            id              {autoinc},
            device_id       TEXT,
            topic           TEXT,
            familiarity     INTEGER DEFAULT 1,
            question_count  INTEGER DEFAULT 1,
            last_asked      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(device_id, topic)
        )
    """)
    conn.commit()
    conn.close()


# ── User ────────────────────────────────────────────────────────────
def get_or_create_user(device_id):
    conn = _conn()
    _insert_user(conn, device_id)
    conn.commit()
    conn.close()


# ── Chat ────────────────────────────────────────────────────────────
def save_chat(device_id, role, content, topics=None):
    conn = _conn()
    topics_str = ",".join(topics) if topics else ""
    conn.execute(
        f"INSERT INTO chat_history (device_id, role, content, topics) VALUES ({_p}, {_p}, {_p}, {_p})",
        (device_id, role, content, topics_str),
    )
    conn.commit()
    conn.close()


# ── Knowledge ───────────────────────────────────────────────────────
def update_knowledge(device_id, topics):
    conn = _conn()
    for topic in topics:
        _upsert_knowledge(conn, device_id, topic)
    conn.commit()
    conn.close()


def get_user_profile(device_id):
    conn = _conn()

    rows = conn.execute(
        "SELECT topic, familiarity, question_count FROM knowledge_state "
        f"WHERE device_id = {_p} ORDER BY last_asked DESC",
        (device_id,),
    ).fetchall()
    knowledge = {r[0]: {"familiarity": r[1], "count": r[2]} for r in rows}

    recent = conn.execute(
        "SELECT content, topics FROM chat_history "
        f"WHERE device_id = {_p} AND role = 'user' ORDER BY created_at DESC LIMIT 5",
        (device_id,),
    ).fetchall()

    total_q = conn.execute(
        f"SELECT COUNT(*) FROM chat_history WHERE device_id = {_p} AND role = 'user'",
        (device_id,),
    ).fetchone()[0]

    conn.close()
    return {"knowledge": knowledge, "recent_questions": [r[0] for r in recent], "total_questions": total_q}


def get_relevant_history(device_id, topics, limit=3):
    """Find relevant past Q&A by keyword matching on topics."""
    if not topics:
        return []

    conn = _conn()
    relevant = []
    for topic in topics:
        rows = conn.execute(
            "SELECT role, content FROM chat_history "
            f"WHERE device_id = {_p} AND topics LIKE {_p} ORDER BY created_at DESC LIMIT 3",
            (device_id, f"%{topic}%"),
        ).fetchall()
        for row in rows:
            entry = (row[0], row[1])
            if entry not in relevant:
                relevant.append(entry)
    conn.close()
    return relevant[:limit]


def clear_user_data(device_id):
    conn = _conn()
    conn.execute(f"DELETE FROM chat_history WHERE device_id = {_p}", (device_id,))
    conn.execute(f"DELETE FROM knowledge_state WHERE device_id = {_p}", (device_id,))
    conn.commit()
    conn.close()


def restore_messages(device_id):
    """Load chat history for a returning user."""
    conn = _conn()
    rows = conn.execute(
        "SELECT role, content FROM chat_history "
        f"WHERE device_id = {_p} ORDER BY id ASC",
        (device_id,),
    ).fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in rows]
