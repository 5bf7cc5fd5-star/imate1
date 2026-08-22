"""Company pool, credits, VIP withdraw rules (as of 15 Aug 2026)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
POOL_FILE = DATA_DIR / "company_pool.json"
USERS_FILE = DATA_DIR / "users.json"
WITHDRAWALS_FILE = DATA_DIR / "withdrawals.json"

WITHDRAW_RULES_EFFECTIVE = "2026-08-15"
VIP_DAILY_CAPS = {1: 5000.0, 2: 7500.0, 3: 10000.0, 4: 12500.0}
WITHDRAW_FEE_PCT = 0.05
POOL_SEED = "usd_100m_2026_08_22"
POOL_OPENING_USD = 100_000_000.00


def _now():
    return datetime.now(timezone.utc).isoformat()


def _load(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default


def _save(path, data):
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def get_pool():
    p = _load(POOL_FILE, None)
    if not p:
        p = {
            "balance": POOL_OPENING_USD,
            "currency": "USD",
            "updated_at": _now(),
            "seed": POOL_SEED,
            "ledger": [{
                "id": "pl_open100m",
                "at": _now(),
                "type": "opening",
                "amount": POOL_OPENING_USD,
                "balance_before": 0.0,
                "balance_after": POOL_OPENING_USD,
                "note": "Company pool opening balance 100,000,000 USD",
                "meta": {},
            }],
            "notes": "Company pool — Inventory. Deposits pull from pool into wallets; approved withdrawals return to pool.",
        }
        _save(POOL_FILE, p)
        return p
    if p.get("seed") != POOL_SEED:
        before = float(p.get("balance") or 0)
        p["balance"] = POOL_OPENING_USD
        p["currency"] = "USD"
        p["seed"] = POOL_SEED
        p.setdefault("ledger", []).insert(0, {
            "id": "pl_set100m",
            "at": _now(),
            "type": "adjust",
            "amount": round(POOL_OPENING_USD - before, 2),
            "balance_before": before,
            "balance_after": POOL_OPENING_USD,
            "note": "Admin set company pool to 100,000,000 USD",
            "meta": {},
        })
        save_pool(p)
    p["currency"] = "USD"
    return p


def save_pool(p):
    p["updated_at"] = _now()
    _save(POOL_FILE, p)


def pool_ledger(entry_type: str, amount: float, note: str, meta=None):
    p = get_pool()
    amt = float(amount)
    before = float(p.get("balance", 0))
    after = round(before + amt, 2)
    p["balance"] = after
    p.setdefault("ledger", []).insert(0, {
        "id": "pl_" + uuid.uuid4().hex[:10],
        "at": _now(),
        "type": entry_type,
        "amount": amt,
        "balance_before": before,
        "balance_after": after,
        "note": note,
        "meta": meta or {},
    })
    p["ledger"] = p["ledger"][:2000]
    save_pool(p)
    return p


def set_pool_balance(new_balance: float, note: str = "Admin set pool balance"):
    p = get_pool()
    delta = round(float(new_balance) - float(p.get("balance", 0)), 2)
    return pool_ledger("adjust", delta, note)


def vip_level(user: dict) -> int:
    total = 0.0
    for m in user.get("machines") or []:
        try:
            total += float(m.get("price") or m.get("amount") or 0)
        except (TypeError, ValueError):
            pass
    if total <= 0:
        for d in user.get("deposits") or []:
            if str(d.get("status", "")).lower() in ("confirmed", "approved", "ok"):
                try:
                    total += float(d.get("amount") or 0)
                except (TypeError, ValueError):
                    pass
    if total >= 140000:
        return 4
    if total >= 105000:
        return 3
    if total >= 70000:
        return 2
    if total >= 35000:
        return 1
    return 1


def daily_withdrawn(user_id: str, day=None) -> float:
    day = day or datetime.now(timezone.utc).date()
    items = _load(WITHDRAWALS_FILE, [])
    total = 0.0
    for w in items:
        if w.get("user_id") != user_id:
            continue
        st = str(w.get("status", "")).lower()
        if st in ("rejected", "cancel", "cancelled"):
            continue
        created = str(w.get("created_at") or "")[:10]
        if created == day.isoformat():
            try:
                total += float(w.get("amount") or 0)
            except (TypeError, ValueError):
                pass
    return total


def withdraw_rules_payload(user=None):
    out = {
        "effective_from": WITHDRAW_RULES_EFFECTIVE,
        "fee_pct": WITHDRAW_FEE_PCT,
        "vip_daily_caps": VIP_DAILY_CAPS,
        "pool_currency": "USD",
        "flow": [
            "Member requests withdraw → amount + 5% fee reserved from wallet",
            "Admin: Under Review → Reviewed → Disbursed",
            "On Disburse: funds leave member wallet (already reserved) and are added to Company Pool (Inventory)",
            "On Reject: reserved amount is refunded to member wallet",
        ],
        "deposit_flow": [
            "Member submits deposit with TxID",
            "Admin verifies TxID → Approve",
            "On Approve: deduct amount from Company Pool (Inventory) and credit member wallet",
        ],
    }
    if user:
        lv = vip_level(user)
        cap = VIP_DAILY_CAPS.get(lv, 5000.0)
        used = daily_withdrawn(user.get("id") or "")
        out["member"] = {
            "vip": lv,
            "daily_cap": cap,
            "withdrawn_today": used,
            "remaining_today": max(0.0, round(cap - used, 2)),
        }
    return out


def credit_user(find_user_fn, update_user_fn, public_user_fn, identifier: str, amount: float, note: str = ""):
    amount = round(float(amount), 2)
    if amount == 0:
        raise ValueError("Amount cannot be zero")
    user = find_user_fn(email=identifier) or find_user_fn(phone=identifier)
    if not user and identifier:
        user = find_user_fn(uid=identifier)
    if not user:
        raise ValueError(f"User not found: {identifier}")
    user["balance"] = round(float(user.get("balance") or 0) + amount, 2)
    user.setdefault("transactions", []).insert(0, {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": f"Admin credit{(' — ' + note) if note else ''}",
        "amount": amount,
    })
    update_user_fn(user)
    return public_user_fn(user)


def bulk_credit(find_user_fn, update_user_fn, public_user_fn, lines: list):
    results = []
    for raw in lines:
        if isinstance(raw, str):
            parts = [p.strip() for p in raw.replace(";", ",").split(",")]
            if len(parts) < 2:
                results.append({"ok": False, "line": raw, "error": "Need identifier,amount"})
                continue
            ident, amt = parts[0], parts[1]
            note = parts[2] if len(parts) > 2 else "bulk credit"
        else:
            ident = raw.get("identifier") or raw.get("email") or raw.get("phone") or raw.get("id")
            amt = raw.get("amount")
            note = raw.get("note") or "bulk credit"
        try:
            u = credit_user(find_user_fn, update_user_fn, public_user_fn, ident, float(amt), note)
            results.append({"ok": True, "identifier": ident, "amount": float(amt), "user": u})
        except Exception as e:
            results.append({"ok": False, "identifier": ident, "error": str(e)})
    return results
