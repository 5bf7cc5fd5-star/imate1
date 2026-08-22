#!/usr/bin/env python3
from pathlib import Path
import runpy, subprocess, sys, base64

root = Path(__file__).resolve().parent
(root / "static").mkdir(exist_ok=True)
(root / "data").mkdir(exist_ok=True)

# Permanent logo install from b64 if present
for b64name, outname in (("static/logo.b64", "own-club-logo.jpg"), ("static/logo.b64", "static/own-club-logo.jpg")):
    bp = root / "static" / "logo.b64"
    if bp.exists():
        try:
            data = base64.b64decode(bp.read_text().strip())
            (root / outname).write_bytes(data)
            print("logo written", outname, len(data))
        except Exception as e:
            print("logo decode", e)

try:
    import persist; persist.init()
except Exception as e:
    print("persist init", e)

for script in ("inject_ops.py", "fix_admin_phone.py", "migrate.py"):
    p = root / script
    if p.exists():
        try: subprocess.check_call([sys.executable, str(p)], cwd=str(root))
        except Exception as e: print(script, "failed", e)

TAG = '<script src="/static/login-tight.js?v=37"></script>'
for name in ("index.html", "frontend.html"):
    p = root / name
    if not p.exists():
        continue
    t = p.read_text(encoding="utf-8", errors="replace")
    # strip older login-tight tags then inject latest
    import re
    t2 = re.sub(r'<script[^>]*login-tight\.js[^>]*></script>', '', t)
    if "login-tight.js?v=37" not in t2:
        if "</body>" in t2:
            t2 = t2.replace("</body>", TAG + "\n</body>", 1)
        else:
            t2 += "\n" + TAG
    if t2 != t:
        p.write_text(t2, encoding="utf-8")
        print("injected v37", name)

print("boot starting server")
runpy.run_path(str(root / "server.py"), run_name="__main__")
