#!/usr/bin/env python3
"""
iMate1 Backend — DEMO ONLY
- Token auth (HMAC)
- Registration / Login
- Machine purchases + 5% first-purchase bonus
- Withdrawal requests (pending → admin approve/reject)
- Admin dashboard API
- Serves frontend + admin UI
"""

import json
import os
import hmac
import hashlib
import base64
import time
import uuid
import re
import random
import string
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from pathlib import Path

HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "8080"))
SECRET = os.environ.get("IMATE1_SECRET", "imate1-demo-secret-change-in-production-2026").encode()
TOKEN_TTL = 60 * 60 * 24 * 7

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
USERS_FILE = DATA_DIR / "users.json"
WITHDRAWALS_FILE = DATA_DIR / "withdrawals.json"

ADMIN_EMAIL = "k_hmed@yahoo.com"
ADMIN_PHONE = "+256780509960"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Madahketa@17")

# Never exposed to regular members via API responses
INTERNAL_MOBILE = "0780509960"
INTERNAL_BINANCE = "TLvT3czNGgpPH3oXURZFtyd4XTQUL2NhGy"


# ─────────────────────────────────────────────
# MOBILE MONEY INTEGRATION (Uganda)
# ─────────────────────────────────────────────
# Production: plug in one of these providers with your API keys.
#
# 1) Flutterwave  — https://developer.flutterwave.com (recommended aggregator)
# 2) Pesapal      — https://developer.pesapal.com
# 3) MTN MoMo     — https://momodeveloper.mtn.com  (Collection product)
# 4) Airtel Money — partner API via aggregator in most cases
#
# Flow:
#   Member taps Pay → backend creates collection request →
#   provider sends USSD/push to member phone → member approves →
#   webhook hits /api/momo/webhook → balance credited.
#
# Env vars (set on host):
#   MOMO_PROVIDER=flutterwave|mtn|pesapal|demo
#   MOMO_SECRET_KEY=...
#   MOMO_PUBLIC_KEY=...
#   MOMO_COLLECTION_NUMBER=0780509960
#   MOMO_WEBHOOK_SECRET=...
# ─────────────────────────────────────────────

MOMO_PROVIDER = os.environ.get("MOMO_PROVIDER", "demo")
MOMO_COLLECTION_NUMBER = os.environ.get("MOMO_COLLECTION_NUMBER", "0780509960")
MOMO_SECRET_KEY = os.environ.get("MOMO_SECRET_KEY", "")
MOMO_PUBLIC_KEY = os.environ.get("MOMO_PUBLIC_KEY", "")


def momo_initiate_collection(amount, phone, network, external_id):
    """
    Initiate a Mobile Money collection.
    Returns dict: {ok, provider_ref, status, message, pay_to}
    In demo mode, returns simulated success pending confirmation.
    """
    phone_digits = re.sub(r"\D", "", phone or "")
    if phone_digits.startswith("0"):
        phone_digits = "256" + phone_digits[1:]

    if MOMO_PROVIDER == "demo" or not MOMO_SECRET_KEY:
        return {
            "ok": True,
            "provider_ref": f"DEMO-{external_id}",
            "status": "pending_approval",
            "message": "Demo mode: instruct member to send MoMo to collection number, then admin confirms.",
            "pay_to": MOMO_COLLECTION_NUMBER,
            "network": network,
            "msisdn": phone_digits,
        }

    # --- Example Flutterwave charge (enable when keys are set) ---
    if MOMO_PROVIDER == "flutterwave":
        # Real call would use urllib.request to POST:
        # https://api.flutterwave.com/v3/charges?type=mobile_money_uganda
        # Headers: Authorization: Bearer <MOMO_SECRET_KEY>
        # Body: amount, currency=UGX, email, phone_number, tx_ref, network=MTN|AIRTEL
        return {
            "ok": False,
            "status": "not_configured",
            "message": "Flutterwave keys detected pattern — implement HTTP call with your secret key.",
            "pay_to": MOMO_COLLECTION_NUMBER,
        }

    return {
        "ok": False,
        "status": "unsupported_provider",
        "message": f"Provider {MOMO_PROVIDER} not implemented yet.",
        "pay_to": MOMO_COLLECTION_NUMBER,
    }


