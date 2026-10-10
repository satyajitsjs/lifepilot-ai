"""SQLite MVP persistence. Replace with PostgreSQL in deployment; APIs keep the contract."""
from __future__ import annotations
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from .config import DATABASE_PATH


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def uid() -> str:
    return str(uuid4())


def postgres_sql(sql: str) -> str:
    """Convert this app's fixed SQLite-style SQL placeholders for psycopg."""
    statement = sql.replace("?", "%s")
    if statement.lstrip().upper().startswith("INSERT OR IGNORE INTO"):
        statement = statement.replace("INSERT OR IGNORE INTO", "INSERT INTO", 1)
        statement = statement.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    return statement


class PostgresConnection:
    """Minimal SQL interface shared by the existing domain modules."""
    def __init__(self, connection):
        self.connection = connection

    def execute(self, statement, params=()):
        return self.connection.execute(postgres_sql(statement), params)

    def executemany(self, statement, values):
        with self.connection.cursor() as cursor:
            return cursor.executemany(postgres_sql(statement), values)

    def executescript(self, script):
        # Only used with the application's trusted, fixed schema DDL.
        for segment in script.split(";"):
            statement = segment.strip()
            if statement and not statement.upper().startswith("PRAGMA"):
                self.execute(statement)

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()


@contextmanager
def connect():
    """Use PostgreSQL for persistent hosting; SQLite for local development only."""
    dsn = os.environ.get("DATABASE_URL", "").strip()
    if dsn:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError("Install psycopg[binary] for PostgreSQL") from exc
        connection = PostgresConnection(psycopg.connect(dsn, row_factory=dict_row, connect_timeout=10))
    else:
        if os.environ.get("VERCEL"):
            raise RuntimeError("DATABASE_URL is required on Vercel; ephemeral SQLite is forbidden")
        DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(DATABASE_PATH), timeout=20)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=20000")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def row_dict(row):
    return dict(row) if row is not None else None


def rows(conn, statement, params=()):
    return [dict(r) for r in conn.execute(statement, params).fetchall()]


def one(conn, statement, params=()):
    return row_dict(conn.execute(statement, params).fetchone())


def event(conn, actor_id: str, kind: str, text: str, circle_id: str | None = None):
    conn.execute(
        "INSERT INTO activity(id, actor_id, kind, message, circle_id, created_at) VALUES(?,?,?,?,?,?)",
        (uid(), actor_id, kind, text, circle_id, now()),
    )


