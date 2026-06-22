import sqlite3
from app.config.settings import DB_PATH

def get_db():
    return sqlite3.connect(DB_PATH)

def init_db():
    db = get_db()
    with open("app/db/schema.sql", "r") as f:
        db.executescript(f.read())
    db.commit()
    db.close()
