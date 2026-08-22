#!/usr/bin/env python3
from pathlib import Path
import runpy, subprocess, sys
root = Path(__file__).resolve().parent
(root / "static").mkdir(exist_ok=True)
(root / "data").mkdir(exist_ok=True)
try:
    import persist; persist.init()
except Exception as e:
    print("persist init", e)
for script in ("inject_ops.py", "fix_admin_phone.py", "migrate.py"):
    p = root / script
    if p.exists():
        try: subprocess.check_call([sys.executable, str(p)], cwd=str(root))
        except Exception as e: print(script, "failed", e)

# Force a script tag into html even if older inject exists
TAG = '<script src="/static/login-tight.js?v=36"></script>'
for name in ("index.html", "frontend.html"):
    p = root / name
    if not p.exists():
        continue
    t = p.read_text(encoding="utf-8", errors="replace")
    if "login-tight.js?v=36" not in t:
        if "</body>" in t:
            t = t.replace("</body>", TAG + "\n</body>", 1)
        else:
            t += "\n" + TAG
        p.write_text(t, encoding="utf-8")
        print("injected v36", name)

print("boot starting server")
runpy.run_path(str(root / "server.py"), run_name="__main__")
