#!/usr/bin/env python3
"""Run versioned database migrations. Never deletes member/staff rows."""
from __future__ import annotations

import sqlite3
import importlib.util
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MIGRATIONS = ROOT / "migrations"


def data_dir() -> Path:
    try:
        import persist
        return persist.init()
    except Exception:
        d = ROOT / "data"
        d.mkdir(exist_ok=True)
        return d


def db_path() -> Path:
    return data_dir() / "ownclub.db"


def connect():
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    return conn


def applied(conn):
    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    return {r["version"] for r in rows}


def mark(conn, version: str):
    conn.execute(
        "INSERT OR REPLACE INTO schema_migrations(version, applied_at) VALUES(?,?)",
        (version, datetime.now(timezone.utc).isoformat()),
    )


def run():
    dest = data_dir()
    conn = connect()
    done = applied(conn)
    files = sorted(MIGRATIONS.glob("*"))
    ran = []
    for f in files:
        if f.name.startswith(".") or f.suffix not in (".sql", ".py"):
            continue
        ver = f.name
        if ver in done:
            print("[migrate] skip", ver)
            continue
        print("[migrate] apply", ver)
        if f.suffix == ".sql":
            conn.executescript(f.read_text(encoding="utf-8"))
        else:
            spec = importlib.util.spec_from_file_location(f"mig_{f.stem}", f)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "apply"):
                mod.apply(conn, dest)
        mark(conn, ver)
        conn.commit()
        ran.append(ver)
    conn.commit()
    conn.close()
    print("[migrate] done", ran or "already up to date", "db=", db_path())
    return ran


if __name__ == "__main__":
    run()
