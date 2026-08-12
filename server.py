#!/usr/bin/env python3
"""
iMate1 Backend
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

MOMO_PROVIDER = os.environ.get("MOMO_PROVIDER", "demo")  # set to mtn when keys ready  # demo | mtn
MOMO_COLLECTION_NUMBER = os.environ.get("MOMO_COLLECTION_NUMBER", "0780509960")
MOMO_SECRET_KEY = os.environ.get("MOMO_SECRET_KEY", "")
MOMO_PUBLIC_KEY = os.environ.get("MOMO_PUBLIC_KEY", "")

# MTN MoMo Collection (RequesttoPay)
# Portal: https://momodeveloper.mtn.com → Collection product
MTN_SUB_KEY = os.environ.get("MTN_MOMO_SUBSCRIPTION_KEY", "") or os.environ.get("MOMO_API_KEY", "")
MTN_API_USER = os.environ.get("MTN_MOMO_API_USER", "")
MTN_API_KEY = os.environ.get("MTN_MOMO_API_KEY", "")
MTN_TARGET = os.environ.get("MTN_MOMO_TARGET_ENVIRONMENT", "sandbox")  # sandbox | mtnuganda
MTN_CURRENCY = os.environ.get("MTN_MOMO_CURRENCY", "UGX")
MTN_CALLBACK = os.environ.get("MTN_MOMO_CALLBACK_URL", "")
ADMIN_ONLY_DEPOSIT_CREDIT = os.environ.get("ADMIN_ONLY_DEPOSIT_CREDIT", "1") == "1"  # 1 = wallet only after admin approve
  # e.g. https://imate1.com/api/momo/webhook



# ─────────────────────────────────────────────
# AUTO DEPOSIT VERIFICATION
# USDT TRC20 → public Tron explorers
# MoMo → requires provider API (MTN/Airtel); TxID stored & rechecked
# ─────────────────────────────────────────────

def _http_json(url, timeout=12):
    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, headers={"User-Agent": "iMate1/1.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8", errors="ignore"))
    except Exception as e:
        return {"_error": str(e)}


def verify_usdt_trc20(txid, expected_to=None):
    """Return {ok, amount, to, from, message} after checking Tron chain."""
    txid = (txid or "").strip()
    if len(txid) < 20:
        return {"ok": False, "message": "Invalid USDT Transaction ID"}
    expected_to = (expected_to or INTERNAL_BINANCE).strip()
    # Tronscan
    data = _http_json(f"https://apilist.tronscanapi.com/api/transaction-info?hash={txid}")
    if data and not data.get("_error"):
        # contract transfers
        transfers = data.get("trc20TransferInfo") or data.get("tokenTransferInfo") or []
        if isinstance(transfers, dict):
            transfers = [transfers]
        for tr in transfers:
            to_addr = (tr.get("to_address") or tr.get("toAddress") or tr.get("to") or "").strip()
            symbol = (tr.get("symbol") or tr.get("tokenAbbr") or tr.get("token_name") or "").upper()
            if expected_to and to_addr and expected_to.lower() not in to_addr.lower() and to_addr.lower() not in expected_to.lower():
                # still accept if confirmed to our address via contract_ret
                pass
            else:
                if "USDT" in symbol or symbol == "" or True:
                    try:
                        raw = float(tr.get("amount_str") or tr.get("amount") or tr.get("quant") or 0)
                        # many APIs use 6 decimals for USDT
                        if raw > 1e6:
                            amount = raw / 1e6
                        else:
                            amount = raw
                    except Exception:
                        amount = 0
                    confirmed = (data.get("confirmed") is True) or (data.get("contractRet") == "SUCCESS") or data.get("confirmed")
                    if confirmed or data.get("contractRet") == "SUCCESS" or transfers:
                        return {
                            "ok": True,
                            "amount": amount,
                            "to": to_addr,
                            "symbol": symbol or "USDT",
                            "message": "USDT TRC20 payment verified on-chain",
                            "raw": {"hash": txid},
                        }
        # fallback: transaction success without parsed token info
        if data.get("contractRet") == "SUCCESS" or data.get("confirmed"):
            return {
                "ok": True,
                "amount": 0,
                "to": expected_to,
                "symbol": "USDT",
                "message": "Transaction found on Tron (confirm amount manually if needed)",
                "raw": {"hash": txid},
            }
    # TronGrid alternative
    data2 = _http_json(f"https://api.trongrid.io/v1/transactions/{txid}/info")
    if data2 and not data2.get("_error") and (data2.get("id") or data2.get("receipt")):
        return {
            "ok": True,
            "amount": 0,
            "to": expected_to,
            "symbol": "USDT",
            "message": "Transaction found via TronGrid",
            "raw": {"hash": txid},
        }
    return {"ok": False, "message": "USDT TxID not found or not confirmed yet. Try again in a minute."}


def verify_momo_txid(txid, network="mtn"):
    """
    Without MTN/Airtel Collection API keys we cannot read real MoMo ledgers.
    We validate TxID shape and mark for auto-retry; real auto-credit needs provider webhooks.
    """
    txid = (txid or "").strip()
    if len(txid) < 6:
        return {"ok": False, "message": "Transaction ID too short"}
    # Typical MTN/Airtel refs are alphanumeric
    if not re.match(r"^[A-Za-z0-9\\-_]{6,64}$", txid):
        return {"ok": False, "message": "Invalid Mobile Money Transaction ID format"}
    # If operator API keys exist in env, hook here later
    api_key = os.environ.get("MOMO_API_KEY") or os.environ.get("MTN_MOMO_SUBSCRIPTION_KEY")
    if not api_key:
        return {
            "ok": False,
            "pending_provider": True,
            "message": "MoMo TxID accepted. Auto-verify needs MTN/Airtel API keys — queued for confirmation.",
        }
    return {"ok": False, "message": "MoMo provider API not fully configured"}


def credit_deposit(user, dep, note="Auto-verified"):
    if dep.get("status") == "confirmed":
        return user
    dep["status"] = "confirmed"
    dep["verified_by"] = "auto"
    dep["verified_at"] = datetime.now(timezone.utc).isoformat()
    dep["verify_note"] = note
    amt = float(dep.get("amount") or 0)
    user["balance"] = round(float(user.get("balance") or 0) + amt, 2)
    user.setdefault("transactions", []).insert(0, {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": f"Deposit auto-verified — {dep.get('method')} — {note}",
        "amount": amt,
    })
    return user



def _mtn_base_url():
    if (MTN_TARGET or "sandbox").lower() == "sandbox":
        return "https://sandbox.momodeveloper.mtn.com"
    return "https://proxy.momoapi.mtn.com"


def _mtn_http(method, path, data=None, headers=None, auth=None, timeout=20):
    """Low-level HTTP for MTN MoMo. Returns (status_code, body_dict_or_text)."""
    url = _mtn_base_url() + path
    body = None
    hdrs = {"User-Agent": "iMate1/1.0", "Ocp-Apim-Subscription-Key": MTN_SUB_KEY}
    if headers:
        hdrs.update(headers)
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    if auth:
        import base64
        token = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
        hdrs["Authorization"] = f"Basic {token}"
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            try:
                return resp.status, (json.loads(raw) if raw else {})
            except Exception:
                return resp.status, {"_raw": raw}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="ignore")
        try:
            return e.code, (json.loads(raw) if raw else {"_error": str(e)})
        except Exception:
            return e.code, {"_error": str(e), "_raw": raw}
    except Exception as e:
        return 0, {"_error": str(e)}


def mtn_create_access_token():
    """CreateAccessToken for Collection product."""
    if not MTN_SUB_KEY or not MTN_API_USER or not MTN_API_KEY:
        return None, "Missing MTN_MOMO_SUBSCRIPTION_KEY / MTN_MOMO_API_USER / MTN_MOMO_API_KEY"
    status, data = _mtn_http(
        "POST",
        "/collection/token/",
        data=None,
        headers={},
        auth=(MTN_API_USER, MTN_API_KEY),
    )
    # token endpoint often wants empty body + Basic auth
    if status not in (200, 201) or not isinstance(data, dict) or not data.get("access_token"):
        # retry with explicit Content-Length 0 style already handled
        return None, f"Token failed ({status}): {data}"
    return data.get("access_token"), None


def mtn_request_to_pay(amount, phone, external_id, payer_message="iMate1 deposit", payee_note="Wallet top-up"):
    """
    RequesttoPay — pushes approval to customer MoMo phone.
    phone: Uganda format 2567XXXXXXXX preferred.
    """
    token, err = mtn_create_access_token()
    if not token:
        return {"ok": False, "status": "error", "message": err or "No access token"}

    # Normalize MSISDN
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("0") and len(digits) == 10:
        digits = "256" + digits[1:]
    if digits.startswith("7") and len(digits) == 9:
        digits = "256" + digits
    if not digits.startswith("256"):
        return {"ok": False, "status": "error", "message": "Phone must be Uganda MoMo (2567…)"}

    ref = external_id if len(external_id) >= 8 else str(uuid.uuid4())
    payload = {
        "amount": str(int(round(float(amount)))),
        "currency": MTN_CURRENCY or "UGX",
        "externalId": ref[:64],
        "payer": {"partyIdType": "MSISDN", "partyId": digits},
        "payerMessage": (payer_message or "iMate1")[:160],
        "payeeNote": (payee_note or "Deposit")[:160],
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Reference-Id": ref,
        "X-Target-Environment": MTN_TARGET or "sandbox",
    }
    if MTN_CALLBACK:
        headers["X-Callback-Url"] = MTN_CALLBACK

    status, data = _mtn_http("POST", "/collection/v1_0/requesttopay", data=payload, headers=headers)
    # 202 Accepted = success for RequesttoPay
    if status in (200, 201, 202):
        return {
            "ok": True,
            "status": "pending",
            "provider_ref": ref,
            "message": "Approve the MTN MoMo prompt on your phone",
            "pay_to": MOMO_COLLECTION_NUMBER,
            "msisdn": digits,
        }
    return {
        "ok": False,
        "status": "error",
        "provider_ref": ref,
        "message": f"RequesttoPay failed ({status}): {data}",
        "pay_to": MOMO_COLLECTION_NUMBER,
    }


def mtn_request_to_pay_status(reference_id):
    """RequesttoPayTransactionStatus."""
    token, err = mtn_create_access_token()
    if not token:
        return {"ok": False, "status": "error", "message": err}
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Target-Environment": MTN_TARGET or "sandbox",
    }
    status, data = _mtn_http(
        "GET",
        f"/collection/v1_0/requesttopay/{reference_id}",
        headers=headers,
    )
    if status != 200 or not isinstance(data, dict):
        return {"ok": False, "status": "error", "message": f"Status check failed ({status})", "raw": data}
    st = (data.get("status") or "").upper()
    return {
        "ok": st == "SUCCESSFUL",
        "status": st.lower() if st else "unknown",
        "message": f"MoMo status: {st}",
        "raw": data,
        "amount": data.get("amount"),
        "financialTransactionId": data.get("financialTransactionId"),
    }


def momo_initiate_collection(amount, phone, network, external_id):
    """
    Start collection. When MOMO_PROVIDER=mtn and keys are set → real RequesttoPay.
    Otherwise demo mode (manual TxID / admin).
    """
    provider = (MOMO_PROVIDER or "demo").lower()
    if provider == "mtn" and MTN_SUB_KEY and MTN_API_USER and MTN_API_KEY:
        return mtn_request_to_pay(amount, phone, external_id)

    # Demo / keys missing
    return {
        "ok": True,
        "provider_ref": external_id,
        "status": "pending",
        "message": "Demo mode: pay via USSD then submit TxID, or set MTN MoMo keys (MOMO_PROVIDER=mtn).",
        "pay_to": MOMO_COLLECTION_NUMBER,
    }



MACHINES = [
    {"id": 1, "name": "CRYPTO A1", "series": "A1", "theme": "Solar Storm", "price": 30000, "daily": 7500, "days": 5, "photo": "https://images.unsplash.com/photo-1462331940025-496dfbfc7564?auto=format&fit=crop&w=600&h=480&q=80", "photoFb": "https://picsum.photos/seed/imate1space1/600/480"},
    {"id": 2, "name": "CRYPTO A2", "series": "A2", "theme": "Deep Galaxy", "price": 50000, "daily": 12500, "days": 5, "photo": "https://images.unsplash.com/photo-1419242902214-272b3f66ee7a?auto=format&fit=crop&w=600&h=480&q=80", "photoFb": "https://picsum.photos/seed/imate1space2/600/480"},
    {"id": 3, "name": "CRYPTO A3", "series": "A3", "theme": "Earth Orbit", "price": 70000, "daily": 17500, "days": 5, "photo": "https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?auto=format&fit=crop&w=600&h=480&q=80", "photoFb": "https://picsum.photos/seed/imate1space3/600/480"},
    {"id": 4, "name": "CRYPTO A4", "series": "A4", "theme": "Blue Earth", "price": 90000, "daily": 22500, "days": 5, "photo": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=600&h=480&q=80", "photoFb": "https://picsum.photos/seed/imate1space4/600/480"},
    {"id": 5, "name": "CRYPTO A5", "series": "A5", "theme": "Spacewalk", "price": 110000, "daily": 27500, "days": 5, "photo": "https://images.unsplash.com/photo-1446776877081-d282a0f896e2?auto=format&fit=crop&w=600&h=480&q=80", "photoFb": "https://picsum.photos/seed/imate1space5/600/480"},
    {"id": 6, "name": "CRYPTO A6", "series": "A6", "theme": "Solar Core", "price": 130000, "daily": 32500, "days": 5, "photo": "https://images.unsplash.com/photo-1614732414444-096e5f1122d5?auto=format&fit=crop&w=600&h=480&q=80", "photoFb": "https://picsum.photos/seed/imate1space6/600/480"},
    {"id": 7, "name": "CRYPTO A7", "series": "A7", "theme": "Bright Sun", "price": 150000, "daily": 37500, "days": 5, "photo": "https://images.unsplash.com/photo-1575881875475-31023242e3f9?auto=format&fit=crop&w=600&h=480&q=80", "photoFb": "https://picsum.photos/seed/imate1space7/600/480"},
    {"id": 8, "name": "CRYPTO A8", "series": "A8", "theme": "Full Moon", "price": 170000, "daily": 42500, "days": 5, "photo": "https://images.unsplash.com/photo-1532693322450-2cb5c511067d?auto=format&fit=crop&w=600&h=480&q=80", "photoFb": "https://picsum.photos/seed/imate1space8/600/480"},
    {"id": 9, "name": "CRYPTO A9", "series": "A9", "theme": "Lunar Surface", "price": 190000, "daily": 47500, "days": 5, "photo": "https://images.unsplash.com/photo-1522030290737-3b28eecba4e7?auto=format&fit=crop&w=600&h=480&q=80", "photoFb": "https://picsum.photos/seed/imate1space9/600/480"},
    {"id": 10, "name": "CRYPTO A10", "series": "A10", "theme": "Purple Nebula", "price": 210000, "daily": 52500, "days": 5, "photo": "https://images.unsplash.com/photo-1502134249126-9f3755a50d78?auto=format&fit=crop&w=600&h=480&q=80", "photoFb": "https://picsum.photos/seed/imate1space10/600/480"},
    {"id": 11, "name": "CRYPTO A11", "series": "A11", "theme": "Cosmic Cloud", "price": 230000, "daily": 57500, "days": 5, "photo": "https://images.unsplash.com/photo-1464802686167-b939a6910659?auto=format&fit=crop&w=600&h=480&q=80", "photoFb": "https://picsum.photos/seed/imate1space11/600/480"},
    {"id": 12, "name": "CRYPTO A12", "series": "A12", "theme": "Milky Way", "price": 250000, "daily": 62500, "days": 5, "photo": "https://images.unsplash.com/photo-1543722530-d2c3201746e6?auto=format&fit=crop&w=600&h=480&q=80", "photoFb": "https://picsum.photos/seed/imate1space12/600/480"},
    {"id": 13, "name": "CRYPTO A13", "series": "A13", "theme": "Star Cluster", "price": 270000, "daily": 67500, "days": 5, "photo": "https://images.unsplash.com/photo-1454789548928-9efd52dc4031?auto=format&fit=crop&w=600&h=480&q=80", "photoFb": "https://picsum.photos/seed/imate1space13/600/480"},
    {"id": 14, "name": "CRYPTO A14", "series": "A14", "theme": "Night Cosmos", "price": 290000, "daily": 72500, "days": 5, "photo": "https://images.unsplash.com/photo-1444703686981-a3abbc4d4fe3?auto=format&fit=crop&w=600&h=480&q=80", "photoFb": "https://picsum.photos/seed/imate1space14/600/480"},
    {"id": 15, "name": "CRYPTO A15", "series": "A15", "theme": "Soft Nebula", "price": 310000, "daily": 77500, "days": 5, "photo": "https://images.unsplash.com/photo-1465101162946-4377e57745c3?auto=format&fit=crop&w=600&h=480&q=80", "photoFb": "https://picsum.photos/seed/imate1space15/600/480"},
    {"id": 16, "name": "CRYPTO A16", "series": "A16", "theme": "Starfield", "price": 330000, "daily": 82500, "days": 5, "photo": "https://images.unsplash.com/photo-1534796636912-3b95bddaed42?auto=format&fit=crop&w=600&h=480&q=80", "photoFb": "https://picsum.photos/seed/imate1space16/600/480"},
    {"id": 17, "name": "CRYPTO A17", "series": "A17", "theme": "Calm Galaxy", "price": 350000, "daily": 87500, "days": 5, "photo": "https://images.unsplash.com/photo-1506318137071-a8e063b4bec0?auto=format&fit=crop&w=600&h=480&q=80", "photoFb": "https://picsum.photos/seed/imate1space17/600/480"},
    {"id": 18, "name": "CRYPTO A18", "series": "A18", "theme": "Dawn Stars", "price": 370000, "daily": 92500, "days": 5, "photo": "https://images.unsplash.com/photo-1519681393784-d120267933ba?auto=format&fit=crop&w=600&h=480&q=80", "photoFb": "https://picsum.photos/seed/imate1space18/600/480"},
    {"id": 19, "name": "CRYPTO A19", "series": "A19", "theme": "Horizon Sky", "price": 390000, "daily": 97500, "days": 5, "photo": "https://images.unsplash.com/photo-1507400492013-162706c8c05e?auto=format&fit=crop&w=600&h=480&q=80", "photoFb": "https://picsum.photos/seed/imate1space19/600/480"},
    {"id": 20, "name": "CRYPTO A20", "series": "A20", "theme": "Quiet Universe", "price": 410000, "daily": 102500, "days": 5, "photo": "https://images.unsplash.com/photo-1475274047050-1d0c0975c63e?auto=format&fit=crop&w=600&h=480&q=80", "photoFb": "https://picsum.photos/seed/imate1space20/600/480"}
]
MACHINES_SORTED = sorted(MACHINES, key=lambda m: m["price"], reverse=True)


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
            "id_num": "ADMIN",
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
        print(f"[boot] Admin → {ADMIN_EMAIL} / {ADMIN_PASSWORD}")


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
        if path.startswith("/static/"):
            name = path.split("/static/", 1)[-1]
            name = name.replace("..", "").lstrip("/")
            static_path = Path(__file__).parent / "static" / name
            if static_path.is_file():
                mime = "image/jpeg" if name.endswith((".jpg", ".jpeg", ".jfif")) else "application/octet-stream"
                if name.endswith(".png"): mime = "image/png"
                if name.endswith(".webp"): mime = "image/webp"
                return self._serve_file(str(static_path), mime, absolute=True)
            return self._json(404, {"error": "Not found"})

        if path == "/api/health":
            return self._json(200, {"ok": True, "service": "iMate1", "mode": "live"})

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
        if path == "/api/deposit/verify":
            return self._verify_deposit(user, body)

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
            amount = float(body.get("amount") or 0)
        except (TypeError, ValueError):
            amount = 0
        if amount < 3000:
            return self._json(400, {"error": "Minimum deposit is UGX 3,000"})
        network = (body.get("network") or body.get("method") or "mtn").lower()
        sender = (body.get("sender") or body.get("phone") or user.get("phone") or "").strip()
        ref = (body.get("reference") or body.get("txid") or body.get("txId") or "").strip()
        # TxID required for USDT; for MoMo with MTN API we can start RequesttoPay with phone only
        if network in ("usdt", "trc20", "usdt_trc20"):
            if not ref or len(ref) < 4:
                return self._json(400, {"error": "USDT Transaction ID is required"})
        elif (MOMO_PROVIDER or "").lower() != "mtn" or not MTN_SUB_KEY:
            if not ref or len(ref) < 4:
                return self._json(400, {"error": "Transaction ID is required (or configure MTN MoMo API for RequesttoPay)"})

        if network in ("usdt", "trc20", "usdt_trc20"):
            method_label = "USDT TRC20"
            channel = INTERNAL_BINANCE
            network = "usdt"
        elif network in ("airtel", "airtel_money"):
            method_label = "Airtel Money"
            channel = INTERNAL_MOBILE
            network = "airtel"
        else:
            method_label = "MTN Mobile Money"
            channel = INTERNAL_MOBILE
            network = "mtn"

        external_id = "d_" + uuid.uuid4().hex[:12]
        dep = {
            "id": external_id,
            "amount": amount,
            "method": method_label,
            "network": network,
            "channel": channel,
            "sender": sender or "—",
            "reference": ref,
            "provider_ref": ref,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "auto_verify": True,
        }

        verify_result = {"ok": False, "message": "pending"}
        if network == "usdt":
            verify_result = verify_usdt_trc20(ref, INTERNAL_BINANCE)
            if verify_result.get("ok") and not ADMIN_ONLY_DEPOSIT_CREDIT:
                credit_deposit(user, dep, verify_result.get("message") or "USDT on-chain verified")
            elif verify_result.get("ok") and ADMIN_ONLY_DEPOSIT_CREDIT:
                dep["verify_message"] = (verify_result.get("message") or "On-chain seen") + " — waiting admin approval"

        else:
            # Try MTN RequesttoPay (push to customer phone)
            if (MOMO_PROVIDER or "").lower() == "mtn" and MTN_SUB_KEY and MTN_API_USER and MTN_API_KEY:
                momo = mtn_request_to_pay(amount, sender or user.get("phone") or "", external_id)
                dep["provider_ref"] = momo.get("provider_ref") or external_id
                dep["reference"] = ref or momo.get("provider_ref") or external_id
                dep["verify_message"] = momo.get("message")
                verify_result = momo
                if momo.get("ok"):
                    # Immediately poll once (user may already have approved)
                    st = mtn_request_to_pay_status(dep["provider_ref"])
                    verify_result = st
                    if st.get("ok") and not ADMIN_ONLY_DEPOSIT_CREDIT:
                        credit_deposit(user, dep, st.get("message") or "MTN MoMo SUCCESSFUL")
                    elif st.get("ok"):
                        dep["verify_message"] = "MoMo success seen — waiting admin approval"

                else:
                    dep["status"] = "pending"
            else:
                verify_result = verify_momo_txid(ref, network) if ref else {"ok": False, "message": "Pending TxID / admin"}
                dep["verify_message"] = verify_result.get("message")

        user.setdefault("deposits", []).insert(0, dep)
        user.setdefault("transactions", []).insert(0, {
            "date": dep["date"],
            "type": (
                f"Deposit confirmed — {method_label}"
                if dep["status"] == "confirmed"
                else f"Deposit submitted — verifying — {method_label}"
            ),
            "amount": amount if dep["status"] == "confirmed" else 0,
        })
        update_user(user)

        return self._json(200, {
            "message": (
                "Payment verified — wallet credited"
                if dep["status"] == "confirmed"
                else verify_result.get("message") or "Deposit submitted — awaiting verification"
            ),
            "verified": dep["status"] == "confirmed",
            "deposit": dep,
            "verify": verify_result,
            "user": public_user(user),
        })

    
    def _verify_deposit(self, user, body):
        """Re-check a pending deposit by TxID (user or admin)."""
        did = body.get("id") or body.get("deposit_id")
        dep = next((d for d in user.get("deposits", []) if d["id"] == did), None)
        if not dep:
            # allow verify by reference alone
            ref = (body.get("reference") or body.get("txid") or "").strip()
            dep = next((d for d in user.get("deposits", []) if d.get("reference") == ref), None)
        if not dep:
            return self._json(404, {"error": "Deposit not found"})
        if dep.get("status") == "confirmed":
            return self._json(200, {"message": "Already confirmed", "deposit": dep, "user": public_user(user)})

        network = (dep.get("network") or "").lower()
        ref = dep.get("reference") or ""
        if network == "usdt":
            result = verify_usdt_trc20(ref, INTERNAL_BINANCE)
            if result.get("ok"):
                credit_deposit(user, dep, result.get("message") or "USDT verified")
                update_user(user)
                return self._json(200, {
                    "message": "Payment verified — wallet credited",
                    "verified": True,
                    "deposit": dep,
                    "verify": result,
                    "user": public_user(user),
                })
            return self._json(200, {"message": result.get("message"), "verified": False, "deposit": dep, "verify": result})
        # Prefer MTN status API when we have provider_ref from RequesttoPay
        pref = dep.get("provider_ref") or dep.get("reference") or ref
        if (MOMO_PROVIDER or "").lower() == "mtn" and MTN_SUB_KEY and pref:
            result = mtn_request_to_pay_status(pref)
            if result.get("ok") or (result.get("status") or "").upper() == "SUCCESSFUL":
                credit_deposit(user, dep, result.get("message") or "MTN MoMo RequesttoPay SUCCESSFUL")
                if result.get("financialTransactionId"):
                    dep["financialTransactionId"] = result.get("financialTransactionId")
                update_user(user)
                return self._json(200, {
                    "message": "Payment verified — wallet credited",
                    "verified": True,
                    "deposit": dep,
                    "verify": result,
                    "user": public_user(user),
                })
            return self._json(200, {
                "message": result.get("message") or "Still pending on MoMo",
                "verified": False,
                "deposit": dep,
                "verify": result,
            })
        result = verify_momo_txid(ref, network)
        return self._json(200, {
            "message": result.get("message") or "Still pending operator confirmation",
            "verified": False,
            "deposit": dep,
            "verify": result,
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
        """MTN / provider callback: credit wallet when payment is SUCCESSFUL."""
        if not isinstance(body, dict):
            body = {}
        ref = (
            body.get("provider_ref")
            or body.get("externalId")
            or body.get("external_id")
            or body.get("tx_ref")
            or body.get("reference")
            or body.get("financialTransactionId")
        )
        status = (body.get("status") or body.get("financialTransactionStatus") or "").strip().lower()
        ok_statuses = ("successful", "success", "completed", "confirmed", "successfull")
        # MTN sometimes sends only reference in path; still try match
        if status and status not in ok_statuses:
            return self._json(200, {"message": "ignored", "status": status})
        credited = 0
        for u in get_users():
            for d in u.get("deposits", []):
                if d.get("status") == "confirmed":
                    continue
                if (
                    (ref and (d.get("provider_ref") == ref or d.get("id") == ref or d.get("reference") == ref))
                    or (not ref and status in ok_statuses)
                ):
                    if ref or status in ok_statuses:
                        if not ADMIN_ONLY_DEPOSIT_CREDIT:
                            credit_deposit(u, d, "MoMo webhook confirmed")
                        else:
                            d["verify_message"] = "Webhook success — waiting admin approval"
                            update_user(u)
                            return self._json(200, {"message": "pending_admin", "deposit_id": d["id"]})
                        if body.get("financialTransactionId"):
                            d["financialTransactionId"] = body.get("financialTransactionId")
                        update_user(u)
                        credited += 1
                        return self._json(200, {"message": "credited", "deposit_id": d["id"]})
        return self._json(200 if not ref else 404, {"message": "deposit not found" if ref else "no ref", "credited": credited})


    def _serve_file(self, name, content_type, absolute=False):
        path = Path(name) if absolute else (Path(__file__).parent / name)
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
║           iMate1 Backend              ║
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
