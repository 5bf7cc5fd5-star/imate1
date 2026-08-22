"""Patch server.py: pool, credits, VIP rules, member IDs, staff positions."""
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
try:
    import staff_roles as _roles
except Exception as _re:
    _roles = None
    print("staff_roles not loaded:", _re)

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

OLD_PUB = '''def public_user(u):
    return {
        "id": u["id"],
        "name": u["name"],
'''

NEW_PUB = '''def public_user(u):
    try:
        if not u.get("member_no"):
            import member_ids as _mid
            u["member_no"] = _mid.alloc(get_users())
            update_user(u)
    except Exception as _mn:
        print("member_no", _mn)
    return {
        "id": u["id"],
        "name": u["name"],
        "member_no": u.get("member_no") or "",
        "position": u.get("position") or ("owner" if u.get("is_admin") else ("support" if u.get("is_support") else "")),
        "position_label": u.get("position_label") or "",
'''

OLD_REG = '''            "id": "u_" + uuid.uuid4().hex[:12],
            "name": name,
'''

NEW_REG = '''            "id": "u_" + uuid.uuid4().hex[:12],
            "member_no": __import__("member_ids").alloc(get_users()),
            "name": name,
'''

STAFF_MARKER = "# === STAFF POSITIONS ==="
STAFF_BLOCK = r'''
# === STAFF POSITIONS ===
def _staff_set(body):
    if not _roles:
        raise RuntimeError("staff_roles missing")
    uid = body.get("id") or body.get("user_id")
    user = find_user(uid=uid) or find_user(email=body.get("email"))
    if not user:
        raise ValueError("Staff not found")
    _roles.apply_position(user, body.get("position"))
    if body.get("name"):
        user["name"] = body.get("name").strip()
    update_user(user)
    return public_user(user)

def _staff_create(body):
    if not _roles:
        raise RuntimeError("staff_roles missing")
    email = (body.get("email") or "").strip().lower()
    name = (body.get("name") or "").strip()
    phone = (body.get("phone") or "").strip()
    password = body.get("password") or ""
    if not email or not name or not password:
        raise ValueError("Name, email and password required")
    if find_user(email=email):
        raise ValueError("Email already registered")
    user = {
        "id": "st_" + uuid.uuid4().hex[:10],
        "name": name,
        "phone": phone,
        "email": email,
        "password_hash": hash_password(password),
        "invite_code": gen_invite_code(),
        "balance": 0,
        "machines": [],
        "transactions": [],
        "deposits": [],
        "is_admin": False,
        "is_support": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        user["member_no"] = __import__("member_ids").alloc(get_users())
    except Exception:
        user["member_no"] = ""
    _roles.apply_position(user, body.get("position") or "support")
    users = get_users()
    users.append(user)
    save_users(users)
    return public_user(user)
'''

OLD_ADMIN_ROUTES = '''    if path == "/api/admin/withdrawals/action":
        return self._admin_withdrawal_action(body)
    if path == "/api/admin/deposits/action":
        return self._admin_deposit_action(body)
'''

STAFF_ROUTES = '''    if path == "/api/admin/withdrawals/action":
        return self._admin_withdrawal_action(body)
    if path == "/api/admin/deposits/action":
        return self._admin_deposit_action(body)
    if path == "/api/admin/staff/set":
        try:
            return self._json(200, {"user": _staff_set(body)})
        except Exception as e:
            return self._json(400, {"error": str(e)})
    if path == "/api/admin/staff/create":
        try:
            return self._json(200, {"user": _staff_create(body)})
        except Exception as e:
            return self._json(400, {"error": str(e)})
'''

def apply_member_ids(t):
    if '"member_no": u.get("member_no")' not in t and OLD_PUB in t:
        t = t.replace(OLD_PUB, NEW_PUB, 1)
        print("patched public_user")
    if '"member_no": __import__("member_ids")' not in t and OLD_REG in t:
        t = t.replace(OLD_REG, NEW_REG, 1)
        print("patched register")
    return t

def apply_staff(t):
    if STAFF_MARKER not in t:
        anchor = "DATA_DIR.mkdir(exist_ok=True)"
        if anchor in t:
            t = t.replace(anchor, anchor + "\n" + STAFF_BLOCK, 1)
        else:
            t = STAFF_BLOCK + "\n" + t
        print("staff helpers")
    if "/api/admin/staff/set" not in t and OLD_ADMIN_ROUTES in t:
        t = t.replace(OLD_ADMIN_ROUTES, STAFF_ROUTES, 1)
        print("staff routes")
    get_anchor = 'if path == "/api/admin/users":'
    extra = '''if path == "/api/admin/positions":
            try:
                import staff_roles as _sr
                return self._json(200, {"positions": _sr.list_positions()})
            except Exception as e:
                return self._json(500, {"error": str(e)})
        if path == "/api/admin/staff":
            return self._json(200, {"staff": [public_user(u) for u in get_users()]})
        '''
    if get_anchor in t and "/api/admin/positions" not in t:
        t = t.replace(get_anchor, extra + get_anchor, 1)
        print("staff GET")
    return t

def main():
    if not SP.exists():
        print("no server.py"); return
    t = SP.read_text(encoding="utf-8")
    if MARKER not in t:
        anchor = "DATA_DIR.mkdir(exist_ok=True)"
        if anchor in t:
            t = t.replace(anchor, anchor + "\n" + PATCH_HELPERS, 1)
        else:
            t = PATCH_HELPERS + "\n" + t
        print("ops helpers")
    else:
        print("ops patch already present")
    t = apply_member_ids(t)
    t = apply_staff(t)
    SP.write_text(t, encoding="utf-8")
    print("done", SP.stat().st_size)

if __name__ == "__main__":
    main()
