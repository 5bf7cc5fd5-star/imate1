"""Staff positions requested for Own Club."""

POSITIONS = {
    "owner": {
        "label": "Owner",
        "desc": "Full system control",
        "is_admin": True,
        "is_support": False,
        "can_approve_withdraw": True,
        "can_approve_deposit": True,
        "can_approve_password": True,
        "can_pool": True,
        "can_credit": True,
    },
    "full_admin": {
        "label": "Full Admin — Deposits & Withdrawals",
        "desc": "Approve deposits and withdrawals",
        "is_admin": True,
        "is_support": False,
        "can_approve_withdraw": True,
        "can_approve_deposit": True,
        "can_approve_password": True,
        "can_pool": True,
        "can_credit": True,
    },
    "support": {
        "label": "Support — Password help only",
        "desc": "Customer password help. No deposits or withdrawals.",
        "is_admin": False,
        "is_support": True,
        "can_approve_withdraw": False,
        "can_approve_deposit": False,
        "can_approve_password": True,
        "can_pool": False,
        "can_credit": False,
    },
    "finance": {
        "label": "Finance — Pool & credits",
        "desc": "Company pool and member credits",
        "is_admin": True,
        "is_support": False,
        "can_approve_withdraw": False,
        "can_approve_deposit": False,
        "can_approve_password": False,
        "can_pool": True,
        "can_credit": True,
    },
    "inventory": {
        "label": "Inventory — Company pool reports",
        "desc": "Track company pool only",
        "is_admin": True,
        "is_support": False,
        "can_approve_withdraw": False,
        "can_approve_deposit": False,
        "can_approve_password": False,
        "can_pool": True,
        "can_credit": False,
    },
    "viewer": {
        "label": "Viewer",
        "desc": "Read-only console",
        "is_admin": False,
        "is_support": True,
        "can_approve_withdraw": False,
        "can_approve_deposit": False,
        "can_approve_password": False,
        "can_pool": False,
        "can_credit": False,
    },
}


def apply_position(user: dict, position: str) -> dict:
    key = (position or "").strip().lower()
    if key not in POSITIONS:
        raise ValueError("Unknown position")
    spec = POSITIONS[key]
    user["position"] = key
    user["position_label"] = spec["label"]
    for k, v in spec.items():
        if k in ("label", "desc"):
            continue
        user[k] = v
    return user


def list_positions():
    return [{"id": k, **v} for k, v in POSITIONS.items()]
