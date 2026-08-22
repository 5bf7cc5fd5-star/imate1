"""Patch server.py: company pool, credits, VIP withdraw caps."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent
SP = ROOT / "server.py"
MARKER = "# === OWNCLUB OPS PATCH ==="
PATCH_HELPERS = r'''
# === OWNCLUB OPS PATCH ===
try:
    import ops_api as _ops
except Exception as _e:
    _ops = None
    print("ops_api not loaded:", _e)

def _pool_on_deposit_confirm(user, dep):
    if not _ops: return
    try:
        amt = float(dep.get("amount") or 0)
        _ops.pool_ledger("deposit_out", -amt, f"Deposit to {user.get('name') or user.get('email')}", {"user_id": user.get("id"), "deposit_id": dep.get("id"), "amount": amt})
    except Exception as e:
        print("pool deposit err", e)

def _pool_on_withdraw_disburse(wd):
    if not _ops: return
    try:
        amt = float(wd.get("amount") or 0)
        _ops.pool_ledger("withdraw_in", amt, f"Withdrawal disbursed user={wd.get('user_id')}", {"user_id": wd.get("user_id"), "withdrawal_id": wd.get("id"), "amount": amt})
    except Exception as e:
        print("pool withdraw err", e)
'''

OLD_DEP = '''    if action == "confirm":
        dep["status"] = "confirmed"
        user["balance"] = round(user.get("balance", 0) + float(dep["amount"]), 2)
        user.setdefault("transactions", []).insert(0, {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": f"Deposit confirmed — {dep['method']}",
            "amount": dep["amount"],
        })
'''

NEW_DEP = '''    if action == "confirm":
        dep["status"] = "confirmed"
        user["balance"] = round(user.get("balance", 0) + float(dep["amount"]), 2)
        user.setdefault("transactions", []).insert(0, {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": f"Deposit confirmed — {dep.get('method', 'deposit')}",
            "amount": dep["amount"],
        })
        try:
            _pool_on_deposit_confirm(user, dep)
        except Exception as _pe:
            print("pool dep", _pe)
'''

OLD_WD_OK = '''    wd["status"] = "approved" if action == "approve" else "rejected"
    wd["processed_at"] = datetime.now(timezone.utc).isoformat()
    wd["admin_note"] = note
    if action == "reject":
'''

NEW_WD_OK = '''    if action in ("approve", "disburse"):
        wd["status"] = "disbursed" if action == "disburse" else "approved"
        try:
            _pool_on_withdraw_disburse(wd)
        except Exception as _pe:
            print("pool wd", _pe)
    else:
        wd["status"] = "rejected"
    wd["processed_at"] = datetime.now(timezone.utc).isoformat()
    wd["admin_note"] = note
    if action == "reject":
'''

OLD_WD_ACT = '''    if action not in ("approve", "reject"):
        return self._json(400, {"error": "action must be approve or reject"})
'''

NEW_WD_ACT = '''    if action not in ("approve", "reject", "disburse", "review"):
        return self._json(400, {"error": "action must be approve, review, disburse or reject"})
    if action == "review":
        items = get_withdrawals()
        wd = next((w for w in items if w["id"] == body.get("id")), None)
        if not wd:
            return self._json(404, {"error": "Withdrawal not found"})
        wd["status"] = "reviewed"
        wd["processed_at"] = datetime.now(timezone.utc).isoformat()
        save_withdrawals(items)
        return self._json(200, {"message": "Withdrawal reviewed", "withdrawal": wd})
'''

OLD_WD_BAL = '''    if amount > user.get("balance", 0):
        return self._json(400, {"error": "Insufficient balance"})

    fee = round(amount * 0.05, 2)
'''

NEW_WD_BAL = '''    if amount > user.get("balance", 0):
        return self._json(400, {"error": "Insufficient balance"})

    try:
        if _ops:
            rules = _ops.withdraw_rules_payload(user)
            mem = rules.get("member") or {}
            cap = float(mem.get("daily_cap") or 5000)
            used = float(mem.get("withdrawn_today") or 0)
            if amount + used > cap + 1e-6:
                return self._json(400, {"error": f"Daily withdraw limit VIP-{mem.get('vip',1)} is {cap:,.0f}. Used today {used:,.0f}. Remaining {max(0,cap-used):,.0f}.", "rules": rules})
    except Exception as _ve:
        print("vip check", _ve)

    fee = round(amount * 0.05, 2)
'''

OLD_ADMIN_ROUTES = '''    if path == "/api/admin/withdrawals/action":
        return self._admin_withdrawal_action(body)
    if path == "/api/admin/deposits/action":
        return self._admin_deposit_action(body)

    self._json(404, {"error": "Not found"})
'''

NEW_ADMIN_ROUTES = '''    if path == "/api/admin/withdrawals/action":
        return self._admin_withdrawal_action(body)
    if path == "/api/admin/deposits/action":
        return self._admin_deposit_action(body)
    if path == "/api/admin/pool":
        if not _ops: return self._json(500, {"error": "ops_api missing"})
        return self._json(200, _ops.get_pool())
    if path == "/api/admin/pool/set":
        if not _ops: return self._json(500, {"error": "ops_api missing"})
        try:
            return self._json(200, _ops.set_pool_balance(float(body.get("balance")), body.get("note") or "Admin set pool"))
        except Exception as e:
            return self._json(400, {"error": str(e)})
    if path == "/api/admin/pool/adjust":
        if not _ops: return self._json(500, {"error": "ops_api missing"})
        try:
            return self._json(200, _ops.pool_ledger(body.get("type") or "adjust", float(body.get("amount") or 0), body.get("note") or "adjust", body.get("meta") or {}))
        except Exception as e:
            return self._json(400, {"error": str(e)})
    if path == "/api/admin/credit":
        try:
            u = _ops.credit_user(find_user, update_user, public_user, body.get("identifier") or body.get("email") or body.get("phone") or body.get("id"), float(body.get("amount") or 0), body.get("note") or "")
            return self._json(200, {"message": "Credited", "user": u})
        except Exception as e:
            return self._json(400, {"error": str(e)})
    if path == "/api/admin/credit/bulk":
        lines = body.get("lines") or body.get("items") or []
        if isinstance(lines, str):
            lines = [ln.strip() for ln in lines.splitlines() if ln.strip()]
        try:
            return self._json(200, {"results": _ops.bulk_credit(find_user, update_user, public_user, lines)})
        except Exception as e:
            return self._json(400, {"error": str(e)})
    if path == "/api/admin/withdraw-rules":
        uid = body.get("user_id") if body else None
        u = find_user(uid=uid) if uid else None
        return self._json(200, _ops.withdraw_rules_payload(u) if _ops else {})

    self._json(404, {"error": "Not found"})
'''

def main():
    if not SP.exists():
        print("no server.py"); return
    t = SP.read_text(encoding="utf-8")
    if MARKER in t:
        print("ops patch already present"); return
    anchor = "DATA_DIR.mkdir(exist_ok=True)"
    if anchor in t:
        t = t.replace(anchor, anchor + "\n" + PATCH_HELPERS, 1)
    else:
        t = PATCH_HELPERS + "\n" + t
    if OLD_DEP in t:
        t = t.replace(OLD_DEP, NEW_DEP, 1); print("patched deposit")
    else:
        print("WARN deposit block")
    if OLD_WD_ACT in t:
        t = t.replace(OLD_WD_ACT, NEW_WD_ACT, 1); print("patched wd act")
    if OLD_WD_OK in t:
        t = t.replace(OLD_WD_OK, NEW_WD_OK, 1); print("patched wd ok")
    if OLD_WD_BAL in t:
        t = t.replace(OLD_WD_BAL, NEW_WD_BAL, 1); print("patched vip")
    if OLD_ADMIN_ROUTES in t:
        t = t.replace(OLD_ADMIN_ROUTES, NEW_ADMIN_ROUTES, 1); print("patched routes")
    get_anchor = 'if path == "/api/admin/users":'
    if get_anchor in t and 'path == "/api/admin/pool"' not in t:
        t = t.replace(get_anchor, 'if path == "/api/admin/pool":\n            try:\n                import ops_api as _ops2\n                return self._json(200, _ops2.get_pool())\n            except Exception as e:\n                return self._json(500, {"error": str(e)})\n        if path == "/api/admin/withdraw-rules":\n            try:\n                import ops_api as _ops2\n                return self._json(200, _ops2.withdraw_rules_payload())\n            except Exception as e:\n                return self._json(500, {"error": str(e)})\n        ' + get_anchor, 1)
        print("patched GET")
    SP.write_text(t, encoding="utf-8")
    print("done", SP.stat().st_size)

if __name__ == "__main__":
    main()