def initialize():
    with connect() as c:
        # Serialize concurrent cold-start seeding on shared PostgreSQL.
        if os.environ.get("DATABASE_URL"):
            c.execute("SELECT pg_advisory_xact_lock(907, 2026)")
        c.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
            avatar TEXT NOT NULL, color TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'member'
        );
        CREATE TABLE IF NOT EXISTS circles (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, icon TEXT NOT NULL, color TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS memberships (
            user_id TEXT NOT NULL REFERENCES users(id), circle_id TEXT NOT NULL REFERENCES circles(id),
            role TEXT NOT NULL DEFAULT 'member', PRIMARY KEY(user_id, circle_id)
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY, circle_id TEXT NOT NULL REFERENCES circles(id),
            title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
            assignee_id TEXT NOT NULL REFERENCES users(id), created_by TEXT NOT NULL REFERENCES users(id),
            status TEXT NOT NULL DEFAULT 'todo', priority TEXT NOT NULL DEFAULT 'medium',
            due_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            idempotency_key TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY, circle_id TEXT NOT NULL REFERENCES circles(id),
            title TEXT NOT NULL, starts_at TEXT NOT NULL, ends_at TEXT NOT NULL,
            created_by TEXT NOT NULL REFERENCES users(id), location TEXT NOT NULL DEFAULT '',
            attendees TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL,
            idempotency_key TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS reminders (
            id TEXT PRIMARY KEY, circle_id TEXT NOT NULL REFERENCES circles(id),
            user_id TEXT NOT NULL REFERENCES users(id), title TEXT NOT NULL,
            due_at TEXT NOT NULL, completed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL, idempotency_key TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS notifications (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
            title TEXT NOT NULL, body TEXT NOT NULL, channel TEXT NOT NULL DEFAULT 'in_app',
            read_at TEXT, created_at TEXT NOT NULL, idempotency_key TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS proposals (
            id TEXT PRIMARY KEY, actor_id TEXT NOT NULL REFERENCES users(id),
            circle_id TEXT NOT NULL REFERENCES circles(id), prompt TEXT NOT NULL,
            summary TEXT NOT NULL, actions TEXT NOT NULL, mode TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL,
            decided_at TEXT, outcomes TEXT NOT NULL DEFAULT '[]'
        );
        CREATE TABLE IF NOT EXISTS activity (
            id TEXT PRIMARY KEY, actor_id TEXT NOT NULL REFERENCES users(id),
            kind TEXT NOT NULL, message TEXT NOT NULL,
            circle_id TEXT, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_tasks_circle ON tasks(circle_id, status);
        CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_proposals_actor ON proposals(actor_id, created_at);
        """)
        if one(c, "SELECT id FROM users LIMIT 1"):
            return
        people = [
            ("alex", "Alex Morgan", "alex@lifepilot.demo", "AM", "indigo", "owner"),
            ("rahul", "Rahul Sharma", "rahul@lifepilot.demo", "RS", "amber", "member"),
            ("priya", "Priya Patel", "priya@lifepilot.demo", "PP", "rose", "member"),
            ("maya", "Maya Chen", "maya@lifepilot.demo", "MC", "teal", "member"),
        ]
        c.executemany("INSERT INTO users VALUES (?,?,?,?,?,?)", people)
        c.executemany("INSERT INTO circles VALUES (?,?,?,?,?)", [
            ("studio", "Design & Dev Team", "layers", "violet", "Our little corner of big ideas"),
            ("home", "Home & Family", "home", "coral", "Better together, every day"),
        ])
        c.executemany("INSERT INTO memberships VALUES (?,?,?)", [
            ("alex", "studio", "owner"), ("rahul", "studio", "member"),
            ("priya", "studio", "member"), ("maya", "studio", "member"),
            ("alex", "home", "owner"), ("priya", "home", "member"),
        ])
        base = datetime.now(timezone.utc)
        tasks = [
            ("Review landing page concepts", "priya", "in_progress", "high", 1, "studio"),
            ("Finalize API endpoints", "rahul", "todo", "high", 2, "studio"),
            ("Update onboarding flow", "alex", "todo", "medium", 3, "studio"),
            ("Share project brief", "maya", "done", "low", -1, "studio"),
            ("Plan weekend grocery run", "priya", "todo", "medium", 4, "home"),
            ("Set up team workspace", "alex", "done", "low", -2, "studio"),
        ]
        for title, assignee, status, priority, offset, circle in tasks:
            c.execute("INSERT INTO tasks(id,circle_id,title,assignee_id,created_by,status,priority,due_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                 (uid(),circle,title,assignee,"alex",status,priority,(base+timedelta(days=offset)).date().isoformat(),now(),now()))
        for title,offset,duration,attendees in [
            ("Weekly team sync",1,45,["alex","rahul","priya","maya"]),
            ("Design review",3,60,["alex","priya"]),
        ]:
            begin=(base+timedelta(days=offset)).replace(hour=15,minute=0,second=0,microsecond=0)
            c.execute("INSERT INTO events(id,circle_id,title,starts_at,ends_at,created_by,attendees,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (uid(),"studio",title,begin.isoformat(),(begin+timedelta(minutes=duration)).isoformat(),"alex",json.dumps(attendees),now()))
        for user,title,body in [
            ("alex","Welcome to LifePilot","Your shared workspace is ready to go."),
            ("rahul","New workspace","You've been added to Design & Dev Team."),
        ]:
            c.execute("INSERT INTO notifications(id,user_id,title,body,created_at) VALUES(?,?,?,?,?)",(uid(),user,title,body,now()))
        event(c,"alex","workspace","Created the Design & Dev Team circle","studio")
        event(c,"priya","task","Started working on landing page concepts","studio")
        event(c,"rahul","task","Finalizing the API endpoints","studio")
