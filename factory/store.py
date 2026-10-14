"""Local durable scheduler/outbox store. Never place this SQLite database on Modal Volume."""
import contextlib
import json
import sqlite3
import time
from pathlib import Path

DB = Path("/srv/kepler/state/factory.sqlite3")


@contextlib.contextmanager
def connect(path=DB):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=30, isolation_level=None)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=FULL")
        con.executescript("""
          CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, payload TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'ready',
            attempts INTEGER NOT NULL DEFAULT 0, next_at REAL NOT NULL DEFAULT 0,
            heartbeat REAL, started REAL, ended REAL, error TEXT, exit_code INTEGER,
            token TEXT, cost_usd REAL NOT NULL DEFAULT 0);
          CREATE TABLE IF NOT EXISTS outbox (
            id TEXT PRIMARY KEY, text TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0, next_at REAL NOT NULL DEFAULT 0,
            message_id TEXT, error TEXT, updated REAL NOT NULL);
          CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS events (
            seq INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, kind TEXT NOT NULL, detail TEXT NOT NULL);
        """)
        yield con
    finally:
        con.close()


@contextlib.contextmanager
def transaction(con):
    con.execute("BEGIN IMMEDIATE")
    try:
        yield
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise


def event(con, kind, detail):
    con.execute("INSERT INTO events(ts,kind,detail) VALUES(?,?,?)",
                (time.time(), kind, json.dumps(detail, ensure_ascii=False, allow_nan=False)))


def notify(con, identity, text):
    con.execute("INSERT OR IGNORE INTO outbox(id,text,updated) VALUES(?,?,?)", (identity, text[:4000], time.time()))


def add_job(con, identity, payload):
    encoded = json.dumps(payload, sort_keys=True, allow_nan=False)
    old = con.execute("SELECT payload FROM jobs WHERE id=?", (identity,)).fetchone()
    if old and old[0] != encoded:
        raise ValueError("iş kimliği farklı içerikle kullanıldı")
    con.execute("INSERT OR IGNORE INTO jobs(id,payload) VALUES(?,?)", (identity, encoded))