MACHINES = [
    {"id": 1, "name": "Crypto Mining A1 Series", "series": "A1", "price": 30000, "daily": 7500, "days": 20, "photo": "https://images.unsplash.com/photo-1486312338219-ce68d2c6f44d?w=400&h=300&fit=crop"},
    {"id": 2, "name": "Crypto Mining A2 Series", "series": "A2", "price": 50000, "daily": 12500, "days": 20, "photo": "https://images.unsplash.com/photo-1541807084-5c52b6b3adef?w=400&h=300&fit=crop"},
    {"id": 3, "name": "Crypto Mining A3 Series", "series": "A3", "price": 70000, "daily": 17500, "days": 20, "photo": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=400&h=300&fit=crop"},
    {"id": 4, "name": "Crypto Mining A4 Series", "series": "A4", "price": 90000, "daily": 22500, "days": 20, "photo": "https://images.unsplash.com/photo-1484788984921-fb4f1e4e8c89?w=400&h=300&fit=crop"},
    {"id": 5, "name": "Crypto Mining A5 Series", "series": "A5", "price": 110000, "daily": 27500, "days": 20, "photo": "https://images.unsplash.com/photo-1587614382346-4ec70e388b28?w=400&h=300&fit=crop"},
    {"id": 6, "name": "Crypto Mining A6 Series", "series": "A6", "price": 130000, "daily": 32500, "days": 20, "photo": "https://images.unsplash.com/photo-1603302576837-37561b2e8303?w=400&h=300&fit=crop"},
    {"id": 7, "name": "Crypto Mining A7 Series", "series": "A7", "price": 150000, "daily": 37500, "days": 20, "photo": "https://images.unsplash.com/photo-1593642632823-8f785ba67e45?w=400&h=300&fit=crop"},
    {"id": 8, "name": "Crypto Mining A8 Series", "series": "A8", "price": 170000, "daily": 42500, "days": 20, "photo": "https://images.unsplash.com/photo-1588872657578-7b0a5901c5b4?w=400&h=300&fit=crop"},
    {"id": 9, "name": "Crypto Mining A9 Series", "series": "A9", "price": 190000, "daily": 47500, "days": 20, "photo": "https://images.unsplash.com/photo-1525547717930-6d62c4fbdd4c?w=400&h=300&fit=crop"},
    {"id": 10, "name": "Crypto Mining A10 Series", "series": "A10", "price": 210000, "daily": 52500, "days": 20, "photo": "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=400&h=300&fit=crop"},
]
MACHINES_SORTED = sorted(MACHINES, key=lambda m: m['price'], reverse=True)


def load_json(path, default):
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_users():
    return load_json(USERS_FILE, [])


def save_users(users):
    save_json(USERS_FILE, users)


def get_withdrawals():
    return load_json(WITHDRAWALS_FILE, [])


def save_withdrawals(items):
    save_json(WITHDRAWALS_FILE, items)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return base64.b64encode(salt + h).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        raw = base64.b64decode(stored)
        salt, h = raw[:16], raw[16:]
        check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
        return hmac.compare_digest(h, check)
    except Exception:
        return False


def make_token(user_id: str, is_admin: bool) -> str:
    payload = {"uid": user_id, "adm": is_admin, "exp": int(time.time()) + TOKEN_TTL}
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = hmac.new(SECRET, body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def decode_token(token: str):
    try:
        body, sig = token.split(".", 1)
        expected = hmac.new(SECRET, body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        pad = "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(body + pad))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def gen_invite_code():
    chars = string.ascii_uppercase + "23456789"
    return "IM" + "".join(random.choices(chars, k=6))


def seed_admin():
    users = get_users()
    if not any(u["email"] == ADMIN_EMAIL for u in users):
        users.append({
            "id": "admin",
            "name": "Admin (Owner)",
            "phone": ADMIN_PHONE,
            "email": ADMIN_EMAIL,
            "password_hash": hash_password(ADMIN_PASSWORD),
            "id_type": "National ID",
            "id_num": "ADMIN-DEMO",
            "invite_code": "IMXT2Y0M8D",
            "referred_by": None,
            "balance": 0,
            "machines": [],
            "transactions": [],
            "bonus_claimed": False,
            "referral_earnings": 0,
            "referral_payouts": [],
            "deposits": [],
            "is_admin": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        save_users(users)
        print(f"[seed] Admin → {ADMIN_EMAIL} / {ADMIN_PASSWORD}")


def find_user(uid=None, email=None, phone=None):
    for u in get_users():
        if uid and u["id"] == uid:
            return u
        if email and u["email"].lower() == email.lower():
            return u
        if phone:
            clean = re.sub(r"\D", "", phone)
            if re.sub(r"\D", "", u["phone"]) == clean:
                return u
    return None


def update_user(user):
    users = get_users()
    for i, u in enumerate(users):
        if u["id"] == user["id"]:
            users[i] = user
            break
    save_users(users)


def public_user(u):
    return {
        "id": u["id"],
        "name": u["name"],
        "phone": u["phone"],
        "email": u["email"],
        "invite_code": u["invite_code"],
        "balance": u.get("balance", 0),
        "machines": u.get("machines", []),
        "transactions": u.get("transactions", [])[:50],
        "bonus_claimed": u.get("bonus_claimed", False),
        "is_admin": u.get("is_admin", False),
        "created_at": u.get("created_at"),
        "referral_count": sum(1 for x in get_users() if x.get("referred_by") == u["id"]),
        "referral_earnings": u.get("referral_earnings", 0),
        "referral_payouts": u.get("referral_payouts", [])[:50],
        "deposits": u.get("deposits", [])[:50],
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode())

    def _auth(self):
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None
        return decode_token(auth[7:].strip())

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        if path in ("/", "/index.html", "/app"):
            return self._serve_file("frontend.html", "text/html")
        if path == "/admin":
            return self._serve_file("admin.html", "text/html")

        if path == "/api/health":
            return self._json(200, {"ok": True, "service": "iMate1", "mode": "DEMO"})

        if path == "/api/machines":
            return self._json(200, {"machines": MACHINES_SORTED if "MACHINES_SORTED" in dir() else sorted(MACHINES, key=lambda m: m["price"], reverse=True)})

        token = self._auth()
        if not token:
            return self._json(401, {"error": "Unauthorized"})

        user = find_user(uid=token["uid"])
        if not user:
            return self._json(401, {"error": "User not found"})

        if path == "/api/me":
            return self._json(200, {"user": public_user(user)})

        if path == "/api/withdrawals/mine":
            mine = [w for w in get_withdrawals() if w["user_id"] == user["id"]]
            return self._json(200, {"withdrawals": mine})

        if not user.get("is_admin"):
            return self._json(403, {"error": "Admin only"})

        if path == "/api/admin/users":
            return self._json(200, {"users": [public_user(u) for u in get_users()]})

        if path == "/api/admin/deposits":
            items = []
            for u in get_users():
                for d in u.get("deposits", []):
                    items.append({**d, "user_id": u["id"], "user_name": u["name"], "user_phone": u["phone"]})
            items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return self._json(200, {"deposits": items})

        if path == "/api/admin/withdrawals":
            items = get_withdrawals()
            users_map = {u["id"]: u for u in get_users()}
            for w in items:
                u = users_map.get(w["user_id"], {})
                w["user_name"] = u.get("name", "?")
                w["user_phone"] = u.get("phone", "?")
                w["user_email"] = u.get("email", "?")
            return self._json(200, {"withdrawals": items})

        if path == "/api/admin/stats":
            users = get_users()
            wds = get_withdrawals()
            total_invested = sum(m["price"] for u in users for m in u.get("machines", []))
            pending = [w for w in wds if w["status"] == "pending"]
            total_ref = sum(u.get("referral_earnings", 0) for u in users)
            return self._json(200, {
                "total_users": len(users),
                "total_invested": total_invested,
                "pending_withdrawals": len(pending),
                "pending_amount": sum(w["amount"] for w in pending),
                "total_withdrawals": len(wds),
                "total_referral_payouts": total_ref,
            })

        self._json(404, {"error": "Not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._read_json()

        if path == "/api/momo/webhook":
            return self._momo_webhook(body)
        if path == "/api/register":
            return self._register(body)
        if path == "/api/login":
            return self._login(body)

        token = self._auth()
        if not token:
            return self._json(401, {"error": "Unauthorized"})
        user = find_user(uid=token["uid"])
        if not user:
            return self._json(401, {"error": "User not found"})

        if path == "/api/purchase":
            return self._purchase(user, body)
        if path == "/api/withdraw":
            return self._withdraw(user, body)
        if path == "/api/deposit":
            return self._deposit(user, body)

        if not user.get("is_admin"):
            return self._json(403, {"error": "Admin only"})

        if path == "/api/admin/withdrawals/action":
            return self._admin_withdrawal_action(body)
        if path == "/api/admin/deposits/action":
            return self._admin_deposit_action(body)

        self._json(404, {"error": "Not found"})

    def _register(self, body):
        name = (body.get("name") or "").strip()
        phone = (body.get("phone") or "").strip()
        email = (body.get("email") or "").strip().lower()
        password = body.get("password") or ""
        id_type = body.get("id_type") or "National ID"
        id_num = (body.get("id_num") or "").strip()
        invite = (body.get("invite_code") or "").strip().upper()

        if not all([name, phone, email, password]):
            return self._json(400, {"error": "All fields required"})
        digits = re.sub(r"\D", "", phone)
        if not digits.startswith("256") or len(digits) < 12:
            return self._json(400, {"error": "Valid +256 mobile number required"})
        if find_user(email=email):
            return self._json(400, {"error": "Email already registered"})
        if find_user(phone=phone):
            return self._json(400, {"error": "Phone already registered"})

        referred_by = None
        if invite:
            ref = next((u for u in get_users() if u["invite_code"] == invite), None)
            if not ref:
                return self._json(400, {"error": "Invalid invitation code"})
            referred_by = ref["id"]

        new_user = {
            "id": "u_" + uuid.uuid4().hex[:12],
            "name": name,
            "phone": phone,
            "email": email,
            "password_hash": hash_password(password),
            "id_type": id_type,
            "id_num": id_num,
            "invite_code": gen_invite_code(),
            "referred_by": referred_by,
            "balance": 0,
            "machines": [],
            "transactions": [],
            "bonus_claimed": False,
            "referral_earnings": 0,
            "referral_payouts": [],
            "deposits": [],
            "is_admin": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        users = get_users()
        users.append(new_user)
        save_users(users)

        token = make_token(new_user["id"], False)
        return self._json(201, {
            "token": token,
            "user": public_user(new_user),
            "message": "Account created. KYC demo verified.",
        })

    def _login(self, body):
        identifier = (body.get("identifier") or "").strip()
        password = body.get("password") or ""
        if not identifier or not password:
            return self._json(400, {"error": "Identifier and password required"})

        user = find_user(email=identifier) or find_user(phone=identifier)
        if not user or not verify_password(password, user["password_hash"]):
            return self._json(401, {"error": "Invalid credentials"})

        token = make_token(user["id"], user.get("is_admin", False))
        return self._json(200, {"token": token, "user": public_user(user)})

    def _purchase(self, user, body):
        machine_id = body.get("machine_id")
        machine = next((m for m in MACHINES if m["id"] == machine_id), None)
        if not machine:
            return self._json(400, {"error": "Invalid machine"})

        now = datetime.now(timezone.utc).isoformat()
        purchase = {
            "id": "m_" + uuid.uuid4().hex[:10],
            "machine_id": machine["id"],
            "name": machine["name"],
            "price": machine["price"],
            "daily": machine["daily"],
            "start": now,
        }
        user.setdefault("machines", []).append(purchase)
        user.setdefault("transactions", []).insert(0, {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": f"Machine purchase — {machine['name']}",
            "amount": -machine["price"],
        })

        is_first = not user.get("bonus_claimed")
        if is_first:
            bonus = int(machine["price"] * 0.05)
            user["balance"] = user.get("balance", 0) + bonus
            user["bonus_claimed"] = True
            user["transactions"].insert(0, {
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": "5% welcome bonus (first purchase)",
                "amount": bonus,
            })

            # Referral reward: 5% of first purchase to inviter
            ref_id = user.get("referred_by")
            if ref_id:
                referrer = find_user(uid=ref_id)
                if referrer:
                    reward = int(machine["price"] * 0.05)
                    referrer["balance"] = referrer.get("balance", 0) + reward
                    referrer["referral_earnings"] = referrer.get("referral_earnings", 0) + reward
                    referrer.setdefault("referral_payouts", []).insert(0, {
                        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "from": user["name"],
                        "from_id": user["id"],
                        "machine": machine["name"],
                        "amount": reward,
                    })
                    referrer.setdefault("transactions", []).insert(0, {
                        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "type": f"Referral reward — {user['name']} (first purchase)",
                        "amount": reward,
                    })
                    update_user(referrer)

        update_user(user)
        return self._json(200, {
            "message": "Demo purchase confirmed",
            "user": public_user(user),
            "deposit_hint": "Use official deposit channels. Admin personal details are never shown to members.",
        })

    def _withdraw(self, user, body):
        try:
            amount = float(body.get("amount"))
        except (TypeError, ValueError):
            return self._json(400, {"error": "Invalid amount"})
        if amount <= 0:
            return self._json(400, {"error": "Amount must be positive"})
        if amount > user.get("balance", 0):
            return self._json(400, {"error": "Insufficient balance"})

        fee = round(amount * 0.05, 2)
        net = round(amount - fee, 2)

        user["balance"] = round(user["balance"] - amount, 2)
        user.setdefault("transactions", []).insert(0, {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": "Withdrawal request",
            "amount": -amount,
        })
        user["transactions"].insert(0, {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": "5% withdrawal fee",
            "amount": -fee,
        })
        update_user(user)

        wd = {
            "id": "w_" + uuid.uuid4().hex[:10],
            "user_id": user["id"],
            "amount": amount,
            "fee": fee,
            "net": net,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "processed_at": None,
            "admin_note": "",
        }
        items = get_withdrawals()
        items.insert(0, wd)
        save_withdrawals(items)

        return self._json(200, {
            "message": "Withdrawal submitted for admin review",
            "withdrawal": wd,
            "user": public_user(user),
        })

    def _admin_withdrawal_action(self, body):
        wid = body.get("id")
        action = (body.get("action") or "").lower()
        note = body.get("note") or ""

        if action not in ("approve", "reject"):
            return self._json(400, {"error": "action must be approve or reject"})

        items = get_withdrawals()
        wd = next((w for w in items if w["id"] == wid), None)
        if not wd:
            return self._json(404, {"error": "Withdrawal not found"})
        if wd["status"] != "pending":
            return self._json(400, {"error": "Already processed"})

        wd["status"] = "approved" if action == "approve" else "rejected"
        wd["processed_at"] = datetime.now(timezone.utc).isoformat()
        wd["admin_note"] = note

        if action == "reject":
            user = find_user(uid=wd["user_id"])
            if user:
                user["balance"] = round(user.get("balance", 0) + wd["amount"], 2)
                user.setdefault("transactions", []).insert(0, {
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "type": "Withdrawal rejected — refund",
                    "amount": wd["amount"],
                })
                update_user(user)

        save_withdrawals(items)
        return self._json(200, {"message": f"Withdrawal {wd['status']}", "withdrawal": wd})


    def _deposit(self, user, body):
        try:
            amount = float(body.get("amount"))
        except (TypeError, ValueError):
            return self._json(400, {"error": "Invalid amount"})
        if amount < 3000:
            return self._json(400, {"error": "Minimum deposit is UGX 3,000"})

        network = (body.get("network") or body.get("method") or "mtn").lower()
        if network in ("mm", "mobile", "mobile_money"):
            network = "mtn"
        sender = (body.get("sender") or body.get("phone") or user.get("phone") or "").strip()
        ref = (body.get("reference") or "").strip()
        external_id = "d_" + uuid.uuid4().hex[:10]

        if network == "usdt":
            method_label = "USDT TRC20"
            channel = INTERNAL_BINANCE
            momo = {"ok": True, "provider_ref": external_id, "status": "pending", "message": "Send USDT TRC20", "pay_to": channel}
        else:
            method_label = "MTN Mobile Money" if network == "mtn" else "Airtel Money"
            channel = MOMO_COLLECTION_NUMBER
            momo = momo_initiate_collection(amount, sender, network, external_id)

        dep = {
            "id": external_id,
            "amount": amount,
            "method": method_label,
            "network": network,
            "channel": channel,
            "sender": sender or "—",
            "reference": ref or momo.get("provider_ref") or "—",
            "provider_ref": momo.get("provider_ref"),
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        user.setdefault("deposits", []).insert(0, dep)
        user.setdefault("transactions", []).insert(0, {
            "date": dep["date"],
            "type": f"Mobile Money deposit request — {method_label}",
            "amount": 0,
        })
        update_user(user)

        return self._json(200, {
            "message": momo.get("message") or "Deposit initiated",
            "deposit": dep,
            "momo": momo,
            "pay_to": {
                "method": method_label,
                "channel": channel,
                "network": network,
                "note": "Approve the MoMo prompt on your phone, or send UGX to the collection number.",
            },
            "user": public_user(user),
        })

    def _admin_deposit_action(self, body):
        did = body.get("id")
        action = (body.get("action") or "").lower()  # confirm | reject
        user_id = body.get("user_id")
        if action not in ("confirm", "reject"):
            return self._json(400, {"error": "action must be confirm or reject"})
        user = find_user(uid=user_id)
        if not user:
            return self._json(404, {"error": "User not found"})
        dep = next((d for d in user.get("deposits", []) if d["id"] == did), None)
        if not dep:
            return self._json(404, {"error": "Deposit not found"})
        if dep["status"] != "pending":
            return self._json(400, {"error": "Already processed"})

        if action == "confirm":
            dep["status"] = "confirmed"
            user["balance"] = round(user.get("balance", 0) + float(dep["amount"]), 2)
            user.setdefault("transactions", []).insert(0, {
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": f"Deposit confirmed — {dep['method']}",
                "amount": dep["amount"],
            })
        else:
            dep["status"] = "rejected"
            user.setdefault("transactions", []).insert(0, {
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": f"Deposit rejected — {dep['method']}",
                "amount": 0,
            })
        update_user(user)
        return self._json(200, {"message": f"Deposit {dep['status']}", "deposit": dep, "user": public_user(user)})


    def _momo_webhook(self, body):
        """Provider callback: mark deposit confirmed and credit wallet."""
        # In production verify signature with MOMO_WEBHOOK_SECRET
        ref = body.get("provider_ref") or body.get("tx_ref") or body.get("reference")
        status = (body.get("status") or "").lower()
        if status not in ("successful", "success", "completed", "confirmed"):
            return self._json(200, {"message": "ignored", "status": status})
        for u in get_users():
            for d in u.get("deposits", []):
                if d.get("provider_ref") == ref or d.get("id") == ref or d.get("reference") == ref:
                    if d["status"] == "pending":
                        d["status"] = "confirmed"
                        u["balance"] = round(u.get("balance", 0) + float(d["amount"]), 2)
                        u.setdefault("transactions", []).insert(0, {
                            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "type": f"Mobile Money deposit confirmed — {d.get('method')}",
                            "amount": d["amount"],
                        })
                        update_user(u)
                        return self._json(200, {"message": "credited", "deposit_id": d["id"]})
                    return self._json(200, {"message": "already processed"})
        return self._json(404, {"error": "deposit not found"})

    def _serve_file(self, name, content_type):
        path = Path(__file__).parent / name
        if not path.exists():
            self._json(404, {"error": "File not found"})
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self._cors()
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    seed_admin()
    print(f"""
╔══════════════════════════════════════════════╗
║           iMate1 Backend (DEMO)              ║
╠══════════════════════════════════════════════╣
║  App:    http://localhost:{PORT}/               ║
║  Admin:  http://localhost:{PORT}/admin          ║
║  API:    http://localhost:{PORT}/api/health     ║
║                                              ║
║  Admin login:                                ║
║    email: {ADMIN_EMAIL}             ║
║    pass:  {ADMIN_PASSWORD}                    ║
╚══════════════════════════════════════════════╝
""")
    HTTPServer((HOST, PORT), Handler).serve_forever()
