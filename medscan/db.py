import sqlite3
from datetime import datetime, timezone

import click
from flask import current_app, g
from werkzeug.security import generate_password_hash

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'doctor', 'technician')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_code TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    age INTEGER NOT NULL CHECK (age > 0),
    gender TEXT NOT NULL,
    contact TEXT,
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    modality TEXT NOT NULL,
    file_path TEXT NOT NULL,
    result_label TEXT NOT NULL,
    confidence REAL NOT NULL,
    report TEXT NOT NULL,
    uploaded_by INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(patient_id) REFERENCES patients(id),
    FOREIGN KEY(uploaded_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS activity_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    event_message TEXT NOT NULL,
    actor_id INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY(actor_id) REFERENCES users(id)
);
"""


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(_=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(SCHEMA)

    existing = db.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    if existing == 0:
        now = utc_now_iso()
        users = [
            ("admin", generate_password_hash("admin123"), "admin", now),
            ("doctor", generate_password_hash("doctor123"), "doctor", now),
            ("tech", generate_password_hash("tech123"), "technician", now),
        ]
        db.executemany(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            users,
        )
        db.execute(
            "INSERT INTO activity_logs (event_type, event_message, actor_id, created_at) VALUES (?, ?, ?, ?)",
            ("seed", "Default users provisioned", None, now),
        )
    db.commit()


def log_activity(event_type, event_message, actor_id=None):
    db = get_db()
    db.execute(
        "INSERT INTO activity_logs (event_type, event_message, actor_id, created_at) VALUES (?, ?, ?, ?)",
        (event_type, event_message, actor_id, utc_now_iso()),
    )
    db.commit()


@click.command("init-db")
def init_db_command():
    init_db()
    click.echo("Database initialized.")
