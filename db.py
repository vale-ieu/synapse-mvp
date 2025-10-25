# db.py
import json
import sqlite3
from pathlib import Path

DB_PATH = Path("app.db")

def _connect():
    return sqlite3.connect(DB_PATH)

def _init_db():
    """Crea le tabelle se non esistono e aggiunge colonne opzionali in modo sicuro."""
    conn = _connect()
    c = conn.cursor()

    # 1) Tabelle base
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            topic TEXT NOT NULL,
            level TEXT,
            goals TEXT,
            plan_json TEXT NOT NULL,
            public_id TEXT,      -- opzionale: link pubblico
            extra TEXT,          -- opzionale: meta varie (JSON)
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS progresses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL,
            step_idx INTEGER NOT NULL,
            status TEXT NOT NULL,
            UNIQUE(plan_id, step_idx),
            FOREIGN KEY(plan_id) REFERENCES plans(id)
        )
    """)

    # 2) Aggiunta colonne opzionali solo se mancano (robusta)
    c.execute("PRAGMA table_info(plans)")
    cols = {row[1] for row in c.fetchall()}
    if "public_id" not in cols:
        try:
            c.execute("ALTER TABLE plans ADD COLUMN public_id TEXT")
        except sqlite3.OperationalError:
            pass
    if "extra" not in cols:
        try:
            c.execute("ALTER TABLE plans ADD COLUMN extra TEXT")
        except sqlite3.OperationalError:
            pass

    # 3) Indici utili
    try:
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_plans_public_id ON plans(public_id)")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("CREATE INDEX IF NOT EXISTS idx_plans_user_id ON plans(user_id)")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

# Inizializza subito all’import
_init_db()


# ========================= USERS =========================
def upsert_user(email: str):
    """Crea l'utente se non esiste e lo ritorna."""
    conn = _connect(); c = conn.cursor()
    c.execute("SELECT id, email FROM users WHERE email=?", (email,))
    row = c.fetchone()
    if not row:
        c.execute("INSERT INTO users(email) VALUES(?)", (email,))
        conn.commit()
        c.execute("SELECT id, email FROM users WHERE email=?", (email,))
        row = c.fetchone()
    conn.close()
    return {"id": row[0], "email": row[1]}


# ========================= PLANS =========================
def save_plan(user_id: int, topic: str, level: str, goals: str, plan_json_obj: dict):
    """Salva un nuovo piano e ritorna il record completo."""
    conn = _connect(); c = conn.cursor()
    plan_json = json.dumps(plan_json_obj)
    c.execute(
        "INSERT INTO plans(user_id, topic, level, goals, plan_json) VALUES (?, ?, ?, ?, ?)",
        (user_id, topic, level, goals or "", plan_json)
    )
    conn.commit()
    plan_id = c.lastrowid
    c.execute("SELECT id, user_id, topic, level, goals, plan_json FROM plans WHERE id=?", (plan_id,))
    row = c.fetchone()
    conn.close()
    return {
        "id": row[0], "user_id": row[1], "topic": row[2], "level": row[3],
        "goals": row[4], "plan_json": json.loads(row[5]) if row[5] else {}
    }

def list_plans(user_id: int | None):
    """Lista piani per utente. Se user_id è None ritorna [] (sicuro per view pubbliche)."""
    if user_id is None:
        return []
    conn = _connect(); c = conn.cursor()
    c.execute("SELECT id, user_id, topic, level, goals, plan_json FROM plans WHERE user_id=? ORDER BY id DESC", (user_id,))
    rows = c.fetchall()
    conn.close()
    plans = []
    for r in rows:
        try:
            pj = json.loads(r[5]) if isinstance(r[5], str) else (r[5] or {})
        except Exception:
            pj = {}
        plans.append({
            "id": r[0], "user_id": r[1], "topic": r[2], "level": r[3],
            "goals": r[4], "plan_json": pj
        })
    return plans

def update_plan_topic(plan_id: int, new_topic: str):
    conn = _connect(); c = conn.cursor()
    c.execute("UPDATE plans SET topic=? WHERE id=?", (new_topic, plan_id))
    conn.commit(); conn.close()

def delete_plan(plan_id: int):
    conn = _connect(); c = conn.cursor()
    c.execute("DELETE FROM progresses WHERE plan_id=?", (plan_id,))
    c.execute("DELETE FROM plans WHERE id=?", (plan_id,))
    conn.commit(); conn.close()

def update_plan_json(plan_id: int, plan_json_obj: dict):
    """Aggiorna il JSON del piano (sovrascrive)."""
    conn = _connect(); c = conn.cursor()
    c.execute("UPDATE plans SET plan_json=? WHERE id=?", (json.dumps(plan_json_obj), plan_id))
    conn.commit(); conn.close()


# ========================= PROGRESS =========================
def get_progress_map(plan_id: int) -> dict[int, str]:
    """Ritorna {step_idx: status} per un plan."""
    conn = _connect(); c = conn.cursor()
    c.execute("SELECT step_idx, status FROM progresses WHERE plan_id=?", (plan_id,))
    rows = c.fetchall(); conn.close()
    return {int(r[0]): r[1] for r in rows}

def set_progress(plan_id: int, step_idx: int, status: str):
    """Salva o aggiorna lo stato di uno step (to-do / doing / done)."""
    conn = _connect(); c = conn.cursor()
    c.execute("""
        INSERT INTO progresses(plan_id, step_idx, status)
        VALUES (?, ?, ?)
        ON CONFLICT(plan_id, step_idx) DO UPDATE SET status=excluded.status
    """, (plan_id, step_idx, status))
    conn.commit(); conn.close()
