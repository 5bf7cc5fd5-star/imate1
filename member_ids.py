"""Own Club member numbers: OCS-AEI12"""
import random
import string
import uuid

PREFIX = "OCS-"


def alloc(users):
    used = set()
    for u in users or []:
        used.add(str(u.get("member_no") or "").upper())
    letters = string.ascii_uppercase
    digits = string.digits
    for _ in range(400):
        code = PREFIX + "".join(random.choice(letters) for _ in range(3)) + "".join(random.choice(digits) for _ in range(2))
        if code not in used:
            return code
    return PREFIX + uuid.uuid4().hex[:5].upper()
