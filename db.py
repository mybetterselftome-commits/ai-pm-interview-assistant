"""Database abstraction — SQLite (local) / PostgreSQL (production)"""
import os

DATABASE_URL = os.getenv("DATABASE_URL")
DB_PATH = os.path.join(os.path.dirname(__file__), "knowledge.db")

# ── Connection ──────────────────────────────────────────────────────
if DATABASE_URL:
    try:
        import psycopg2
        import psycopg2.extras
        USE_POSTGRES = True
    except ImportError:
        USE_POSTGRES = False
else:
    USE_POSTGRES = False

if USE_POSTGRES:

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
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS career_assets (
            id          {autoinc},
            device_id   TEXT,
            asset_type  TEXT,
            title       TEXT,
            content     TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS career_feedback (
            id          {autoinc},
            device_id   TEXT,
            module      TEXT,
            value       TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS weakness_tags (
            id              {autoinc},
            device_id       TEXT,
            tag             TEXT,
            dimension       TEXT,
            severity        INTEGER DEFAULT 1,
            hit_count       INTEGER DEFAULT 1,
            last_hit_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(device_id, tag)
        )
    """)
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS interview_sessions (
            id              {autoinc},
            device_id       TEXT,
            role            TEXT,
            mode            TEXT,
            question        TEXT,
            transcript      TEXT,
            verdict         TEXT,
            score           INTEGER,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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


# ── V3 Career Assets ────────────────────────────────────────────────
def save_career_asset(device_id, asset_type, title, content):
    conn = _conn()
    cursor = conn.execute(
        "INSERT INTO career_assets (device_id, asset_type, title, content) "
        f"VALUES ({_p}, {_p}, {_p}, {_p})",
        (device_id, asset_type, title, content),
    )
    asset_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return asset_id


def list_career_assets(device_id):
    conn = _conn()
    rows = conn.execute(
        "SELECT id, asset_type, title, content, created_at FROM career_assets "
        f"WHERE device_id = {_p} ORDER BY id DESC",
        (device_id,),
    ).fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "type": r[1],
            "title": r[2],
            "content": r[3],
            "created_at": str(r[4])[:16] if r[4] else "",
        }
        for r in rows
    ]


def delete_career_asset(device_id, asset_id):
    conn = _conn()
    conn.execute(
        f"DELETE FROM career_assets WHERE device_id = {_p} AND id = {_p}",
        (device_id, asset_id),
    )
    conn.commit()
    conn.close()


def save_feedback(device_id, module, value):
    conn = _conn()
    conn.execute(
        f"INSERT INTO career_feedback (device_id, module, value) VALUES ({_p}, {_p}, {_p})",
        (device_id, module, value),
    )
    conn.commit()
    conn.close()


def list_feedback(device_id, limit=50):
    conn = _conn()
    rows = conn.execute(
        "SELECT module, value, created_at FROM career_feedback "
        f"WHERE device_id = {_p} ORDER BY id DESC LIMIT {_p}",
        (device_id, limit),
    ).fetchall()
    conn.close()
    return [
        {"module": r[0], "value": r[1], "created_at": str(r[2])[:16] if r[2] else ""}
        for r in rows
    ]


def clear_career_data(device_id):
    conn = _conn()
    conn.execute(f"DELETE FROM career_assets WHERE device_id = {_p}", (device_id,))
    conn.execute(f"DELETE FROM career_feedback WHERE device_id = {_p}", (device_id,))
    conn.execute(f"DELETE FROM weakness_tags WHERE device_id = {_p}", (device_id,))
    conn.execute(f"DELETE FROM interview_sessions WHERE device_id = {_p}", (device_id,))
    conn.commit()
    conn.close()


# ── V3 Weakness Tags (data flywheel) ────────────────────────────────
def upsert_weakness_tag(device_id, tag, dimension, severity=1):
    """Record a weakness exposure. If tag already exists, hit_count += 1 and severity = max."""
    conn = _conn()
    if USE_POSTGRES:
        conn.execute(
            "INSERT INTO weakness_tags (device_id, tag, dimension, severity, hit_count, last_hit_at) "
            "VALUES (%s, %s, %s, %s, 1, CURRENT_TIMESTAMP) "
            "ON CONFLICT (device_id, tag) DO UPDATE SET "
            "  hit_count = weakness_tags.hit_count + 1, "
            "  severity = GREATEST(weakness_tags.severity, EXCLUDED.severity), "
            "  dimension = EXCLUDED.dimension, "
            "  last_hit_at = CURRENT_TIMESTAMP",
            (device_id, tag, dimension, severity),
        )
    else:
        conn.execute(
            "INSERT INTO weakness_tags (device_id, tag, dimension, severity, hit_count, last_hit_at) "
            "VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP) "
            "ON CONFLICT(device_id, tag) DO UPDATE SET "
            "  hit_count = hit_count + 1, "
            "  severity = MAX(severity, excluded.severity), "
            "  dimension = excluded.dimension, "
            "  last_hit_at = CURRENT_TIMESTAMP",
            (device_id, tag, dimension, severity),
        )
    conn.commit()
    conn.close()


def list_weakness_tags(device_id, limit=20):
    conn = _conn()
    rows = conn.execute(
        "SELECT tag, dimension, severity, hit_count, last_hit_at FROM weakness_tags "
        f"WHERE device_id = {_p} ORDER BY severity DESC, hit_count DESC, last_hit_at DESC LIMIT {_p}",
        (device_id, limit),
    ).fetchall()
    conn.close()
    return [
        {
            "tag": r[0],
            "dimension": r[1],
            "severity": r[2],
            "hit_count": r[3],
            "last_hit_at": str(r[4])[:16] if r[4] else "",
        }
        for r in rows
    ]


def top_weak_dimensions(device_id, top_n=3):
    """Return the top N dimensions ranked by total severity*hit_count, for adaptive question selection."""
    conn = _conn()
    rows = conn.execute(
        "SELECT dimension, SUM(severity * hit_count) AS score FROM weakness_tags "
        f"WHERE device_id = {_p} GROUP BY dimension ORDER BY score DESC LIMIT {_p}",
        (device_id, top_n),
    ).fetchall()
    conn.close()
    return [r[0] for r in rows if r[0]]


# ── V3 Interview Sessions ───────────────────────────────────────────
def save_interview_session(device_id, role, mode, question, transcript, verdict, score):
    conn = _conn()
    conn.execute(
        "INSERT INTO interview_sessions (device_id, role, mode, question, transcript, verdict, score) "
        f"VALUES ({_p}, {_p}, {_p}, {_p}, {_p}, {_p}, {_p})",
        (device_id, role, mode, question, transcript, verdict, score),
    )
    conn.commit()
    conn.close()


def list_interview_sessions(device_id, limit=20):
    conn = _conn()
    rows = conn.execute(
        "SELECT id, role, mode, question, score, created_at FROM interview_sessions "
        f"WHERE device_id = {_p} ORDER BY id DESC LIMIT {_p}",
        (device_id, limit),
    ).fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "role": r[1],
            "mode": r[2],
            "question": r[3],
            "score": r[4],
            "created_at": str(r[5])[:16] if r[5] else "",
        }
        for r in rows
    ]
