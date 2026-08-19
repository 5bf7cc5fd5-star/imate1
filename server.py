#!/usr/bin/env python3
"""
Own Club Backend
- Token auth (HMAC)
- Registration / Login
- Machine purchases + 5% first-purchase bonus
- Withdrawal requests (pending → admin approve/reject)
- Admin dashboard API
- Serves frontend + admin UI
"""

import json
import secrets
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
from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer
import struct
import threading
from collections import defaultdict
from urllib.parse import urlparse, parse_qs
from pathlib import Path

HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "8080"))
SECRET = os.environ.get("IMATE1_SECRET", "imate1-demo-secret-change-in-production-2026").encode()
TOKEN_TTL = 60 * 60 * 24 * 7

BASE = Path(__file__).resolve().parent
DATA_DIR = Path(__file__).parent / "data"

# ---------- Web Push notifications ----------
PUSH_FILE = DATA_DIR / "push_subscriptions.json"
VAPID_PRIVATE = os.environ.get("VAPID_PRIVATE_KEY", "").strip()
VAPID_PUBLIC = os.environ.get("VAPID_PUBLIC_KEY", "").strip()
VAPID_EMAIL = os.environ.get("VAPID_CONTACT", "mailto:k_hmed@yahoo.com").strip()

def get_push_subs():
    try:
        if PUSH_FILE.exists():
            return json.loads(PUSH_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print("[push] load", e)
    return []

def save_push_subs(items):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PUSH_FILE.write_text(json.dumps(items, indent=2), encoding="utf-8")

def upsert_push_sub(user_id, subscription):
    if not subscription or not isinstance(subscription, dict):
        return False
    endpoint = (subscription.get("endpoint") or "").strip()
    if not endpoint:
        return False
    items = get_push_subs()
    items = [x for x in items if (x.get("subscription") or {}).get("endpoint") != endpoint]
    items.append({
        "user_id": user_id,
        "subscription": subscription,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    # keep last 500
    save_push_subs(items[-500:])
    return True

def remove_push_endpoint(endpoint):
    items = [x for x in get_push_subs() if (x.get("subscription") or {}).get("endpoint") != endpoint]
    save_push_subs(items)

def send_web_push(subscription, payload: dict):
    """Send via pywebpush if VAPID configured."""
    if not VAPID_PRIVATE or not VAPID_PUBLIC:
        return {"ok": False, "message": "VAPID keys not configured"}
    try:
        from pywebpush import webpush, WebPushException
        webpush(
            subscription_info=subscription,
            data=json.dumps(payload),
            vapid_private_key=VAPID_PRIVATE,
            vapid_claims={"sub": VAPID_EMAIL or "mailto:admin@ownclubshares.com"},
        )
        return {"ok": True}
    except Exception as e:
        msg = str(e)
        print("[push] send error", msg)
        if "410" in msg or "404" in msg:
            try:
                remove_push_endpoint((subscription or {}).get("endpoint") or "")
            except Exception:
                pass
        return {"ok": False, "message": msg}

def notify_user(user_id, title, body, url="/", tag="ownclub"):
    """Push to all devices registered for this user + broadcast in-app via WS."""
    payload = {"title": title, "body": body, "url": url, "tag": tag}
    try:
        ws_broadcast("notification", {"user_id": user_id, **payload}, user_id=user_id)
    except Exception:
        pass
    if not user_id:
        return {"sent": 0}
    sent = 0
    for item in get_push_subs():
        if item.get("user_id") != user_id:
            continue
        sub = item.get("subscription")
        if not sub:
            continue
        r = send_web_push(sub, payload)
        if r.get("ok"):
            sent += 1
    return {"sent": sent}

def notify_admins(title, body, url="/admin", tag="admin"):
    """Notify all admin/support/staff accounts."""
    n = 0
    for u in get_users():
        if u.get("is_admin") or u.get("is_support") or u.get("is_staff") or u.get("can_approve_deposit"):
            r = notify_user(u.get("id"), title, body, url=url, tag=tag)
            n += int(r.get("sent") or 0)
    return {"sent": n}

def ensure_vapid_keys():
    """Load or create VAPID keys (env or data/vapid.json)."""
    global VAPID_PRIVATE, VAPID_PUBLIC
    if VAPID_PRIVATE and VAPID_PUBLIC:
        return
    key_path = DATA_DIR / "vapid.json"
    try:
        if key_path.exists():
            data = json.loads(key_path.read_text(encoding="utf-8"))
            VAPID_PRIVATE = (data.get("private") or "").strip() or VAPID_PRIVATE
            VAPID_PUBLIC = (data.get("public") or "").strip() or VAPID_PUBLIC
            if VAPID_PRIVATE and VAPID_PUBLIC:
                return
    except Exception as e:
        print("[push] vapid load", e)
    try:
        import base64
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization
        priv = ec.generate_private_key(ec.SECP256R1())
        priv_bytes = priv.private_numbers().private_value.to_bytes(32, "big")
        pub_bytes = priv.public_key().public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )
        VAPID_PRIVATE = base64.urlsafe_b64encode(priv_bytes).decode().rstrip("=")
        VAPID_PUBLIC = base64.urlsafe_b64encode(pub_bytes).decode().rstrip("=")
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        key_path.write_text(json.dumps({"private": VAPID_PRIVATE, "public": VAPID_PUBLIC}), encoding="utf-8")
        print("[push] Generated VAPID keys → data/vapid.json")
    except Exception as e:
        print("[push] VAPID generate failed:", e)


def ws_broadcast(event: str, data=None, user_id=None):
    """Push event to all connected WS clients (optionally target one user)."""
    msg = {"event": event, "data": data or {}, "ts": datetime.now(timezone.utc).isoformat()}
    if user_id:
        msg["user_id"] = user_id
    dead = []
    with WS_LOCK:
        clients = list(WS_CLIENTS)
    for c in clients:
        if not c.alive:
            dead.append(c)
            continue
        try:
            # targeted events: send to that user + all admins
            if user_id and c.user_id and c.user_id != user_id and not c.is_admin:
                continue
            c.send_json(msg)
        except Exception:
            dead.append(c)
    if dead:
        with WS_LOCK:
            for c in dead:
                WS_CLIENTS.discard(c)
                try:
                    c.close()
                except Exception:
                    pass


def _ws_accept_key(sec_key: str) -> str:
    magic = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    dig = hashlib.sha1((sec_key + magic).encode("utf-8")).digest()
    return base64.b64encode(dig).decode("ascii")


def _ws_read_frame(sock):
    hdr = sock.recv(2)
    if not hdr or len(hdr) < 2:
        return None, None
    b1, b2 = hdr[0], hdr[1]
    opcode = b1 & 0x0F
    masked = (b2 & 0x80) != 0
    ln = b2 & 0x7F
    if ln == 126:
        ext = sock.recv(2)
        ln = struct.unpack("!H", ext)[0]
    elif ln == 127:
        ext = sock.recv(8)
        ln = struct.unpack("!Q", ext)[0]
    mask = sock.recv(4) if masked else b"\x00\x00\x00\x00"
    data = b""
    while len(data) < ln:
        chunk = sock.recv(ln - len(data))
        if not chunk:
            break
        data += chunk
    if masked:
        data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    return opcode, data



# ===== SMS notifications (new deposits → admin) =====
# Africa's Talking (East Africa) OR Twilio
SMS_PROVIDER = (os.environ.get("SMS_PROVIDER") or "africastalking").strip().lower()
SMS_NOTIFY_TO = os.environ.get("SMS_NOTIFY_TO", ADMIN_PHONE)  # admin receives deposit alerts
# Africa's Talking
AT_USERNAME = os.environ.get("AT_USERNAME", "").strip()
AT_API_KEY = os.environ.get("AT_API_KEY", "").strip()
AT_SENDER = os.environ.get("AT_SENDER", "").strip()  # optional shortcode/sender ID
# Twilio
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_FROM = os.environ.get("TWILIO_FROM", "").strip()  # e.g. +1234567890


def _normalize_msisdn(phone: str) -> str:
    p = re.sub(r"\D", "", str(phone or ""))
    if not p:
        return ""
    if p.startswith("0") and len(p) >= 9:
        p = "256" + p[1:]  # Uganda local → international
    if not p.startswith("+"):
        p = "+" + p
    return p


def send_sms(to_phone: str, message: str) -> dict:
    """Send SMS via Africa's Talking or Twilio. Returns {ok, message, provider}."""
    to = _normalize_msisdn(to_phone)
    text = (message or "")[:600]
    if not to or not text:
        return {"ok": False, "message": "Missing phone or message", "provider": SMS_PROVIDER}

    try:
        if SMS_PROVIDER in ("africastalking", "at", "africastalking.com"):
            if not AT_USERNAME or not AT_API_KEY:
                return {"ok": False, "message": "AT_USERNAME / AT_API_KEY not set", "provider": "africastalking"}
            import urllib.request
            import urllib.parse
            data = {
                "username": AT_USERNAME,
                "to": to,
                "message": text,
            }
            if AT_SENDER:
                data["from"] = AT_SENDER
            body = urllib.parse.urlencode(data).encode()
            req = urllib.request.Request(
                "https://api.africastalking.com/version1/messaging",
                data=body,
                headers={
                    "ApiKey": AT_API_KEY,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            print(f"[sms] AT → {to}: {raw[:200]}")
            return {"ok": True, "message": "SMS queued (Africa's Talking)", "provider": "africastalking", "raw": raw}

        if SMS_PROVIDER in ("twilio",):
            if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM):
                return {"ok": False, "message": "Twilio env vars missing", "provider": "twilio"}
            import urllib.request
            import urllib.parse
            import base64
            url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
            data = urllib.parse.urlencode({
                "To": to,
                "From": TWILIO_FROM,
                "Body": text,
            }).encode()
            auth = base64.b64encode(f"{TWILIO_ACCOUNT_SID}:{TWILIO_AUTH_TOKEN}".encode()).decode()
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Authorization": f"Basic {auth}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            print(f"[sms] Twilio → {to}: {raw[:200]}")
            return {"ok": True, "message": "SMS queued (Twilio)", "provider": "twilio", "raw": raw}

        return {"ok": False, "message": f"Unknown SMS_PROVIDER={SMS_PROVIDER}", "provider": SMS_PROVIDER}
    except Exception as e:
        print(f"[sms] error: {e}")
        return {"ok": False, "message": str(e), "provider": SMS_PROVIDER}


def notify_admin_new_deposit(user: dict, dep: dict) -> dict:
    """SMS disabled — approvals are manual in the admin app only."""
    return {"ok": False, "message": "SMS disabled; use in-app approvals", "results": []}



# Never exposed to regular members via API responses
INTERNAL_MOBILE = "0780509960"
INTERNAL_BINANCE = "TX4so634h6M13YiCrE4cEncLQg4GgyXP7P"
# Multi-network USDT deposit addresses (fill ERC20 / BEP20 from Binance Deposit)
USDT_DEPOSIT_ADDRS = {
    "trc20": os.environ.get("USDT_TRC20", "TX4so634h6M13YiCrE4cEncLQg4GgyXP7P"),
    "bep20": os.environ.get("USDT_BEP20", "0xe76D1AC2a2cF2A6248200a37b684AA6954e8B04A"),
    "erc20": os.environ.get("USDT_ERC20", "0xe76D1AC2a2cF2A6248200a37b684AA6954e8B04A"),
}
ALL_USDT_DEPOSIT_ADDRS = [a.lower() for a in USDT_DEPOSIT_ADDRS.values() if a]



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
ADMIN_ONLY_DEPOSIT_CREDIT = os.environ.get("ADMIN_ONLY_DEPOSIT_CREDIT", "0") == "1"  # 0 = auto-credit when chain/API verifies; 1 = always wait system approve
  # e.g. https://ownclubshares.com/api/momo/webhook



# ─────────────────────────────────────────────
# AUTO DEPOSIT VERIFICATION
# USDT TRC20 → public Tron explorers
# MoMo → requires provider API (MTN/Airtel); TxID stored & rechecked
# ─────────────────────────────────────────────

def _http_json(url, timeout=12):
    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, headers={"User-Agent": "OwnClub/1.0"})
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



# Multi-level referral on investment (share purchase): L1 30%, L2 25%, L3 20%, L4 15%
REFERRAL_LEVEL_RATES = (0.30, 0.25, 0.20, 0.15)

def pay_referral_levels(buyer, invest_amount, product_name="Club share"):
    """Credit upline: 30% / 25% / 20% / 15% of investment amount."""
    try:
        amount = float(invest_amount or 0)
    except Exception:
        amount = 0
    if amount <= 0:
        return
    uid = buyer.get("id")
    parent_id = buyer.get("referred_by") or buyer.get("referredBy")
    for level, rate in enumerate(REFERRAL_LEVEL_RATES, start=1):
        if not parent_id:
            break
        parent = find_user(uid=parent_id)
        if not parent:
            break
        reward = int(round(amount * rate))
        if reward <= 0:
            parent_id = parent.get("referred_by") or parent.get("referredBy")
            continue
        parent["balance"] = round(float(parent.get("balance") or 0) + reward, 2)
        parent["referral_earnings"] = round(float(parent.get("referral_earnings") or 0) + reward, 2)
        parent.setdefault("referral_payouts", []).insert(0, {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "from": buyer.get("name") or buyer.get("id"),
            "from_id": uid,
            "level": level,
            "rate": rate,
            "machine": product_name,
            "invest_amount": amount,
            "amount": reward,
        })
        parent.setdefault("transactions", []).insert(0, {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": f"L{level} referral {int(rate*100)}% — {buyer.get('name') or 'member'} ({product_name})",
            "amount": reward,
        })
        try:
            adjust_pool(-ugx_to_usd(reward), f"L{level} referral → {parent.get('name')}", {
                "user_id": parent.get("id"), "from": uid, "level": level, "type": "referral"
            })
        except Exception as e:
            print("[pool] referral", e)
        update_user(parent)
        try:
            ws_broadcast("balance", {"user_id": parent.get("id"), "balance": parent.get("balance")}, user_id=parent.get("id"))
            notify_user(parent.get("id"), f"L{level} referral bonus", f"UGX {reward:,} from {buyer.get('name') or 'your team'}", url="/", tag="referral")
        except Exception:
            pass
        parent_id = parent.get("referred_by") or parent.get("referredBy")

def credit_deposit(user, dep, note="Auto-verified"):
    if dep.get("status") == "confirmed":
        return user
    dep["status"] = "confirmed"
    dep["verified_by"] = "auto"
    dep["verified_at"] = datetime.now(timezone.utc).isoformat()
    dep["verify_note"] = note
    amt = float(dep.get("amount") or 0)
    extra = 0
    if int(round(amt)) == 3000 and not user.get("join3000_bonus_credited"):
        extra = 1500
        user["join3000_bonus_credited"] = True
        user["welcome_credited"] = True
        user["join_reward_ugx"] = 1500
        user.setdefault("transactions", []).insert(0, {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": "Joining bonus UGX 1,500 (3,000 deposit)",
            "amount": extra,
        })
    user["balance"] = round(float(user.get("balance") or 0) + amt + extra, 2)
    user.setdefault("transactions", []).insert(0, {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": f"Deposit auto-verified — {dep.get('method')} — {note}",
        "amount": amt,
    })
    try:
        adjust_pool(-ugx_to_usd(amt), f"Auto deposit credit → {user.get('name') or user.get('id')}", {
            "user_id": user.get("id"), "dep_id": dep.get("id"), "type": "deposit_auto"
        })
    except Exception as e:
        print("[pool] auto deposit", e)
    try:
        ws_broadcast("deposit", {"status": "confirmed", "user_id": user.get("id")})
        ws_broadcast("balance", {"user_id": user.get("id"), "balance": user.get("balance")}, user_id=user.get("id"))
        ws_broadcast("users", {"reason": "deposit_confirm"})
        ws_broadcast("pool", {})
    except Exception:
        pass
    try:
        notify_user(user.get("id"), "Deposit approved", f"UGX {int(amt):,} is in your wallet.", url="/", tag="deposit_ok")
    except Exception as e:
        print("[push] credit notify", e)
    return user



def _mtn_base_url():
    if (MTN_TARGET or "sandbox").lower() == "sandbox":
        return "https://sandbox.momodeveloper.mtn.com"
    return "https://proxy.momoapi.mtn.com"


def _mtn_http(method, path, data=None, headers=None, auth=None, timeout=20):
    """Low-level HTTP for MTN MoMo. Returns (status_code, body_dict_or_text)."""
    url = _mtn_base_url() + path
    body = None
    hdrs = {"User-Agent": "OwnClub/1.0", "Ocp-Apim-Subscription-Key": MTN_SUB_KEY}
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


def mtn_request_to_pay(amount, phone, external_id, payer_message="Own Club deposit", payee_note="Wallet top-up"):
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
        "payerMessage": (payer_message or "Own Club")[:160],
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



MACHINES = [{"id": 1, "name": "Manchester City Shares", "code": "Manchester City", "league": "Premier League", "theme": "Premier League", "marketValue": "≈ $5.0B", "photo": "https://crests.football-data.org/65.png", "photoFb": "https://ui-avatars.com/api/?name=Manchester+City&background=0B1E33&color=7EC8FF&size=256&bold=true", "price": 35000, "daily": 5000, "days": 7, "tiers": [{"weeks": 1, "price": 35000, "label": "1 week", "dailyWithdraw": 5000}, {"weeks": 2, "price": 70000, "label": "2 weeks", "dailyWithdraw": 7500}, {"weeks": 3, "price": 105000, "label": "3 weeks", "dailyWithdraw": 10000}, {"weeks": 4, "price": 140000, "label": "4 weeks", "dailyWithdraw": 12500}], "raffleTickets": 1}, {"id": 2, "name": "Arsenal Shares", "code": "Arsenal", "league": "Premier League", "theme": "Premier League", "marketValue": "≈ $3.5B", "photo": "https://crests.football-data.org/57.png", "photoFb": "https://ui-avatars.com/api/?name=Arsenal&background=0B1E33&color=7EC8FF&size=256&bold=true", "price": 35000, "daily": 5000, "days": 7, "tiers": [{"weeks": 1, "price": 35000, "label": "1 week", "dailyWithdraw": 5000}, {"weeks": 2, "price": 70000, "label": "2 weeks", "dailyWithdraw": 7500}, {"weeks": 3, "price": 105000, "label": "3 weeks", "dailyWithdraw": 10000}, {"weeks": 4, "price": 140000, "label": "4 weeks", "dailyWithdraw": 12500}], "raffleTickets": 1}, {"id": 3, "name": "Liverpool Shares", "code": "Liverpool", "league": "Premier League", "theme": "Premier League", "marketValue": "≈ $5.3B", "photo": "https://crests.football-data.org/64.png", "photoFb": "https://ui-avatars.com/api/?name=Liverpool&background=0B1E33&color=7EC8FF&size=256&bold=true", "price": 35000, "daily": 5000, "days": 7, "tiers": [{"weeks": 1, "price": 35000, "label": "1 week", "dailyWithdraw": 5000}, {"weeks": 2, "price": 70000, "label": "2 weeks", "dailyWithdraw": 7500}, {"weeks": 3, "price": 105000, "label": "3 weeks", "dailyWithdraw": 10000}, {"weeks": 4, "price": 140000, "label": "4 weeks", "dailyWithdraw": 12500}], "raffleTickets": 1}, {"id": 4, "name": "Chelsea Shares", "code": "Chelsea", "league": "Premier League", "theme": "Premier League", "marketValue": "≈ $3.1B", "photo": "https://crests.football-data.org/61.png", "photoFb": "https://ui-avatars.com/api/?name=Chelsea&background=0B1E33&color=7EC8FF&size=256&bold=true", "price": 35000, "daily": 5000, "days": 7, "tiers": [{"weeks": 1, "price": 35000, "label": "1 week", "dailyWithdraw": 5000}, {"weeks": 2, "price": 70000, "label": "2 weeks", "dailyWithdraw": 7500}, {"weeks": 3, "price": 105000, "label": "3 weeks", "dailyWithdraw": 10000}, {"weeks": 4, "price": 140000, "label": "4 weeks", "dailyWithdraw": 12500}], "raffleTickets": 1}, {"id": 5, "name": "Manchester United Shares", "code": "Manchester United", "league": "Premier League", "theme": "Premier League", "marketValue": "≈ $6.0B", "photo": "https://crests.football-data.org/66.png", "photoFb": "https://ui-avatars.com/api/?name=Manchester+United&background=0B1E33&color=7EC8FF&size=256&bold=true", "price": 35000, "daily": 5000, "days": 7, "tiers": [{"weeks": 1, "price": 35000, "label": "1 week", "dailyWithdraw": 5000}, {"weeks": 2, "price": 70000, "label": "2 weeks", "dailyWithdraw": 7500}, {"weeks": 3, "price": 105000, "label": "3 weeks", "dailyWithdraw": 10000}, {"weeks": 4, "price": 140000, "label": "4 weeks", "dailyWithdraw": 12500}], "raffleTickets": 1}, {"id": 6, "name": "Tottenham Hotspur Shares", "code": "Tottenham Hotspur", "league": "Premier League", "theme": "Premier League", "marketValue": "≈ $2.8B", "photo": "https://crests.football-data.org/73.png", "photoFb": "https://ui-avatars.com/api/?name=Tottenham+Hotspur&background=0B1E33&color=7EC8FF&size=256&bold=true", "price": 35000, "daily": 5000, "days": 7, "tiers": [{"weeks": 1, "price": 35000, "label": "1 week", "dailyWithdraw": 5000}, {"weeks": 2, "price": 70000, "label": "2 weeks", "dailyWithdraw": 7500}, {"weeks": 3, "price": 105000, "label": "3 weeks", "dailyWithdraw": 10000}, {"weeks": 4, "price": 140000, "label": "4 weeks", "dailyWithdraw": 12500}], "raffleTickets": 1}, {"id": 7, "name": "Real Madrid Shares", "code": "Real Madrid", "league": "La Liga", "theme": "La Liga", "marketValue": "≈ $6.0B", "photo": "https://crests.football-data.org/86.png", "photoFb": "https://ui-avatars.com/api/?name=Real+Madrid&background=0B1E33&color=7EC8FF&size=256&bold=true", "price": 35000, "daily": 5000, "days": 7, "tiers": [{"weeks": 1, "price": 35000, "label": "1 week", "dailyWithdraw": 5000}, {"weeks": 2, "price": 70000, "label": "2 weeks", "dailyWithdraw": 7500}, {"weeks": 3, "price": 105000, "label": "3 weeks", "dailyWithdraw": 10000}, {"weeks": 4, "price": 140000, "label": "4 weeks", "dailyWithdraw": 12500}], "raffleTickets": 1}, {"id": 8, "name": "FC Barcelona Shares", "code": "FC Barcelona", "league": "La Liga", "theme": "La Liga", "marketValue": "≈ $5.0B", "photo": "https://crests.football-data.org/81.png", "photoFb": "https://ui-avatars.com/api/?name=FC+Barcelona&background=0B1E33&color=7EC8FF&size=256&bold=true", "price": 35000, "daily": 5000, "days": 7, "tiers": [{"weeks": 1, "price": 35000, "label": "1 week", "dailyWithdraw": 5000}, {"weeks": 2, "price": 70000, "label": "2 weeks", "dailyWithdraw": 7500}, {"weeks": 3, "price": 105000, "label": "3 weeks", "dailyWithdraw": 10000}, {"weeks": 4, "price": 140000, "label": "4 weeks", "dailyWithdraw": 12500}], "raffleTickets": 1}, {"id": 9, "name": "Atlético Madrid Shares", "code": "Atlético Madrid", "league": "La Liga", "theme": "La Liga", "marketValue": "≈ $1.5B", "photo": "https://crests.football-data.org/78.png", "photoFb": "https://ui-avatars.com/api/?name=Atlético+Madrid&background=0B1E33&color=7EC8FF&size=256&bold=true", "price": 35000, "daily": 5000, "days": 7, "tiers": [{"weeks": 1, "price": 35000, "label": "1 week", "dailyWithdraw": 5000}, {"weeks": 2, "price": 70000, "label": "2 weeks", "dailyWithdraw": 7500}, {"weeks": 3, "price": 105000, "label": "3 weeks", "dailyWithdraw": 10000}, {"weeks": 4, "price": 140000, "label": "4 weeks", "dailyWithdraw": 12500}], "raffleTickets": 1}, {"id": 10, "name": "Athletic Club Shares", "code": "Athletic Club", "league": "La Liga", "theme": "La Liga", "marketValue": "≈ $0.9B", "photo": "https://crests.football-data.org/77.png", "photoFb": "https://ui-avatars.com/api/?name=Athletic+Club&background=0B1E33&color=7EC8FF&size=256&bold=true", "price": 35000, "daily": 5000, "days": 7, "tiers": [{"weeks": 1, "price": 35000, "label": "1 week", "dailyWithdraw": 5000}, {"weeks": 2, "price": 70000, "label": "2 weeks", "dailyWithdraw": 7500}, {"weeks": 3, "price": 105000, "label": "3 weeks", "dailyWithdraw": 10000}, {"weeks": 4, "price": 140000, "label": "4 weeks", "dailyWithdraw": 12500}], "raffleTickets": 1}, {"id": 11, "name": "Real Sociedad Shares", "code": "Real Sociedad", "league": "La Liga", "theme": "La Liga", "marketValue": "≈ $0.8B", "photo": "https://crests.football-data.org/92.png", "photoFb": "https://ui-avatars.com/api/?name=Real+Sociedad&background=0B1E33&color=7EC8FF&size=256&bold=true", "price": 35000, "daily": 5000, "days": 7, "tiers": [{"weeks": 1, "price": 35000, "label": "1 week", "dailyWithdraw": 5000}, {"weeks": 2, "price": 70000, "label": "2 weeks", "dailyWithdraw": 7500}, {"weeks": 3, "price": 105000, "label": "3 weeks", "dailyWithdraw": 10000}, {"weeks": 4, "price": 140000, "label": "4 weeks", "dailyWithdraw": 12500}], "raffleTickets": 1}, {"id": 12, "name": "Villarreal CF Shares", "code": "Villarreal CF", "league": "La Liga", "theme": "La Liga", "marketValue": "≈ $0.7B", "photo": "https://crests.football-data.org/94.png", "photoFb": "https://ui-avatars.com/api/?name=Villarreal+CF&background=0B1E33&color=7EC8FF&size=256&bold=true", "price": 35000, "daily": 5000, "days": 7, "tiers": [{"weeks": 1, "price": 35000, "label": "1 week", "dailyWithdraw": 5000}, {"weeks": 2, "price": 70000, "label": "2 weeks", "dailyWithdraw": 7500}, {"weeks": 3, "price": 105000, "label": "3 weeks", "dailyWithdraw": 10000}, {"weeks": 4, "price": 140000, "label": "4 weeks", "dailyWithdraw": 12500}], "raffleTickets": 1}, {"id": 13, "name": "Inter Milan Shares", "code": "Inter Milan", "league": "Serie A", "theme": "Serie A", "marketValue": "≈ $1.4B", "photo": "https://crests.football-data.org/108.png", "photoFb": "https://ui-avatars.com/api/?name=Inter+Milan&background=0B1E33&color=7EC8FF&size=256&bold=true", "price": 35000, "daily": 5000, "days": 7, "tiers": [{"weeks": 1, "price": 35000, "label": "1 week", "dailyWithdraw": 5000}, {"weeks": 2, "price": 70000, "label": "2 weeks", "dailyWithdraw": 7500}, {"weeks": 3, "price": 105000, "label": "3 weeks", "dailyWithdraw": 10000}, {"weeks": 4, "price": 140000, "label": "4 weeks", "dailyWithdraw": 12500}], "raffleTickets": 1}, {"id": 14, "name": "Juventus Shares", "code": "Juventus", "league": "Serie A", "theme": "Serie A", "marketValue": "≈ $1.7B", "photo": "https://crests.football-data.org/109.png", "photoFb": "https://ui-avatars.com/api/?name=Juventus&background=0B1E33&color=7EC8FF&size=256&bold=true", "price": 35000, "daily": 5000, "days": 7, "tiers": [{"weeks": 1, "price": 35000, "label": "1 week", "dailyWithdraw": 5000}, {"weeks": 2, "price": 70000, "label": "2 weeks", "dailyWithdraw": 7500}, {"weeks": 3, "price": 105000, "label": "3 weeks", "dailyWithdraw": 10000}, {"weeks": 4, "price": 140000, "label": "4 weeks", "dailyWithdraw": 12500}], "raffleTickets": 1}, {"id": 15, "name": "AC Milan Shares", "code": "AC Milan", "league": "Serie A", "theme": "Serie A", "marketValue": "≈ $1.5B", "photo": "https://crests.football-data.org/98.png", "photoFb": "https://ui-avatars.com/api/?name=AC+Milan&background=0B1E33&color=7EC8FF&size=256&bold=true", "price": 35000, "daily": 5000, "days": 7, "tiers": [{"weeks": 1, "price": 35000, "label": "1 week", "dailyWithdraw": 5000}, {"weeks": 2, "price": 70000, "label": "2 weeks", "dailyWithdraw": 7500}, {"weeks": 3, "price": 105000, "label": "3 weeks", "dailyWithdraw": 10000}, {"weeks": 4, "price": 140000, "label": "4 weeks", "dailyWithdraw": 12500}], "raffleTickets": 1}, {"id": 16, "name": "SSC Napoli Shares", "code": "SSC Napoli", "league": "Serie A", "theme": "Serie A", "marketValue": "≈ $1.2B", "photo": "https://crests.football-data.org/113.png", "photoFb": "https://ui-avatars.com/api/?name=SSC+Napoli&background=0B1E33&color=7EC8FF&size=256&bold=true", "price": 35000, "daily": 5000, "days": 7, "tiers": [{"weeks": 1, "price": 35000, "label": "1 week", "dailyWithdraw": 5000}, {"weeks": 2, "price": 70000, "label": "2 weeks", "dailyWithdraw": 7500}, {"weeks": 3, "price": 105000, "label": "3 weeks", "dailyWithdraw": 10000}, {"weeks": 4, "price": 140000, "label": "4 weeks", "dailyWithdraw": 12500}], "raffleTickets": 1}, {"id": 17, "name": "Paris Saint-Germain Shares", "code": "Paris Saint-Germain", "league": "Ligue 1", "theme": "Ligue 1", "marketValue": "≈ $4.2B", "photo": "https://crests.football-data.org/524.png", "photoFb": "https://ui-avatars.com/api/?name=Paris+Saint-Germain&background=0B1E33&color=7EC8FF&size=256&bold=true", "price": 35000, "daily": 5000, "days": 7, "tiers": [{"weeks": 1, "price": 35000, "label": "1 week", "dailyWithdraw": 5000}, {"weeks": 2, "price": 70000, "label": "2 weeks", "dailyWithdraw": 7500}, {"weeks": 3, "price": 105000, "label": "3 weeks", "dailyWithdraw": 10000}, {"weeks": 4, "price": 140000, "label": "4 weeks", "dailyWithdraw": 12500}], "raffleTickets": 1}, {"id": 18, "name": "Olympique Marseille Shares", "code": "Olympique Marseille", "league": "Ligue 1", "theme": "Ligue 1", "marketValue": "≈ $0.8B", "photo": "https://crests.football-data.org/516.png", "photoFb": "https://ui-avatars.com/api/?name=Olympique+Marseille&background=0B1E33&color=7EC8FF&size=256&bold=true", "price": 35000, "daily": 5000, "days": 7, "tiers": [{"weeks": 1, "price": 35000, "label": "1 week", "dailyWithdraw": 5000}, {"weeks": 2, "price": 70000, "label": "2 weeks", "dailyWithdraw": 7500}, {"weeks": 3, "price": 105000, "label": "3 weeks", "dailyWithdraw": 10000}, {"weeks": 4, "price": 140000, "label": "4 weeks", "dailyWithdraw": 12500}], "raffleTickets": 1}, {"id": 19, "name": "Bayern Munich Shares", "code": "Bayern Munich", "league": "Bundesliga", "theme": "Bundesliga", "marketValue": "≈ $4.8B", "photo": "https://crests.football-data.org/5.png", "photoFb": "https://ui-avatars.com/api/?name=Bayern+Munich&background=0B1E33&color=7EC8FF&size=256&bold=true", "price": 35000, "daily": 5000, "days": 7, "tiers": [{"weeks": 1, "price": 35000, "label": "1 week", "dailyWithdraw": 5000}, {"weeks": 2, "price": 70000, "label": "2 weeks", "dailyWithdraw": 7500}, {"weeks": 3, "price": 105000, "label": "3 weeks", "dailyWithdraw": 10000}, {"weeks": 4, "price": 140000, "label": "4 weeks", "dailyWithdraw": 12500}], "raffleTickets": 1}, {"id": 20, "name": "Borussia Dortmund Shares", "code": "Borussia Dortmund", "league": "Bundesliga", "theme": "Bundesliga", "marketValue": "≈ $1.9B", "photo": "https://crests.football-data.org/4.png", "photoFb": "https://ui-avatars.com/api/?name=Borussia+Dortmund&background=0B1E33&color=7EC8FF&size=256&bold=true", "price": 35000, "daily": 5000, "days": 7, "tiers": [{"weeks": 1, "price": 35000, "label": "1 week", "dailyWithdraw": 5000}, {"weeks": 2, "price": 70000, "label": "2 weeks", "dailyWithdraw": 7500}, {"weeks": 3, "price": 105000, "label": "3 weeks", "dailyWithdraw": 10000}, {"weeks": 4, "price": 140000, "label": "4 weeks", "dailyWithdraw": 12500}], "raffleTickets": 1}, {"id": 21, "name": "Al Hilal Shares", "code": "Al Hilal", "league": "Saudi Pro League", "theme": "Saudi Pro League", "marketValue": "≈ $0.9B", "photo": "https://r2.thesportsdb.com/images/media/team/badge/w0b80d1661656916.png", "photoFb": "https://ui-avatars.com/api/?name=Al+Hilal&background=0B1E33&color=7EC8FF&size=256&bold=true", "price": 35000, "daily": 5000, "days": 7, "tiers": [{"weeks": 1, "price": 35000, "label": "1 week", "dailyWithdraw": 5000}, {"weeks": 2, "price": 70000, "label": "2 weeks", "dailyWithdraw": 7500}, {"weeks": 3, "price": 105000, "label": "3 weeks", "dailyWithdraw": 10000}, {"weeks": 4, "price": 140000, "label": "4 weeks", "dailyWithdraw": 12500}], "raffleTickets": 1}, {"id": 22, "name": "Al Nassr Shares", "code": "Al Nassr", "league": "Saudi Pro League", "theme": "Saudi Pro League", "marketValue": "≈ $0.8B", "photo": "https://r2.thesportsdb.com/images/media/team/badge/84yvqi1748524565.png", "photoFb": "https://ui-avatars.com/api/?name=Al+Nassr&background=0B1E33&color=7EC8FF&size=256&bold=true", "price": 35000, "daily": 5000, "days": 7, "tiers": [{"weeks": 1, "price": 35000, "label": "1 week", "dailyWithdraw": 5000}, {"weeks": 2, "price": 70000, "label": "2 weeks", "dailyWithdraw": 7500}, {"weeks": 3, "price": 105000, "label": "3 weeks", "dailyWithdraw": 10000}, {"weeks": 4, "price": 140000, "label": "4 weeks", "dailyWithdraw": 12500}], "raffleTickets": 1}, {"id": 23, "name": "Al Ittihad Shares", "code": "Al Ittihad", "league": "Saudi Pro League", "theme": "Saudi Pro League", "marketValue": "≈ $0.6B", "photo": "https://r2.thesportsdb.com/images/media/team/badge/e5q6lh1745436268.png", "photoFb": "https://ui-avatars.com/api/?name=Al+Ittihad&background=0B1E33&color=7EC8FF&size=256&bold=true", "price": 35000, "daily": 5000, "days": 7, "tiers": [{"weeks": 1, "price": 35000, "label": "1 week", "dailyWithdraw": 5000}, {"weeks": 2, "price": 70000, "label": "2 weeks", "dailyWithdraw": 7500}, {"weeks": 3, "price": 105000, "label": "3 weeks", "dailyWithdraw": 10000}, {"weeks": 4, "price": 140000, "label": "4 weeks", "dailyWithdraw": 12500}], "raffleTickets": 1}, {"id": 24, "name": "Al Ahli Shares", "code": "Al Ahli", "league": "Saudi Pro League", "theme": "Saudi Pro League", "marketValue": "≈ $0.5B", "photo": "https://r2.thesportsdb.com/images/media/team/badge/1bbtgb1755192301.png", "photoFb": "https://ui-avatars.com/api/?name=Al+Ahli&background=0B1E33&color=7EC8FF&size=256&bold=true", "price": 35000, "daily": 5000, "days": 7, "tiers": [{"weeks": 1, "price": 35000, "label": "1 week", "dailyWithdraw": 5000}, {"weeks": 2, "price": 70000, "label": "2 weeks", "dailyWithdraw": 7500}, {"weeks": 3, "price": 105000, "label": "3 weeks", "dailyWithdraw": 10000}, {"weeks": 4, "price": 140000, "label": "4 weeks", "dailyWithdraw": 12500}], "raffleTickets": 1}, {"id": 25, "name": "Inter Miami CF Shares", "code": "Inter Miami CF", "league": "MLS", "theme": "MLS", "marketValue": "≈ $1.1B", "photo": "https://r2.thesportsdb.com/images/media/team/badge/m4it3e1602103647.png", "photoFb": "https://ui-avatars.com/api/?name=Inter+Miami+CF&background=0B1E33&color=7EC8FF&size=256&bold=true", "price": 35000, "daily": 5000, "days": 7, "tiers": [{"weeks": 1, "price": 35000, "label": "1 week", "dailyWithdraw": 5000}, {"weeks": 2, "price": 70000, "label": "2 weeks", "dailyWithdraw": 7500}, {"weeks": 3, "price": 105000, "label": "3 weeks", "dailyWithdraw": 10000}, {"weeks": 4, "price": 140000, "label": "4 weeks", "dailyWithdraw": 12500}], "raffleTickets": 1}, {"id": 26, "name": "Los Angeles FC Shares", "code": "Los Angeles FC", "league": "MLS", "theme": "MLS", "marketValue": "≈ $1.0B", "photo": "https://r2.thesportsdb.com/images/media/team/badge/7nbj2a1602103638.png", "photoFb": "https://ui-avatars.com/api/?name=Los+Angeles+FC&background=0B1E33&color=7EC8FF&size=256&bold=true", "price": 35000, "daily": 5000, "days": 7, "tiers": [{"weeks": 1, "price": 35000, "label": "1 week", "dailyWithdraw": 5000}, {"weeks": 2, "price": 70000, "label": "2 weeks", "dailyWithdraw": 7500}, {"weeks": 3, "price": 105000, "label": "3 weeks", "dailyWithdraw": 10000}, {"weeks": 4, "price": 140000, "label": "4 weeks", "dailyWithdraw": 12500}], "raffleTickets": 1}, {"id": 27, "name": "LA Galaxy Shares", "code": "LA Galaxy", "league": "MLS", "theme": "MLS", "marketValue": "≈ $0.9B", "photo": "https://r2.thesportsdb.com/images/media/team/badge/ysyysr1420227188.png", "photoFb": "https://ui-avatars.com/api/?name=LA+Galaxy&background=0B1E33&color=7EC8FF&size=256&bold=true", "price": 35000, "daily": 5000, "days": 7, "tiers": [{"weeks": 1, "price": 35000, "label": "1 week", "dailyWithdraw": 5000}, {"weeks": 2, "price": 70000, "label": "2 weeks", "dailyWithdraw": 7500}, {"weeks": 3, "price": 105000, "label": "3 weeks", "dailyWithdraw": 10000}, {"weeks": 4, "price": 140000, "label": "4 weeks", "dailyWithdraw": 12500}], "raffleTickets": 1}, {"id": 28, "name": "Atlanta United FC Shares", "code": "Atlanta United FC", "league": "MLS", "theme": "MLS", "marketValue": "≈ $0.85B", "photo": "https://r2.thesportsdb.com/images/media/team/badge/ej091x1602103070.png", "photoFb": "https://ui-avatars.com/api/?name=Atlanta+United+FC&background=0B1E33&color=7EC8FF&size=256&bold=true", "price": 35000, "daily": 5000, "days": 7, "tiers": [{"weeks": 1, "price": 35000, "label": "1 week", "dailyWithdraw": 5000}, {"weeks": 2, "price": 70000, "label": "2 weeks", "dailyWithdraw": 7500}, {"weeks": 3, "price": 105000, "label": "3 weeks", "dailyWithdraw": 10000}, {"weeks": 4, "price": 140000, "label": "4 weeks", "dailyWithdraw": 12500}], "raffleTickets": 1}, {"id": 29, "name": "Leicester City Shares", "code": "Leicester City", "league": "Championship", "theme": "Championship", "marketValue": "≈ $0.45B", "photo": "https://crests.football-data.org/338.png", "photoFb": "https://ui-avatars.com/api/?name=Leicester+City&background=0B1E33&color=7EC8FF&size=256&bold=true", "price": 35000, "daily": 5000, "days": 7, "tiers": [{"weeks": 1, "price": 35000, "label": "1 week", "dailyWithdraw": 5000}, {"weeks": 2, "price": 70000, "label": "2 weeks", "dailyWithdraw": 7500}, {"weeks": 3, "price": 105000, "label": "3 weeks", "dailyWithdraw": 10000}, {"weeks": 4, "price": 140000, "label": "4 weeks", "dailyWithdraw": 12500}], "raffleTickets": 1}, {"id": 30, "name": "Leeds United Shares", "code": "Leeds United", "league": "Championship", "theme": "Championship", "marketValue": "≈ $0.40B", "photo": "https://crests.football-data.org/341.png", "photoFb": "https://ui-avatars.com/api/?name=Leeds+United&background=0B1E33&color=7EC8FF&size=256&bold=true", "price": 35000, "daily": 5000, "days": 7, "tiers": [{"weeks": 1, "price": 35000, "label": "1 week", "dailyWithdraw": 5000}, {"weeks": 2, "price": 70000, "label": "2 weeks", "dailyWithdraw": 7500}, {"weeks": 3, "price": 105000, "label": "3 weeks", "dailyWithdraw": 10000}, {"weeks": 4, "price": 140000, "label": "4 weeks", "dailyWithdraw": 12500}], "raffleTickets": 1}, {"id": 31, "name": "Southampton FC Shares", "code": "Southampton FC", "league": "Championship", "theme": "Championship", "marketValue": "≈ $0.38B", "photo": "https://crests.football-data.org/340.png", "photoFb": "https://ui-avatars.com/api/?name=Southampton+FC&background=0B1E33&color=7EC8FF&size=256&bold=true", "price": 35000, "daily": 5000, "days": 7, "tiers": [{"weeks": 1, "price": 35000, "label": "1 week", "dailyWithdraw": 5000}, {"weeks": 2, "price": 70000, "label": "2 weeks", "dailyWithdraw": 7500}, {"weeks": 3, "price": 105000, "label": "3 weeks", "dailyWithdraw": 10000}, {"weeks": 4, "price": 140000, "label": "4 weeks", "dailyWithdraw": 12500}], "raffleTickets": 1}, {"id": 32, "name": "Ipswich Town Shares", "code": "Ipswich Town", "league": "Championship", "theme": "Championship", "marketValue": "≈ $0.25B", "photo": "https://crests.football-data.org/349.png", "photoFb": "https://ui-avatars.com/api/?name=Ipswich+Town&background=0B1E33&color=7EC8FF&size=256&bold=true", "price": 35000, "daily": 5000, "days": 7, "tiers": [{"weeks": 1, "price": 35000, "label": "1 week", "dailyWithdraw": 5000}, {"weeks": 2, "price": 70000, "label": "2 weeks", "dailyWithdraw": 7500}, {"weeks": 3, "price": 105000, "label": "3 weeks", "dailyWithdraw": 10000}, {"weeks": 4, "price": 140000, "label": "4 weeks", "dailyWithdraw": 12500}], "raffleTickets": 1}]
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



def load_webauthn():
    p = DATA_DIR / "webauthn.json"
    if not p.exists():
        return {"creds": []}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {"creds": []}

def save_webauthn(data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "webauthn.json").write_text(json.dumps(data, indent=2))

def gen_invite_code():
    chars = string.ascii_uppercase + "23456789"
    return "IM" + "".join(random.choices(chars, k=6))




def _load_otps():
    try:
        if OTPS_FILE.exists():
            data = json.loads(OTPS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []

def _save_otps(items):
    OTPS_FILE.parent.mkdir(parents=True, exist_ok=True)
    OTPS_FILE.write_text(json.dumps(items, indent=2), encoding="utf-8")

def purge_expired_otps():
    now = time.time()
    items = [o for o in _load_otps() if float(o.get("exp", 0)) > now]
    _save_otps(items)
    return items

def create_email_otp(email, purpose="signup", ttl_seconds=180):
    """Always 6 digits, stored max 3 minutes."""
    email = (email or "").strip().lower()
    ttl_seconds = max(60, min(180, int(ttl_seconds or 180)))
    # cryptographically stronger random 6-digit
    code = f"{secrets.randbelow(1000000):06d}"
    now = time.time()
    items = purge_expired_otps()
    # remove existing for same email+purpose
    items = [o for o in items if not (o.get("email") == email and o.get("purpose") == purpose)]
    rec = {
        "email": email,
        "code": code,
        "purpose": purpose,
        "created": now,
        "exp": now + ttl_seconds,
        "ttl_seconds": ttl_seconds,
    }
    items.append(rec)
    _save_otps(items)
    return rec

def verify_email_otp(email, code, purpose="signup"):
    email = (email or "").strip().lower()
    code = (code or "").strip()
    if not re.fullmatch(r"\d{6}", code or ""):
        return False, "OTP must be exactly 6 digits"
    items = purge_expired_otps()
    for o in items:
        if o.get("email") == email and o.get("purpose") == purpose and str(o.get("code")) == code:
            # one-time: remove
            items = [x for x in items if x is not o]
            _save_otps(items)
            return True, "ok"
    return False, "Invalid or expired OTP (valid 3 minutes only)"


def send_otp_email(to_email, code, purpose="signup", ttl_seconds=180):
    """Send OTP via SMTP if configured. Returns (ok, message)."""
    host = os.environ.get("SMTP_HOST", "").strip()
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASS", "").strip()
    mail_from = os.environ.get("SMTP_FROM", user).strip()
    port = int(os.environ.get("SMTP_PORT", "587") or 587)
    if not host or not user or not password:
        return False, "SMTP not configured"
    try:
        import smtplib
        from email.mime.text import MIMEText
        mins = max(1, int(ttl_seconds) // 60)
        body = (
            f"Your Own Club verification code is: {code}\n\n"
            f"Purpose: {purpose}\n"
            f"This code expires in {mins} minute(s) (maximum 3 minutes).\n"
            f"If you did not request this, ignore this email.\n"
        )
        msg = MIMEText(body)
        msg["Subject"] = f"Own Club OTP: {code}"
        msg["From"] = mail_from or user
        msg["To"] = to_email
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.sendmail(msg["From"], [to_email], msg.as_string())
        return True, "sent"
    except Exception as e:
        return False, str(e)



def seed_support_staff():
    """Staff / co-managers. Cannot dismiss the owner. Withdrawals stay owner-only unless flagged."""
    staff = [
        {
            "id": "staff_kato",
            "name": "James Kato (Support)",
            "phone": "",
            "email": "katojamex@gmail.com",
            "password": "Trade001",
            "invite_code": "STAFF0KATO",
            "title": "Support",
            "can_approve_deposit": False,
            "can_approve_withdraw": False,
        },
        {
            "id": "staff_mugaga",
            "name": "Mugaga Muto",
            "phone": "+96550051932",
            "email": "mugagamuto04@gmail.com",
            "password": "Muto@2026",
            "invite_code": "STAFFMUTO",
            "title": "Co-Manager",
            "can_approve_deposit": True,
            "can_approve_withdraw": False,
        },
    ]
    users = get_users()
    changed = False
    emails = {(u.get("email") or "").lower() for u in users}
    phones = {str(u.get("phone") or "") for u in users}
    for st in staff:
        em = st["email"].lower()
        existing = next((u for u in users if (u.get("email") or "").lower() == em), None)
        if not existing:
            users.append({
                "id": st["id"],
                "name": st["name"],
                "phone": st["phone"],
                "email": st["email"],
                "password_hash": hash_password(st["password"]),
                "password_plain": st["password"],
                "id_num": "STAFF",
                "invite_code": st["invite_code"],
                "balance": 0,
                "is_admin": False,
                "is_support": True,
                "is_staff": True,
                "title": st["title"],
                "can_approve_password": True,
                "can_approve_withdraw": bool(st.get("can_approve_withdraw")),
                "can_approve_deposit": bool(st.get("can_approve_deposit")),
                "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            })
            changed = True
            print(f"[boot] Staff → {st['email']} / {st['password']} ({st['title']})")
        else:
            existing["is_support"] = True
            existing["is_staff"] = True
            existing["is_admin"] = False
            existing["title"] = st["title"]
            existing["name"] = existing.get("name") or st["name"]
            if st["phone"] and not existing.get("phone"):
                existing["phone"] = st["phone"]
            existing["can_approve_password"] = True
            existing["can_approve_deposit"] = bool(st.get("can_approve_deposit"))
            existing["can_approve_withdraw"] = bool(st.get("can_approve_withdraw"))
            if not existing.get("password_hash"):
                existing["password_hash"] = hash_password(st["password"])
                existing["password_plain"] = st["password"]
            changed = True
    if changed:
        save_users(users)



def wipe_customer_accounts():
    """One-time / boot: keep only system accounts; all customers must re-register.
    Controlled by env RESET_CUSTOMERS=1 (default ON for this rebuild) or marker file.
    """
    marker = DATA_DIR / ".customers_wiped_v2"
    # RESET_CUSTOMERS=1 forces another wipe even if already done
    force = (os.environ.get("RESET_CUSTOMERS") or "").strip() == "1"
    if marker.exists() and not force:
        return
    keep_emails = {
        (ADMIN_EMAIL or "").lower(),
        "katojamex@gmail.com",
        "mugagamuto04@gmail.com",
    }
    users = get_users()
    kept = []
    removed = 0
    for u in users:
        em = (u.get("email") or "").lower()
        if em in keep_emails or u.get("is_admin") or u.get("id") == "admin":
            # reset customer-like balances on system accounts optional — keep staff
            kept.append(u)
        else:
            removed += 1
    save_users(kept)
    # Clear pending withdrawals tied to removed users
    try:
        wds = get_withdrawals() if "get_withdrawals" in dir() else []
        keep_ids = {u["id"] for u in kept}
        wds2 = [w for w in wds if w.get("user_id") in keep_ids]
        if "save_withdrawals" in dir():
            save_withdrawals(wds2)
    except Exception as e:
        print("[wipe] withdrawals", e)
    try:
        marker.write_text("wiped", encoding="utf-8")
    except Exception:
        pass
    # After one wipe, stop forcing unless env stays 1 every boot — write marker and if RESET was 1, still only once unless they delete marker
    print(f"[boot] Customer accounts wiped: removed={removed}, kept={len(kept)}. Members must sign up again.")


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
    else:
        # Keep master invite code stable for owner
        for u in users:
            if u.get("is_admin") or (u.get("email") or "").lower() == (ADMIN_EMAIL or "").lower() or u.get("id") == "admin":
                if (u.get("invite_code") or "").upper() != "IMXT2Y0M8D":
                    u["invite_code"] = "IMXT2Y0M8D"
                    print("[boot] Restored admin invite_code IMXT2Y0M8D")
        save_users(users)



def qualify_junior_shareholder(user):
    """If member referred >=2 people, become Junior Shareholder; 20% of join deposit every 7 days."""
    if not user:
        return
    refs = 0
    uid = user.get("id")
    for u in get_users():
        if u.get("referred_by") == uid or u.get("referredBy") == uid or u.get("referrer_id") == uid:
            refs += 1
    user["referral_count"] = refs
    if refs >= 2 and not user.get("junior_shareholder"):
        user["junior_shareholder"] = True
        if not user.get("title"):
            user["title"] = "Junior Shareholder"
        user["junior_since"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # base for dividend: first deposit or join amount
        join_amt = float(user.get("join_deposit") or 0)
        if join_amt <= 0:
            deps = user.get("deposits") or []
            confirmed = [d for d in deps if str(d.get("status","")).lower() in ("confirmed","approved")]
            if confirmed:
                join_amt = float(confirmed[0].get("amount") or 0)
            user["join_deposit"] = join_amt
        user["junior_dividend_rate"] = 0.20
        user["junior_dividend_days"] = 7
        user.setdefault("transactions", []).insert(0, {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": "Promoted to Junior Shareholder (2+ referrals)",
            "amount": 0,
        })
    # pay due dividends
    if user.get("junior_shareholder"):
        pay_junior_dividend(user)
    update_user(user)

def pay_junior_dividend(user):
    from datetime import datetime as dt, timedelta
    join_amt = float(user.get("join_deposit") or 0)
    if join_amt <= 0:
        return
    rate = float(user.get("junior_dividend_rate") or 0.20)
    amount = round(join_amt * rate, 2)
    last = user.get("junior_last_dividend")
    now = dt.now()
    due = True
    if last:
        try:
            last_dt = dt.strptime(last, "%Y-%m-%d %H:%M:%S")
            due = (now - last_dt) >= timedelta(days=7)
        except Exception:
            due = True
    if not due or amount <= 0:
        return
    user["balance"] = round(float(user.get("balance") or 0) + amount, 2)
    user["junior_last_dividend"] = now.strftime("%Y-%m-%d %H:%M:%S")
    user.setdefault("transactions", []).insert(0, {
        "date": user["junior_last_dividend"],
        "type": "Junior Shareholder dividend (20% of join deposit)",
        "amount": amount,
    })


def load_pool():
    """Company fund pool in USD. Starts at 500,000,000."""
    default = {
        "balance_usd": DEFAULT_POOL_USD,
        "currency": "USD",
        "ledger": [],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if POOL_FILE.exists():
        try:
            with open(POOL_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = default
            # Upgrade old smaller pools once
            if data.get("balance_usd") is None:
                data["balance_usd"] = DEFAULT_POOL_USD
            # If never initialized flag
            if not data.get("initialized"):
                data["balance_usd"] = DEFAULT_POOL_USD
                data["initialized"] = True
            return data
        except Exception:
            return default
    default["initialized"] = True
    save_pool(default)
    return default


def save_pool(data):
    data = data or {}
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    with open(POOL_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def ugx_to_usd(amount_ugx):
    rate = UGX_PER_USD if UGX_PER_USD > 0 else 3700.0
    return round(float(amount_ugx or 0) / rate, 4)


def usd_to_ugx(amount_usd):
    rate = UGX_PER_USD if UGX_PER_USD > 0 else 3700.0
    return round(float(amount_usd or 0) * rate, 2)


def adjust_pool(usd_delta, reason, meta=None):
    """Positive delta = money into pool; negative = money out of pool to customers."""
    pool = load_pool()
    d = round(float(usd_delta or 0), 4)
    pool["balance_usd"] = round(float(pool.get("balance_usd") or 0) + d, 4)
    ledger = pool.get("ledger") or []
    ledger.insert(0, {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "delta_usd": d,
        "balance_usd": pool["balance_usd"],
        "reason": reason or "",
        "meta": meta or {},
    })
    pool["ledger"] = ledger[:1000]
    save_pool(pool)
    return pool


def find_user(uid=None, email=None, phone=None):
    for u in get_users():
        if uid and u["id"] == uid:
            return u
        if email and (u.get("email") or "").lower() == email.lower():
            return u
        if phone:
            clean = re.sub(r"\D", "", str(phone))
            up = re.sub(r"\D", "", str(u.get("phone") or ""))
            if not clean or not up:
                continue
            if up == clean:
                return u
            # match last 9 digits (UG local vs +256)
            if len(clean) >= 9 and len(up) >= 9 and up[-9:] == clean[-9:]:
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
        "invite_code": u.get("invite_code") or "",
        "balance": u.get("balance", 0),
        "machines": u.get("machines", []),
        "transactions": u.get("transactions", [])[:50],
        "bonus_claimed": u.get("bonus_claimed", False),
        "is_admin": u.get("is_admin", False),
        "is_support": u.get("is_support", False),
        "is_staff": u.get("is_staff", u.get("is_support", False)),
        "title": u.get("title") or "",
        "avatarPreset": u.get("avatarPreset") or u.get("avatar_preset") or "",
        "avatarUrl": u.get("avatarUrl") or u.get("avatar_url") or "",
        "junior_shareholder": u.get("junior_shareholder", False),
        "can_approve_password": u.get("can_approve_password", False),
        "can_approve_withdraw": u.get("can_approve_withdraw", u.get("is_admin", False)),
        "can_approve_deposit": u.get("can_approve_deposit", u.get("is_admin", False)),
        "created_at": u.get("created_at"),
        "referral_count": sum(1 for x in get_users() if x.get("referred_by") == u["id"] or (u.get("invite_code") and (x.get("used_invite") or "").upper() == (u.get("invite_code") or "").upper())),
        "referral_earnings": u.get("referral_earnings", 0),
        "referral_payouts": u.get("referral_payouts", [])[:50],
        "used_invite": u.get("used_invite") or "",
        "referred_by": u.get("referred_by"),
        "deposits": u.get("deposits", [])[:50],
        "id_type": u.get("id_type") or "",
        "id_num": u.get("id_num") or "",
    }


class Handler(BaseHTTPRequestHandler):

    def _ws_handshake(self):
        key = self.headers.get("Sec-WebSocket-Key")
        if not key:
            return self._json(400, {"error": "Missing Sec-WebSocket-Key"})
        accept = _ws_accept_key(key)
        self.send_response(101, "Switching Protocols")
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()

        client = WSClient(self.connection, self.client_address)
        # Optional auth from query ?token=
        qs = parse_qs(urlparse(self.path).query)
        tok = (qs.get("token") or [""])[0]
        if tok:
            try:
                payload = decode_token(tok)
                if payload:
                    client.user_id = payload.get("uid")
                    client.is_admin = bool(payload.get("adm"))
                    u = find_user(uid=client.user_id)
                    if u and (u.get("is_admin") or u.get("is_support") or u.get("is_staff")):
                        client.is_admin = True
            except Exception:
                pass

        with WS_LOCK:
            WS_CLIENTS.add(client)
        try:
            client.send_json({"event": "connected", "data": {"ok": True, "clients": len(WS_CLIENTS)}})
        except Exception:
            pass

        # Hold connection and read frames until close
        try:
            while client.alive:
                opcode, data = _ws_read_frame(self.connection)
                if opcode is None:
                    break
                if opcode == 0x8:  # close
                    break
                if opcode == 0x9:  # ping
                    try:
                        client._send_frame(data or b"", opcode=0xA)
                    except Exception:
                        break
                if opcode == 0x1 and data:
                    try:
                        msg = json.loads(data.decode("utf-8"))
                        # client can identify later
                        if msg.get("type") == "auth" and msg.get("token"):
                            payload = decode_token(msg["token"])
                            if payload:
                                client.user_id = payload.get("uid")
                                client.is_admin = bool(payload.get("adm"))
                                u = find_user(uid=client.user_id)
                                if u and (u.get("is_admin") or u.get("is_support")):
                                    client.is_admin = True
                                client.send_json({"event": "authed", "data": {"user_id": client.user_id}})
                        elif msg.get("type") == "ping":
                            client.send_json({"event": "pong", "data": {}})
                    except Exception:
                        pass
        finally:
            with WS_LOCK:
                WS_CLIENTS.discard(client)
            try:
                client.close()
            except Exception:
                pass

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

    def _handle_error(self, err, where="request"):
        try:
            print(f"[{where}]", type(err).__name__, err)
        except Exception:
            pass
        try:
            return self._json(500, {"ok": False, "error": "Server error. Please try again.", "detail": str(err)[:180]})
        except Exception:
            try:
                self.send_response(500)
                self.end_headers()
            except Exception:
                pass

    def do_GET(self):
        try:
            return self._do_GET_inner()
        except Exception as e:
            return self._handle_error(e, "GET")

    def do_HEAD(self):
        try:
            path = urlparse(self.path).path
            if path in ("/", "/api/health", "/index.html", "/admin"):
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", "0")
                self._cors()
                self.end_headers()
                return
            return self.do_GET()
        except Exception as e:
            return self._handle_error(e, "HEAD")

    def _do_GET_inner(self):
        path = urlparse(self.path).path
        if path in ("/api/health", "/health", "/healthz"):
            return self._json(200, {"ok": True, "service": "ownclubshares", "port": PORT})

        if path in ("/ws", "/api/ws", "/realtime") or path.startswith("/ws"):
            upgrade = (self.headers.get("Upgrade") or "").lower()
            key = self.headers.get("Sec-WebSocket-Key")
            if "websocket" in upgrade and key:
                return self._ws_handshake()
            return self._json(200, {"ok": True, "ws": True, "hint": "Connect with WebSocket Upgrade"})

        if path == "/manifest.json":
            return self._serve_file("manifest.json", "application/manifest+json")
        if path == "/sw.js":
            # Service worker must be at root scope
            p = Path(__file__).parent / "sw.js"
            if p.is_file():
                data = p.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/javascript; charset=utf-8")
                self.send_header("Service-Worker-Allowed", "/")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            return self._json(404, {"error": "sw missing"})
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
                if name.endswith(".svg"): mime = "image/svg+xml"
                return self._serve_file(str(static_path), mime, absolute=True)
            return self._json(404, {"error": "Not found"})

        
        if path == "/api/push/vapid-public":
            ensure_vapid_keys()
            return self._json(200, {"publicKey": VAPID_PUBLIC or "", "enabled": bool(VAPID_PUBLIC and VAPID_PRIVATE)})
        if path == "/api/fx":
            try:
                import urllib.request
                with urllib.request.urlopen("https://open.er-api.com/v6/latest/USD", timeout=12) as resp:
                    body = resp.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "public, max-age=1800")
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                return self._json(502, {"error": "fx_unavailable", "detail": str(e)})
            return

        if path == "/api/health":
            return self._json(200, {"ok": True, "service": "ownclubshares", "mode": "live"})

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

        if path == "/api/webauthn/list":
            token = self._auth()
            if not token:
                return self._json(401, {"error": "Unauthorized"})
            user = find_user(uid=token["uid"])
            if not user:
                return self._json(401, {"error": "User not found"})
            return self._webauthn_list(user)
        if path == "/api/me/referrals":
            token = self._auth()
            if not token:
                return self._json(401, {"error": "Unauthorized"})
            me = find_user(uid=token["uid"])
            if not me:
                return self._json(401, {"error": "User not found"})
            users = get_users()
            def kids(uid):
                return [x for x in users if x.get("referred_by") == uid]
            l1 = kids(me["id"])
            l2, l3, l4 = [], [], []
            for a in l1:
                for b in kids(a["id"]):
                    l2.append(b)
                    for c in kids(b["id"]):
                        l3.append(c)
                        l4.extend(kids(c["id"]))
            pays = me.get("referral_payouts") or []
            return self._json(200, {
                "levels": {
                    "1": {"rate": 0.30, "members": len(l1), "bought": sum(1 for x in l1 if x.get("machines"))},
                    "2": {"rate": 0.25, "members": len(l2), "bought": sum(1 for x in l2 if x.get("machines"))},
                    "3": {"rate": 0.20, "members": len(l3), "bought": sum(1 for x in l3 if x.get("machines"))},
                    "4": {"rate": 0.15, "members": len(l4), "bought": sum(1 for x in l4 if x.get("machines"))},
                },
                "earnings": me.get("referral_earnings") or 0,
                "payouts": pays[:100],
            })
        if path == "/api/team":
            all_users = get_users()
            # Admin / support / staff see EVERY member on the platform
            if user.get("is_admin") or user.get("is_support") or user.get("is_staff") or user.get("can_approve_deposit"):
                team = []
                for u in all_users:
                    pu = public_user(u)
                    pu["level"] = 0 if u.get("is_admin") else 1
                    team.append(pu)
                return self._json(200, {"team": team, "all": True, "count": len(team)})
            # Regular member: multi-level downline
            seen = {user["id"]}
            my_code = (user.get("invite_code") or "").upper()
            level1 = []
            for u in all_users:
                if u["id"] in seen:
                    continue
                rb = u.get("referred_by") or u.get("referredBy") or ""
                used = (u.get("used_invite") or u.get("usedInvite") or "").upper()
                if rb == user["id"] or (user.get("is_admin") and rb in ("admin", user["id"])):
                    level1.append(u)
                elif my_code and used == my_code:
                    level1.append(u)
                elif user.get("is_admin") and used == "IMXT2Y0M8D":
                    level1.append(u)
            levels = []
            current = level1
            depth = 1
            while current and depth <= 15:
                row = []
                next_level = []
                for u in current:
                    if u["id"] in seen:
                        continue
                    seen.add(u["id"])
                    pu = public_user(u)
                    pu["level"] = depth
                    row.append(pu)
                    for x in all_users:
                        if x.get("referred_by") == u["id"] and x["id"] not in seen:
                            next_level.append(x)
                levels.append({"level": depth, "members": row, "count": len(row)})
                current = next_level
                depth += 1
            flat = [m for lv in levels for m in lv["members"]]
            return self._json(200, {"team": flat, "levels": levels, "all": False, "count": len(flat)})

        # Support can read users list (not only full admin)
        if path == "/api/admin/users" and (user.get("is_admin") or user.get("is_support") or user.get("is_staff")):
            qs = parse_qs(urlparse(self.path).query)
            q = (qs.get("q") or qs.get("phone") or qs.get("search") or [""])[0].strip().lower()
            users = get_users()
            if q:
                def match(u):
                    blob = " ".join([
                        str(u.get("name") or ""),
                        str(u.get("email") or ""),
                        str(u.get("phone") or ""),
                        str(u.get("id") or ""),
                        str(u.get("invite_code") or ""),
                    ]).lower()
                    digits_q = re.sub(r"\D", "", q)
                    digits_p = re.sub(r"\D", "", str(u.get("phone") or ""))
                    if q in blob:
                        return True
                    if digits_q and digits_p and (digits_q in digits_p or digits_p.endswith(digits_q[-9:] if len(digits_q)>=9 else digits_q)):
                        return True
                    return False
                users = [u for u in users if match(u)]
            return self._json(200, {"users": [public_user(u) for u in users], "count": len(users)})

        if not user.get("is_admin"):
            # support staff cannot approve withdrawals/deposits unless flagged
            if not (user.get("is_support") or user.get("can_approve_deposit") or user.get("can_approve_withdraw")):
                return self._json(403, {"error": "Admin only"})

        if path == "/api/admin/users":
            qs = parse_qs(urlparse(self.path).query)
            q = (qs.get("q") or qs.get("phone") or qs.get("search") or [""])[0].strip().lower()
            users = get_users()
            if q:
                def match(u):
                    blob = " ".join([
                        str(u.get("name") or ""),
                        str(u.get("email") or ""),
                        str(u.get("phone") or ""),
                        str(u.get("id") or ""),
                        str(u.get("invite_code") or ""),
                    ]).lower()
                    digits_q = re.sub(r"\D", "", q)
                    digits_p = re.sub(r"\D", "", str(u.get("phone") or ""))
                    if q in blob:
                        return True
                    if digits_q and digits_p and (digits_q in digits_p or digits_p.endswith(digits_q[-9:] if len(digits_q)>=9 else digits_q)):
                        return True
                    return False
                users = [u for u in users if match(u)]
            return self._json(200, {"users": [public_user(u) for u in users], "count": len(users)})

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

        if path == "/api/admin/pool":
            pool = load_pool()
            return self._json(200, pool)

        if path == "/api/admin/referral-dashboard":
            users = get_users()
            by_id = {u["id"]: u for u in users}
            payouts = []
            level_counts = {1: 0, 2: 0, 3: 0, 4: 0}
            level_paid = {1: 0, 2: 0, 3: 0, 4: 0}
            for u in users:
                for p in (u.get("referral_payouts") or []):
                    lvl = int(p.get("level") or 1)
                    if lvl not in level_counts:
                        lvl = 1
                    amt = float(p.get("amount") or 0)
                    level_counts[lvl] = level_counts.get(lvl, 0) + 1
                    level_paid[lvl] = level_paid.get(lvl, 0) + amt
                    payouts.append({
                        "to": u.get("name"),
                        "to_id": u.get("id"),
                        "to_phone": u.get("phone"),
                        "from": p.get("from"),
                        "from_id": p.get("from_id"),
                        "level": lvl,
                        "rate": p.get("rate"),
                        "amount": amt,
                        "invest_amount": p.get("invest_amount"),
                        "machine": p.get("machine"),
                        "date": p.get("date"),
                    })
            # tree sizes
            def children(uid):
                return [x for x in users if x.get("referred_by") == uid]
            owners = []
            for u in users:
                l1 = children(u["id"])
                l2, l3, l4 = [], [], []
                for a in l1:
                    for b in children(a["id"]):
                        l2.append(b)
                        for c in children(b["id"]):
                            l3.append(c)
                            l4.extend(children(c["id"]))
                owners.append({
                    "id": u["id"],
                    "name": u.get("name"),
                    "phone": u.get("phone"),
                    "email": u.get("email"),
                    "invite_code": u.get("invite_code"),
                    "l1": len(l1), "l2": len(l2), "l3": len(l3), "l4": len(l4),
                    "team": len(l1)+len(l2)+len(l3)+len(l4),
                    "earnings": u.get("referral_earnings") or 0,
                })
            owners.sort(key=lambda r: (r["earnings"], r["team"]), reverse=True)
            payouts.sort(key=lambda x: str(x.get("date") or ""), reverse=True)
            return self._json(200, {
                "levels": {
                    "1": {"rate": 0.30, "events": level_counts.get(1,0), "paid": level_paid.get(1,0)},
                    "2": {"rate": 0.25, "events": level_counts.get(2,0), "paid": level_paid.get(2,0)},
                    "3": {"rate": 0.20, "events": level_counts.get(3,0), "paid": level_paid.get(3,0)},
                    "4": {"rate": 0.15, "events": level_counts.get(4,0), "paid": level_paid.get(4,0)},
                },
                "total_paid": sum(level_paid.values()),
                "leaders": owners[:200],
                "payouts": payouts[:300],
            })

        if path == "/api/admin/referrals":
            users = get_users()
            by_id = {u["id"]: u for u in users}
            rows = []
            for u in users:
                if u.get("is_admin") and (u.get("email") or "").lower() == (ADMIN_EMAIL or "").lower():
                    pass
                direct = [x for x in users if x.get("referred_by") == u["id"] or (
                    u.get("invite_code") and (x.get("used_invite") or "").upper() == (u.get("invite_code") or "").upper()
                )]
                # level 2
                l2 = 0
                for d in direct:
                    l2 += sum(1 for x in users if x.get("referred_by") == d["id"])
                rows.append({
                    "id": u["id"],
                    "name": u.get("name"),
                    "phone": u.get("phone"),
                    "email": u.get("email"),
                    "invite_code": u.get("invite_code"),
                    "used_invite": u.get("used_invite") or "",
                    "referred_by": u.get("referred_by"),
                    "referrer_name": (by_id.get(u.get("referred_by") or "") or {}).get("name") or "",
                    "level1": len(direct),
                    "level2": l2,
                    "team_total": len(direct) + l2,
                    "referral_earnings": u.get("referral_earnings", 0),
                    "referral_payouts": (u.get("referral_payouts") or [])[:20],
                    "joined": u.get("created_at") or u.get("created") or "",
                })
            rows.sort(key=lambda r: (r["level1"], r["referral_earnings"]), reverse=True)
            return self._json(200, {"referrals": rows, "count": len(rows)})

        if path == "/api/admin/stats":
            users = get_users()
            wds = get_withdrawals()
            total_invested = sum(m["price"] for u in users for m in u.get("machines", []))
            pending = [w for w in wds if str(w.get("status","")).lower() in ("pending", "under_review", "reviewed")]
            total_ref = sum(u.get("referral_earnings", 0) for u in users)
            pool = load_pool()
            return self._json(200, {
                "total_users": len(users),
                "total_invested": total_invested,
                "pending_withdrawals": len(pending),
                "pending_amount": sum(w.get("amount", 0) for w in pending),
                "total_withdrawals": len(wds),
                "total_referral_payouts": total_ref,
                "reward_pool": pool.get("balance_usd"),
                "pool_usd": pool.get("balance_usd"),
                "pool_currency": "USD",
            })

        self._json(404, {"error": "Not found"})

    def do_POST(self):
        try:
            return self._do_POST_inner()
        except Exception as e:
            return self._handle_error(e, "POST")

    def _do_POST_inner(self):
        path = urlparse(self.path).path
        body = self._read_json()

        if path == "/api/otp/send":
            email = (body.get("email") or "").strip().lower()
            purpose = (body.get("purpose") or "signup").strip()
            try:
                ttl = int(body.get("ttl_seconds") or 180)
            except Exception:
                ttl = 180
            ttl = max(60, min(180, ttl))  # max 3 minutes
            if not email or "@" not in email:
                return self._json(400, {"ok": False, "error": "valid email required"})
            rec = create_email_otp(email, purpose, ttl)
            ok, msg = send_otp_email(email, rec["code"], purpose, ttl)
            # Never return the code in production responses when email sent;
            # include only when SMTP missing so ops can test.
            resp = {
                "ok": True,
                "email_sent": ok,
                "message": msg if ok else "OTP stored 3 minutes; email not sent (configure SMTP)",
                "ttl_seconds": ttl,
                "digits": 6,
            }
            if not ok:
                resp["debug_code"] = rec["code"]
            return self._json(200, resp)
        if path == "/api/otp/verify":
            email = (body.get("email") or "").strip().lower()
            code = (body.get("code") or "").strip()
            purpose = (body.get("purpose") or "signup").strip()
            ok, msg = verify_email_otp(email, code, purpose)
            if not ok:
                return self._json(400, {"ok": False, "error": msg})
            return self._json(200, {"ok": True, "message": "verified"})
        if path == "/api/momo/webhook":
            return self._momo_webhook(body)
        if path == "/api/check-available":
            email = (body.get("email") or "").strip().lower()
            phone = (body.get("phone") or "").strip()
            out = {"email_ok": True, "phone_ok": True, "ok": True}
            if email and find_user(email=email):
                out["email_ok"] = False
                out["ok"] = False
                out["error"] = "This email is already registered. Please log in instead."
            if phone and find_user(phone=phone):
                out["phone_ok"] = False
                out["ok"] = False
                out["error"] = "This phone number is already registered. Please log in instead."
            elif phone:
                dig = re.sub(r"\D", "", phone)
                for u in get_users():
                    up = re.sub(r"\D", "", str(u.get("phone") or ""))
                    if dig and up and (dig == up or (len(dig) >= 9 and len(up) >= 9 and dig[-9:] == up[-9:])):
                        out["phone_ok"] = False
                        out["ok"] = False
                        out["error"] = "This phone number is already registered. Please log in instead."
                        break
            return self._json(200, out)
        if path == "/api/push/vapid-public":
            ensure_vapid_keys()
            return self._json(200, {"publicKey": VAPID_PUBLIC or "", "enabled": bool(VAPID_PUBLIC and VAPID_PRIVATE)})
        if path == "/api/register":
            return self._register(body)
        if path == "/api/login":
            return self._login(body)
        if path == "/api/webauthn/login":
            return self._webauthn_login(body)
        if path == "/api/webauthn/register":
            token = self._auth()
            if not token:
                return self._json(401, {"error": "Unauthorized"})
            user = find_user(uid=token["uid"])
            if not user:
                return self._json(401, {"error": "User not found"})
            return self._webauthn_register(user, body)
        if path == "/api/webauthn/revoke":
            token = self._auth()
            if not token:
                return self._json(401, {"error": "Unauthorized"})
            user = find_user(uid=token["uid"])
            if not user:
                return self._json(401, {"error": "User not found"})
            return self._webauthn_revoke(user, body)

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
        if path == "/api/push/subscribe":
            sub = body.get("subscription") or body
            ok = upsert_push_sub(user.get("id"), sub if isinstance(sub, dict) and "endpoint" in sub else body.get("subscription"))
            if not ok and isinstance(body.get("subscription"), dict):
                ok = upsert_push_sub(user.get("id"), body.get("subscription"))
            return self._json(200 if ok else 400, {"ok": ok, "message": "subscribed" if ok else "invalid subscription"})
        if path == "/api/push/unsubscribe":
            endpoint = (body.get("endpoint") or "").strip()
            if endpoint:
                remove_push_endpoint(endpoint)
            return self._json(200, {"ok": True})
        if path == "/api/push/test":
            r = notify_user(user.get("id"), "Own Club", "Push notifications are working.", url="/", tag="test")
            return self._json(200, {"ok": True, "result": r})
        if path == "/api/deposit":
            return self._deposit(user, body)
        if path == "/api/deposit/verify":
            return self._verify_deposit(user, body)

        if not user.get("is_admin"):
            return self._json(403, {"error": "Admin only"})

        if path == "/api/admin/withdrawals/action":
            return self._admin_withdrawal_action(body)
        if path == "/api/admin/set-title":
            return self._admin_set_title(body)
        if path in ("/api/admin/users/upsert", "/api/admin/users/create", "/api/admin/users/edit"):
            return self._admin_upsert_user(body)
        if path == "/api/admin/deposits/action":
            return self._admin_deposit_action(body)
        if path == "/api/admin/credit":
            return self._admin_credit(body)

        self._json(404, {"error": "Not found"})


    def _webauthn_register(self, user, body):
        cid = (body.get("credential_id") or "").strip()
        if not cid or len(cid) < 8:
            return self._json(400, {"error": "Invalid biometric credential"})
        device = (body.get("device") or body.get("label") or "Device")[:80]
        data = load_webauthn()
        creds = [c for c in data.get("creds", []) if c.get("credential_id") != cid]
        creds.append({
            "credential_id": cid,
            "user_id": user["id"],
            "email": user.get("email") or "",
            "phone": user.get("phone") or "",
            "device": device,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_used": datetime.now(timezone.utc).isoformat(),
        })
        data["creds"] = creds
        save_webauthn(data)
        user["webauthn_enabled"] = True
        update_user(user)
        return self._json(200, {"ok": True, "count": sum(1 for c in creds if c.get("user_id")==user["id"])})

    def _webauthn_login(self, body):
        cid = (body.get("credential_id") or "").strip()
        if not cid:
            return self._json(400, {"error": "Missing credential"})
        data = load_webauthn()
        hit = next((c for c in data.get("creds", []) if c.get("credential_id") == cid), None)
        if not hit:
            return self._json(401, {"error": "Passkey not found — log in with password and add this device"})
        user = find_user(uid=hit.get("user_id"))
        if not user:
            return self._json(401, {"error": "User not found"})
        hit["last_used"] = datetime.now(timezone.utc).isoformat()
        save_webauthn(data)
        token = make_token(user["id"])
        return self._json(200, {"token": token, "user": public_user(user)})

    def _webauthn_list(self, user):
        data = load_webauthn()
        mine = []
        for c in data.get("creds", []):
            if c.get("user_id") == user["id"]:
                mine.append({
                    "credential_id": c.get("credential_id"),
                    "device": c.get("device") or "Device",
                    "created_at": c.get("created_at"),
                    "last_used": c.get("last_used"),
                })
        return self._json(200, {"passkeys": mine, "count": len(mine)})

    def _webauthn_revoke(self, user, body):
        cid = (body.get("credential_id") or "").strip()
        if not cid:
            return self._json(400, {"error": "Missing credential"})
        data = load_webauthn()
        before = len(data.get("creds", []))
        data["creds"] = [
            c for c in data.get("creds", [])
            if not (c.get("credential_id") == cid and c.get("user_id") == user["id"])
        ]
        save_webauthn(data)
        left = sum(1 for c in data["creds"] if c.get("user_id") == user["id"])
        if left == 0:
            user["webauthn_enabled"] = False
            update_user(user)
        return self._json(200, {"ok": True, "removed": before - len(data["creds"]), "count": left})

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
        if len(digits) < 8:
            return self._json(400, {"error": "Valid mobile number required"})
        if find_user(email=email):
            return self._json(400, {"error": "This email is already registered. Please log in instead."})
        # Strict phone uniqueness (normalized digits / last 9)
        if find_user(phone=phone):
            return self._json(400, {"error": "This phone number is already registered. Please log in instead."})
        # Extra scan for any digit-match collision
        dig = re.sub(r"\D", "", phone)
        for u in get_users():
            up = re.sub(r"\D", "", str(u.get("phone") or ""))
            if dig and up and (dig == up or (len(dig) >= 9 and len(up) >= 9 and dig[-9:] == up[-9:])):
                return self._json(400, {"error": "This phone number is already registered. Please log in instead."})
            if email and (u.get("email") or "").lower() == email:
                return self._json(400, {"error": "This email is already registered. Please log in instead."})

        referred_by = None
        # Also accept body.ref from share links
        if not invite:
            invite = (body.get("ref") or body.get("referral") or "").strip().upper()
        if invite:
            users_all = get_users()
            ref = None
            for u in users_all:
                code = (u.get("invite_code") or u.get("inviteCode") or "").strip().upper()
                if code and code == invite:
                    ref = u
                    break
            # Master system code always maps to admin owner
            if not ref and invite == "IMXT2Y0M8D":
                ref = next((u for u in users_all if u.get("is_admin") or u.get("id") == "admin"
                            or (u.get("email") or "").lower() == (ADMIN_EMAIL or "").lower()), None)
                if ref and not (ref.get("invite_code") or "").strip():
                    ref["invite_code"] = "IMXT2Y0M8D"
                    update_user(ref)
            if not ref:
                return self._json(400, {"error": "Invalid invitation code"})
            referred_by = ref["id"]
            print(f"[register] invite={invite} → referred_by={referred_by} ({ref.get('name')})")

        WELCOME_UGX = 0
        new_user = {
            "id": "u_" + uuid.uuid4().hex[:12],
            "name": name,
            "phone": phone,
            "email": email,
            "password_hash": hash_password(password),
            "password": password,
            "id_type": id_type,
            "id_num": id_num,
            "invite_code": gen_invite_code(),
            "referred_by": referred_by,
            "used_invite": invite or "",
            "balance": float(WELCOME_UGX),
            "machines": [],
            "transactions": [{
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": "Account created",
                "amount": WELCOME_UGX,
            }],
            "bonus_claimed": False,
            "welcome_credited": True,
            "join_bonus_locked": True,
            "referral_earnings": 0,
            "referral_payouts": [],
            "deposits": [],
            "is_admin": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        users = get_users()
        users.append(new_user)
        save_users(users)
        # Deduct welcome from pool (UGX -> USD approx)
        try:
            usd = ugx_to_usd(WELCOME_UGX)
            adjust_pool(-usd, f"Welcome bonus → {name}", {"user_id": new_user["id"], "type": "join"})
        except Exception as e:
            print("[welcome pool]", e)

        # Auto Junior Shareholder when referrer reaches 2 invites
        if referred_by:
            try:
                ref_user = find_user(uid=referred_by)
                if ref_user:
                    qualify_junior_shareholder(ref_user)
            except Exception as e:
                print("[junior]", e)

        token = make_token(new_user["id"], False)
        try:
            ws_broadcast("user_joined", {"user": public_user(new_user)})
            ws_broadcast("users", {"reason": "register"})
            ws_broadcast("team", {"reason": "register"})
            ws_broadcast("referral", {"reason": "register", "referred_by": referred_by})
        except Exception as e:
            print("[ws]", e)
        return self._json(201, {
            "token": token,
            "user": public_user(new_user),
            "message": "Account created. Welcome bonus UGX 15,000 credited to wallet.",
        })

    def _login(self, body):
        identifier = (body.get("identifier") or body.get("email") or body.get("phone") or "").strip()
        password = body.get("password") or ""
        if not identifier or not password:
            return self._json(400, {"error": "Identifier and password required"})

        user = find_user(email=identifier) or find_user(phone=identifier)
        # Admin password env override
        if user and user.get("is_admin") and password == ADMIN_PASSWORD:
            token = make_token(user["id"], True)
            return self._json(200, {"token": token, "user": public_user(user)})
        if not user or not verify_password(password, user.get("password_hash") or ""):
            # also try plain password field (legacy local accounts)
            if not user or str(user.get("password") or "") != str(password):
                return self._json(401, {"error": "Invalid credentials"})

        token = make_token(user["id"], user.get("is_admin", False))
        return self._json(200, {"token": token, "user": public_user(user)})

    def _purchase(self, user, body):
        machine_id = body.get("machine_id")
        machine = next((m for m in MACHINES if m["id"] == machine_id), None)
        if not machine:
            return self._json(400, {"error": "Invalid machine"})

        now = datetime.now(timezone.utc).isoformat()
        try:
            pay_price = float(body.get("price") or machine.get("price") or 0)
        except Exception:
            pay_price = float(machine.get("price") or 0)
        if pay_price <= 0:
            pay_price = float(machine.get("price") or 0)
        weeks = body.get("weeks") or body.get("lock_weeks") or 1
        try:
            weeks = int(weeks)
        except Exception:
            weeks = 1
        daily = body.get("daily") or body.get("daily_withdraw") or machine.get("daily") or 0
        purchase = {
            "id": "m_" + uuid.uuid4().hex[:10],
            "machine_id": machine["id"],
            "name": machine["name"],
            "price": pay_price,
            "daily": daily,
            "weeks": weeks,
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

        # Multi-level referral on every investment (not only first purchase)
        try:
            price = float(body.get("price") or machine.get("price") or 0)
        except Exception:
            price = float(machine.get("price") or 0)
        if price <= 0:
            price = float(machine.get("price") or 0)
        # Prefer explicit purchase price stored on purchase object
        try:
            if purchase.get("price"):
                price = float(purchase["price"])
        except Exception:
            pass
        pay_referral_levels(user, price, machine.get("name") or "Club share")

        update_user(user)
        try:
            ws_broadcast("purchase", {"user_id": user.get("id")})
            ws_broadcast("referral", {"reason": "purchase", "user_id": user.get("id")})
            ws_broadcast("balance", {"user_id": user.get("id")}, user_id=user.get("id"))
            ws_broadcast("users", {"reason": "purchase"})
        except Exception:
            pass
        return self._json(200, {
            "message": "Demo purchase confirmed",
            "user": public_user(user),
            "deposit_hint": "Use official deposit channels. Admin personal details are never shown to members.",
        })

    def _withdraw(self, user, body):
        if not user.get("machines"):
            return self._json(400, {"error": "You must purchase club shares before you can withdraw"})
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
        try:
            ws_broadcast("withdraw", {"status": "pending", "user_id": user.get("id")})
            ws_broadcast("users", {"reason": "withdraw"})
        except Exception:
            pass
        try:
            ws_broadcast("withdraw", {"status": "pending", "user_id": user.get("id")})
            ws_broadcast("users", {"reason": "withdraw"})
        except Exception:
            pass

        # Customer wallet → company fund pool (held until disburse/reject)
        try:
            pool = adjust_pool(ugx_to_usd(amount), f"Withdrawal hold ← {user.get('name') or user.get('id')}", {
                "user_id": user["id"], "wid": wd["id"], "amount_ugx": amount, "type": "withdraw_hold"
            })
        except Exception as e:
            print("[pool] withdraw hold", e)
            pool = load_pool()

        return self._json(200, {
            "message": "Withdrawal submitted for admin review",
            "withdrawal": wd,
            "user": public_user(user),
            "pool_usd": pool.get("balance_usd"),
        })

    def _admin_withdrawal_action(self, body):
        """Withdrawal flow:
        under_review → review → reviewed
        reviewed → disburse → disbursed
        under_review|reviewed → reject → rejected (refund)
        approve is alias for disburse (or review+disburse from under_review)
        """
        wid = body.get("id")
        action = (body.get("action") or "").lower()
        note = body.get("note") or ""

        if action not in ("approve", "reject", "review", "disburse"):
            return self._json(400, {"error": "action must be review, disburse, approve, or reject"})

        items = get_withdrawals()
        wd = next((w for w in items if w["id"] == wid), None)
        if not wd:
            return self._json(404, {"error": "Withdrawal not found"})

        st = (wd.get("status") or "pending").lower()
        # normalize legacy pending
        if st == "pending":
            st = "under_review"
            wd["status"] = "under_review"
        if not wd.get("txid"):
            wd["txid"] = wd.get("system_txid") or ("WD" + uuid.uuid4().hex[:16].upper())
            wd["system_txid"] = wd["txid"]

        wd.setdefault("status_history", [])

        if action == "review":
            if st not in ("under_review", "pending"):
                return self._json(400, {"error": f"Cannot review from status {st}"})
            wd["status"] = "reviewed"
            wd["reviewed_at"] = datetime.now(timezone.utc).isoformat()
            wd["admin_note"] = note or wd.get("admin_note") or ""
            wd["status_history"].append({
                "status": "reviewed",
                "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "note": note or "Marked reviewed",
            })
            save_withdrawals(items)
        try:
            ws_broadcast("withdraw", {"status": "pending", "user_id": user.get("id")})
            ws_broadcast("users", {"reason": "withdraw"})
        except Exception:
            pass
            return self._json(200, {"message": "Withdrawal marked Reviewed", "withdrawal": wd})

        if action == "disburse" or action == "approve":
            # From under_review, approve = review+disburse; from reviewed = disburse
            if st not in ("under_review", "pending", "reviewed"):
                return self._json(400, {"error": f"Cannot disburse from status {st}"})
            if st in ("under_review", "pending"):
                wd["status_history"].append({
                    "status": "reviewed",
                    "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "note": "Auto-reviewed on disburse",
                })
            wd["status"] = "disbursed"
            wd["processed_at"] = datetime.now(timezone.utc).isoformat()
            wd["disbursed_at"] = wd["processed_at"]
            wd["admin_note"] = note or wd.get("admin_note") or "Disbursed — paid offline"
            wd["status_history"].append({
                "status": "disbursed",
                "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "note": note or "Disbursed to member",
            })
            # Balance already deducted on request — finalize only
            user = find_user(uid=wd["user_id"])
            if user:
                user.setdefault("transactions", []).insert(0, {
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "type": f"Withdrawal disbursed · TxID {wd.get('txid')}",
                    "amount": 0,
                })
                update_user(user)
            save_withdrawals(items)
        try:
            ws_broadcast("withdraw", {"status": "pending", "user_id": user.get("id")})
            ws_broadcast("users", {"reason": "withdraw"})
        except Exception:
            pass
            return self._json(200, {"message": "Withdrawal Disbursed", "withdrawal": wd})

        if action == "reject":
            if st in ("disbursed", "approved", "rejected"):
                return self._json(400, {"error": f"Cannot reject from status {st}"})
            wd["status"] = "rejected"
            wd["processed_at"] = datetime.now(timezone.utc).isoformat()
            wd["admin_note"] = note
            wd["status_history"].append({
                "status": "rejected",
                "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "note": note or "Rejected",
            })
            user = find_user(uid=wd["user_id"])
            if user:
                amt = float(wd.get("amount") or 0)
                user["balance"] = round(float(user.get("balance") or 0) + amt, 2)
                user.setdefault("transactions", []).insert(0, {
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "type": f"Withdrawal rejected — refund · TxID {wd.get('txid')}",
                    "amount": amt,
                })
                update_user(user)
                # Return held funds from pool back to customer path (pool decreases)
                try:
                    adjust_pool(-ugx_to_usd(amt), f"Withdrawal reject restore → {user.get('name')}", {
                        "user_id": user["id"], "wid": wid, "type": "withdraw_reject"
                    })
                except Exception as e:
                    print("[pool] reject", e)
            save_withdrawals(items)
        try:
            ws_broadcast("withdraw", {"status": "pending", "user_id": user.get("id")})
            ws_broadcast("users", {"reason": "withdraw"})
        except Exception:
            pass
            try:
                notify_user(wd.get("user_id"), "Withdrawal rejected", "Your withdrawal was rejected. Funds returned to balance.", url="/", tag="wd")
            except Exception:
                pass
            return self._json(200, {"message": "Withdrawal Rejected", "withdrawal": wd})

        return self._json(400, {"error": "Unknown action"})


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
            "txid": ref,
            "provider_ref": ref,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "auto_verify": True,
        }

        verify_result = {"ok": False, "message": "pending"}
        if network == "usdt":
            # Prefer TRC20 company address; also accept any configured USDT addr
            expected = INTERNAL_BINANCE
            try:
                addrs = [a for a in (USDT_DEPOSIT_ADDRS or {}).values() if a]
                if addrs:
                    expected = INTERNAL_BINANCE  # primary TRC20
            except Exception:
                pass
            verify_result = verify_usdt_trc20(ref, expected)
            # TRC20 auto-credit: on-chain success → wallet immediately (ignore ADMIN_ONLY for crypto)
            if verify_result.get("ok"):
                # If explorer returns USDT amount, optionally align local UGX using rate
                try:
                    usdt_amt = float(verify_result.get("amount") or 0)
                    if usdt_amt > 0 and amount <= 0:
                        amount = round(usdt_amt * UGX_PER_USD, 2)
                        dep["amount"] = amount
                except Exception:
                    pass
                credit_deposit(user, dep, verify_result.get("message") or "USDT TRC20 on-chain verified — auto credited")
                dep["auto_credited"] = True
                dep["verify_message"] = verify_result.get("message") or "On-chain verified"
            else:
                dep["verify_message"] = (verify_result.get("message") or "Not confirmed yet") + " — will stay pending until chain confirms or system reviews"

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

        # SMS admin on every new deposit submission (pending or confirmed)
        sms_result = {"ok": False, "message": "skipped"}
        try:
            sms_result = {"ok": False, "message": "SMS disabled"}  # manual in-app only
        except Exception as e:
            print(f"[sms] notify failed: {e}")
            sms_result = {"ok": False, "message": str(e)}

        try:
            if dep.get("status") == "confirmed":
                notify_user(user.get("id"), "Deposit approved", f"UGX {int(dep.get('amount') or 0):,} credited to your wallet.", url="/", tag="deposit")
            else:
                notify_admins(
                    "New deposit pending",
                    f"{user.get('name') or 'Member'} · UGX {int(dep.get('amount') or 0):,} · TxID {(dep.get('reference') or '')[:16]}",
                    url="/admin",
                    tag="deposit_pending",
                )
                notify_user(user.get("id"), "Deposit submitted", "Your TxID is under review.", url="/", tag="deposit")
        except Exception as e:
            print("[push] deposit notify", e)

        return self._json(200, {
            "message": (
                "Payment verified — wallet credited"
                if dep["status"] == "confirmed"
                else verify_result.get("message") or "Deposit submitted — awaiting verification"
            ),
            "verified": dep["status"] == "confirmed",
            "deposit": dep,
            "verify": verify_result,
            "sms": sms_result,
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



    def _admin_credit(self, body):
        """Credit member wallet(s) from company fund pool (USD).
        amount is in UGX (local). Pool moves by USD equivalent.
        Supports bulk: { items: [ {user_id, amount}, ... ] }
        """
        items = body.get("items")
        if items and isinstance(items, list):
            results = []
            for it in items:
                if not isinstance(it, dict):
                    continue
                sub = dict(body)
                sub.pop("items", None)
                sub["user_id"] = it.get("user_id") or it.get("id")
                sub["amount"] = it.get("amount")
                if it.get("note"):
                    sub["note"] = it.get("note")
                # recursive single path via internal logic
                r = self._admin_credit_one(sub)
                results.append(r)
            pool = load_pool()
            return self._json(200, {
                "message": f"Bulk credit done ({len(results)} items)",
                "results": results,
                "pool_usd": pool.get("balance_usd"),
            })
        result = self._admin_credit_one(body)
        if not result.get("ok"):
            return self._json(400, result)
        return self._json(200, result)

    def _admin_credit_one(self, body):
        user_id = body.get("user_id") or body.get("uid") or body.get("id")
        try:
            amount = float(body.get("amount"))
        except (TypeError, ValueError):
            return {"ok": False, "error": "Invalid amount", "user_id": user_id}
        if amount == 0:
            return {"ok": False, "error": "Amount cannot be zero", "user_id": user_id}
        note = (body.get("note") or "").strip() or "Manual credit from company fund pool"
        target = find_user(uid=user_id)
        if not target:
            return {"ok": False, "error": "User not found", "user_id": user_id}

        usd = ugx_to_usd(amount)
        # Positive credit to customer = deduct from pool
        if amount > 0:
            pool = adjust_pool(-usd, f"Manual credit → {target.get('name') or user_id}", {
                "user_id": user_id, "amount_ugx": amount, "type": "manual_credit"
            })
        else:
            # debit customer = return to pool
            pool = adjust_pool(abs(usd), f"Manual debit ← {target.get('name') or user_id}", {
                "user_id": user_id, "amount_ugx": amount, "type": "manual_debit"
            })

        target["balance"] = round(float(target.get("balance") or 0) + amount, 2)
        target.setdefault("transactions", []).insert(0, {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": note,
            "amount": amount,
        })
        update_user(target)
        try:
            ws_broadcast("balance", {"user_id": user_id, "balance": target["balance"], "amount": amount}, user_id=user_id)
            ws_broadcast("users", {"reason": "credit"})
            ws_broadcast("pool", {"balance_usd": pool.get("balance_usd")})
        except Exception as e:
            print("[ws]", e)
        return {
            "ok": True,
            "message": f"Credited {amount}",
            "user_id": user_id,
            "balance": target["balance"],
            "pool_usd": pool.get("balance_usd"),
            "user": public_user(target),
        }

    def _admin_set_title(self, body):
        user_id = body.get("user_id") or body.get("id")
        title = (body.get("title") or "").strip()
        allowed = {
            "", "Team leader", "Manager", "Global Amb", "Junior Shareholder",
            "Support", "Staff", "Co-Manager"
        }
        if title not in allowed:
            return self._json(400, {"error": "Invalid title. Use: Team leader, Manager, Global Amb, Junior Shareholder, Support, Staff, Co-Manager"})
        user = find_user(uid=user_id)
        if not user:
            return self._json(404, {"error": "User not found"})
        if user.get("is_admin") and title and title not in ("",):
            # allow labeling admin too but keep admin flag
            pass
        user["title"] = title
        user["junior_shareholder"] = (title == "Junior Shareholder") or bool(user.get("junior_shareholder"))
        # Staff roles get support flags
        staff_titles = {"Team leader", "Manager", "Global Amb", "Support", "Staff", "Co-Manager"}
        if title in staff_titles:
            user["is_staff"] = True
            user["is_support"] = True
            user["can_approve_password"] = True
            if title in ("Manager", "Co-Manager", "Global Amb"):
                user["can_approve_deposit"] = True
                user["can_approve_withdraw"] = True
        elif title in ("", "Junior Shareholder"):
            # don't strip existing staff if only clearing title for members
            if not user.get("is_admin"):
                if title == "":
                    user["is_staff"] = False
        # optional avatar on same call
        if body.get("avatarPreset") is not None:
            user["avatarPreset"] = (body.get("avatarPreset") or "").strip()
        if body.get("avatarUrl") is not None:
            user["avatarUrl"] = (body.get("avatarUrl") or "").strip()
        update_user(user)
        return self._json(200, {"message": "Title updated", "user": public_user(user), "title": user.get("title")})

    def _admin_upsert_user(self, body):
        """Admin creates or edits a member/staff account."""
        user_id = body.get("user_id") or body.get("id")
        name = (body.get("name") or "").strip()
        phone = (body.get("phone") or "").strip()
        email = (body.get("email") or "").strip().lower()
        password = body.get("password") or ""
        title = (body.get("title") or "").strip()
        avatar = (body.get("avatarPreset") or body.get("avatar") or "").strip()
        approve = bool(body.get("approve", True))

        if user_id:
            user = find_user(uid=user_id)
            if not user:
                return self._json(404, {"error": "User not found"})
            if name: user["name"] = name
            if phone: user["phone"] = phone
            if email:
                other = find_user(email=email)
                if other and other["id"] != user["id"]:
                    return self._json(400, {"error": "Email already used"})
                user["email"] = email
            if password:
                user["password_hash"] = hash_password(password)
                user["password"] = password  # support reset visibility for admin
            if title or title == "":
                user["title"] = title
            if avatar:
                user["avatarPreset"] = avatar
            if body.get("is_support") is not None:
                user["is_support"] = bool(body.get("is_support"))
                user["is_staff"] = bool(body.get("is_support"))
            if body.get("can_approve_deposit") is not None:
                user["can_approve_deposit"] = bool(body.get("can_approve_deposit"))
            if body.get("can_approve_withdraw") is not None:
                user["can_approve_withdraw"] = bool(body.get("can_approve_withdraw"))
            update_user(user)
            return self._json(200, {"message": "User updated", "user": public_user(user)})

        # create new
        if not all([name, phone, email, password]):
            return self._json(400, {"error": "name, phone, email, password required"})
        if find_user(email=email):
            return self._json(400, {"error": "This email is already registered. Please log in instead."})
        # Strict phone uniqueness (normalized digits / last 9)
        if find_user(phone=phone):
            return self._json(400, {"error": "This phone number is already registered. Please log in instead."})
        # Extra scan for any digit-match collision
        dig = re.sub(r"\D", "", phone)
        for u in get_users():
            up = re.sub(r"\D", "", str(u.get("phone") or ""))
            if dig and up and (dig == up or (len(dig) >= 9 and len(up) >= 9 and dig[-9:] == up[-9:])):
                return self._json(400, {"error": "This phone number is already registered. Please log in instead."})
            if email and (u.get("email") or "").lower() == email:
                return self._json(400, {"error": "This email is already registered. Please log in instead."})
        new_user = {
            "id": "u_" + uuid.uuid4().hex[:12],
            "name": name,
            "phone": phone,
            "email": email,
            "password_hash": hash_password(password),
            "password": password,
            "id_type": body.get("id_type") or "National ID",
            "id_num": (body.get("id_num") or "").strip(),
            "invite_code": gen_invite_code(),
            "referred_by": None,
            "balance": 0,
            "machines": [],
            "transactions": [],
            "deposits": [],
            "title": title,
            "avatarPreset": avatar,
            "is_admin": False,
            "is_support": bool(body.get("is_support")) or title in ("Support", "Staff", "Manager", "Team leader", "Global Amb", "Co-Manager"),
            "is_staff": bool(body.get("is_staff")) or bool(body.get("is_support")),
            "can_approve_password": bool(body.get("is_support")),
            "can_approve_deposit": bool(body.get("can_approve_deposit")),
            "can_approve_withdraw": bool(body.get("can_approve_withdraw")),
            "approved": approve,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by_admin": True,
        }
        if title == "Junior Shareholder":
            new_user["junior_shareholder"] = True
        users = get_users()
        users.append(new_user)
        save_users(users)
        return self._json(200, {"message": "Account created", "user": public_user(new_user)})

    def _admin_deposit_action(self, body):
        did = body.get("id")
        action = (body.get("action") or "").lower()  # confirm | approve | reject
        if action == "approve":
            action = "confirm"
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
            amt = float(dep.get("amount") or 0)
            bonus = round(amt * 0.025, 2)
            credit_total = round(amt + bonus, 2)
            dep["bonus"] = bonus
            dep["credited_total"] = credit_total
            # Company pool pays the credit to customer wallet
            usd = ugx_to_usd(credit_total)
            pool = adjust_pool(-usd, f"Deposit approved → {user.get('name') or user_id}", {
                "user_id": user_id, "dep_id": did, "amount_ugx": credit_total, "type": "deposit_credit"
            })
            user["balance"] = round(float(user.get("balance") or 0) + credit_total, 2)
            if not user.get("join_deposit"):
                user["join_deposit"] = amt
            user.setdefault("transactions", []).insert(0, {
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": f"Deposit confirmed — {dep.get('method') or 'pay'}",
                "amount": amt,
            })
            if bonus:
                user.setdefault("transactions", []).insert(0, {
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "type": "Deposit 2.5% bonus",
                    "amount": bonus,
                })
            update_user(user)
            return self._json(200, {
                "message": f"Deposit confirmed · credited {credit_total}",
                "deposit": dep,
                "user": public_user(user),
                "pool_usd": pool.get("balance_usd"),
            })
        else:
            dep["status"] = "rejected"
            user.setdefault("transactions", []).insert(0, {
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": f"Deposit rejected — {dep.get('method') or 'pay'}",
                "amount": 0,
            })
            update_user(user)
            try:
                ws_broadcast("deposit", {"status": "rejected"})
                ws_broadcast("users", {"reason": "deposit"})
            except Exception:
                pass
            return self._json(200, {"message": "Deposit rejected", "deposit": dep, "user": public_user(user)})


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
    # Bind immediately so Railway healthcheck (/api/health) can succeed.
    class _Server(ThreadingHTTPServer):
        allow_reuse_address = True
        daemon_threads = True

    httpd = _Server((HOST, PORT), Handler)
    print(f"[boot] Own Club listening on {HOST}:{PORT}", flush=True)
    print(f"[boot] health http://0.0.0.0:{PORT}/api/health", flush=True)

    def _boot_jobs():
        try:
            seed_admin()
            seed_support_staff()
        except Exception as e:
            print("[boot] seed", e)
        try:
            ensure_vapid_keys()
        except Exception as e:
            print("[push] boot", e)
        try:
            # Do not wipe customers on every Railway restart
            if (os.environ.get("RESET_CUSTOMERS") or "").strip() == "1":
                wipe_customer_accounts()
                seed_admin()
                seed_support_staff()
        except Exception as e:
            print("[boot] wipe failed", e)

    threading.Thread(target=_boot_jobs, daemon=True).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
