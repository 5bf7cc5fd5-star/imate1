#!/usr/bin/env python3
from pathlib import Path
import runpy
import subprocess
import sys

root = Path(__file__).resolve().parent
(root / "static").mkdir(exist_ok=True)
(root / "data").mkdir(exist_ok=True)

try:
    import persist
    persist.init()
except Exception as e:
    print("persist init", e)

for script in ("inject_ops.py", "fix_admin_phone.py", "migrate.py"):
    p = root / script
    if p.exists():
        try:
            subprocess.check_call([sys.executable, str(p)], cwd=str(root))
        except Exception as e:
            print(script, "failed", e)

INJECT = """
<link rel=\"stylesheet\" href=\"/static/login-tight.css?v=30\">
<script src=\"/static/login-tight.js?v=30\"></script>
<script src=\"/static/market-data.js?v=30\"></script>
<script src=\"/static/lock-nav.js?v=30\"></script>
<script src=\"/static/nav-rules.js?v=30\"></script>
<script src=\"/static/member-id.js?v=30\"></script>
<script src=\"/static/tx-history.js?v=30\"></script>
<style id=\"login-iphone-30\">
#authScreen{justify-content:flex-start!important;overflow:hidden!important;height:100dvh!important;padding:28px 18px 12px!important;}
#authScreen .auth-logo{margin:0 0 8px!important;}
#authScreen img,#authScreen svg{max-height:56px!important;height:56px!important;}
#authScreen input{min-height:40px!important;height:40px!important;margin:0!important;}
</style>
"""

def inject_once(text, needle, blob):
    if needle in text:
        return text
    if "</body>" in text:
        return text.replace("</body>", blob + "\n</body>", 1)
    return text + blob

for name in ("index.html", "frontend.html"):
    p = root / name
    if p.exists():
        old = p.read_text(encoding="utf-8", errors="replace")
        new = inject_once(old, "login-iphone-30", INJECT)
        if new != old:
            p.write_text(new, encoding="utf-8")
            print("iphone login", name)

print("boot starting server")
runpy.run_path(str(root / "server.py"), run_name="__main__")
