"""Durable storage for members, staff, pool, withdrawals.
Never overwrite a live file with empty/new deploy files.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KEEP = (
    "users.json",
    "withdrawals.json",
    "company_pool.json",
    "otps.json",
)
DATA_DIR: Path | None = None


def _writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def resolve() -> Path:
    env = (os.environ.get("DATA_DIR") or os.environ.get("RAILWAY_VOLUME_MOUNT_PATH") or "").strip()
    candidates = []
    if env:
        candidates.append(Path(env))
    candidates.append(Path("/data"))
    candidates.append(ROOT / "data")
    for c in candidates:
        if _writable(c):
            return c
    fallback = ROOT / "data"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def migrate(dest: Path) -> None:
    src = ROOT / "data"
    dest.mkdir(parents=True, exist_ok=True)
    if src.resolve() == dest.resolve():
        return
    for name in KEEP:
        s, d = src / name, dest / name
        live = d.exists() and d.stat().st_size > 2
        if live:
            continue
        if s.exists() and s.stat().st_size > 2:
            shutil.copy2(s, d)


def backup(path: Path) -> None:
    try:
        if path.exists() and path.stat().st_size > 2:
            bak = path.with_suffix(path.suffix + ".bak")
            shutil.copy2(path, bak)
    except Exception as e:
        print("backup skip", path.name, e)


def init() -> Path:
    global DATA_DIR
    dest = resolve()
    migrate(dest)
    DATA_DIR = dest
    os.environ["OC_DATA_DIR"] = str(dest)
    print("[persist] DATA_DIR", dest)
    for name in KEEP:
        p = dest / name
        print("[persist]", name, "ok" if p.exists() else "missing", p.stat().st_size if p.exists() else 0)
    return dest


if __name__ == "__main__":
    init()
