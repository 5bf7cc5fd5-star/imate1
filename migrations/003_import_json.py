"""Import existing JSON files into SQLite without deleting live rows."""
import json
from datetime import datetime, timezone
from pathlib import Path


def apply(conn, data_dir: Path):
    now = datetime.now(timezone.utc).isoformat()
    users_file = data_dir / "users.json"
    wd_file = data_dir / "withdrawals.json"
    pool_file = data_dir / "company_pool.json"

    existing = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing == 0 and users_file.exists():
        raw = json.loads(users_file.read_text(encoding="utf-8") or "[]")
        for u in raw:
            uid = u.get("id") or ""
            if not uid:
                continue
            conn.execute(
                "INSERT OR IGNORE INTO users(id,email,phone,member_no,name,position,is_admin,is_support,balance,data,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    uid,
                    (u.get("email") or "").lower(),
                    u.get("phone") or "",
                    u.get("member_no") or "",
                    u.get("name") or "",
                    u.get("position") or "",
                    1 if u.get("is_admin") else 0,
                    1 if u.get("is_support") else 0,
                    float(u.get("balance") or 0),
                    json.dumps(u, ensure_ascii=False),
                    now,
                ),
            )
            for i, t in enumerate(u.get("transactions") or []):
                tid = f"{uid}-tx-{i}-" + str(t.get("date") or i)
                conn.execute(
                    "INSERT OR IGNORE INTO transactions(id,user_id,at,type,amount,note,data,created_at) VALUES(?,?,?,?,?,?,?,?)",
                    (
                        tid,
                        uid,
                        t.get("date") or t.get("at") or now,
                        t.get("type") or "tx",
                        float(t.get("amount") or 0),
                        t.get("type") or "",
                        json.dumps(t, ensure_ascii=False),
                        now,
                    ),
                )
        print("[migrate] imported users", len(raw))
    else:
        print("[migrate] users already present", existing, — skip json overwrite")

    wd_n = conn.execute("SELECT COUNT(*) FROM withdrawals").fetchone()[0]
    if wd_n == 0 and wd_file.exists():
        raw = json.loads(wd_file.read_text(encoding="utf-8") or "[]")
        for w in raw:
            wid = w.get("id") or ""
            if not wid:
                continue
            conn.execute(
                "INSERT OR IGNORE INTO withdrawals(id,user_id,amount,fee,status,data,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (
                    wid,
                    w.get("user_id"),
                    float(w.get("amount") or 0),
                    float(w.get("fee") or 0),
                    w.get("status") or "pending",
                    json.dumps(w, ensure_ascii=False),
                    w.get("created_at") or now,
                    now,
                ),
            )
        print("[migrate] imported withdrawals", len(raw))

    pool_n = conn.execute("SELECT COUNT(*) FROM pool_state").fetchone()[0]
    if pool_n == 0 and pool_file.exists():
        p = json.loads(pool_file.read_text(encoding="utf-8") or "{}")
        if p:
            conn.execute(
                "INSERT OR IGNORE INTO pool_state(id,balance,currency,seed,data,updated_at) VALUES(1,?,?,?,?,?)",
                (
                    float(p.get("balance") or 0),
                    p.get("currency") or "USD",
                    p.get("seed") or "",
                    json.dumps(p, ensure_ascii=False),
                    p.get("updated_at") or now,
                ),
            )
            for e in p.get("ledger") or []:
                conn.execute(
                    "INSERT OR IGNORE INTO pool_ledger(id,at,type,amount,balance_before,balance_after,note,meta,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        e.get("id") or "",
                        e.get("at"),
                        e.get("type"),
                        float(e.get("amount") or 0),
                        float(e.get("balance_before") or 0),
                        float(e.get("balance_after") or 0),
                        e.get("note") or "",
                        json.dumps(e.get("meta") or {}, ensure_ascii=False),
                        now,
                    ),
                )
            print("[migrate] imported pool")
