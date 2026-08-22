"""Force Owner phone to +256779168109."""
import json
from pathlib import Path

NEW = "+256779168109"
TARGET_EMAIL = "k_hmed@yahoo.com"

def run():
    p = Path(__file__).parent / "data" / "users.json"
    if not p.exists():
        print("no users.json yet")
        return
    try:
        users = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print("users.json read fail", e)
        return
    changed = False
    for u in users:
        email = (u.get("email") or "").lower()
        if email == TARGET_EMAIL or u.get("id") == "admin" or (u.get("name") or "").startswith("Admin"):
            if u.get("phone") != NEW:
                u["phone"] = NEW
                changed = True
    if changed:
        p.write_text(json.dumps(users, indent=2, ensure_ascii=False), encoding="utf-8")
        print("owner phone ->", NEW)
    else:
        print("owner phone already", NEW)

if __name__ == "__main__":
    run()
