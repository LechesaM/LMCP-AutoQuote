CREATE TABLE IF NOT EXISTS tenders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hash TEXT UNIQUE,
    title TEXT,
    reference TEXT,
    closing_date TEXT,
    source TEXT,
    raw TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
