import sqlite3
from contextlib import contextmanager
from app.config import DB_PATH

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS grievances (id INTEGER PRIMARY KEY AUTOINCREMENT, submitted_text TEXT NOT NULL DEFAULT '', extracted_text TEXT NOT NULL DEFAULT '', input_type TEXT NOT NULL, filename TEXT, ocr_confidence REAL, predicted_department TEXT, top3_json TEXT NOT NULL DEFAULT '[]', confidence REAL, needs_review INTEGER NOT NULL DEFAULT 1, review_reason TEXT, original_prediction TEXT, corrected_department TEXT, final_department TEXT, tracking_token_hash TEXT, status TEXT NOT NULL DEFAULT 'pending', resolution_note TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        columns = {row[1] for row in conn.execute("PRAGMA table_info(grievances)")}
        migrations = {
            "tracking_token_hash": "TEXT",
            "status": "TEXT NOT NULL DEFAULT 'pending'",
            "resolution_note": "TEXT",
        }
        for name, declaration in migrations.items():
            if name not in columns:
                conn.execute(f"ALTER TABLE grievances ADD COLUMN {name} {declaration}")
        conn.commit()

@contextmanager
def connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def row_to_dict(row):
    import json
    item = dict(row)
    item["top3"] = json.loads(item.pop("top3_json") or "[]")
    item.pop("tracking_token_hash", None)
    item["needs_review"] = bool(item["needs_review"])
    return item
